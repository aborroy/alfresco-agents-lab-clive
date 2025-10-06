# Add a Summary Action to ACA

This guide walks you from zero to a working [ACA](https://github.com/Alfresco/alfresco-content-app) action that calculates a summary of the document and stores the result in property `cm:description`

What we’re building (in plain words)

* An Alfresco Content Application that adds the action `Summarize` to documents
* It stores the summary in property `cm:description` of the document
* Invokes FastAPI Agent REST API `/agent` with a prompt that asks for the summarization and the storage

## Requirements

### Runtime

* Alfresco Agents Lab stack running locally with the Agent REST API available in http://localhost:8000/agent, instructions available in root [README.md](../README.md)

### Developing

* Node.js 18+

> Check you have them
>
> ```bash
> node --version
> npm --version
> ```

If you don’t have Node

* macOS: `brew install node`
* Windows/macOS/Linux: [https://nodejs.org/en/download](https://nodejs.org/en/download)

## Set up development environment

Get the source code

```bash
git clone git@github.com:Alfresco/alfresco-content-app.git
cd alfresco-content-app
```

Create the configuration file

```bash
vi .env
BASE_URL="http://localhost:8080"
```

Install dependencies

```bash
npm install
```

## Develop the integration with Agent REST API

Create a new folder for the assets of the summary extension

```bash
mkdir -p projects/ext-summary/src/effects
```

Code the service class as a new ACA Action in file `projects/ext-summary/src/effects/summary.effects.ts`

```typescript
import { Injectable, inject } from '@angular/core';
import { Actions, createEffect, ofType } from '@ngrx/effects';
import { HttpClient } from '@angular/common/http';
import { MatSnackBar } from '@angular/material/snack-bar';
import { tap } from 'rxjs';

@Injectable()
export class SummaryEffects {
  private actions$ = inject(Actions);
  private http = inject(HttpClient);
  private snackBar = inject(MatSnackBar);

  summarize$ = createEffect(
    () =>
      this.actions$.pipe(
        ofType('SUMMARY'),
        tap((action: any) => {
          const node = action.payload;
          const nodeId = node?.id;
          const nodeName = node?.name || 'file';
          const prompt = `Fetch Markdown for node ${nodeId}, summarize it in 50 words or less and store the result in cm:description property.`;
          this.snackBar.open(`Summary requested for ${nodeName}`, 'OK', { duration: 3000 });
          this.http.post('/agent', { prompt }).subscribe({
            next: () => this.snackBar.open(`Summary completed for ${nodeName}`, 'OK', { duration: 3000 }),
            error: () => this.snackBar.open(`Summary failed for ${nodeName}`, 'Close', { duration: 3000 })
          });
        })
      ),
    { dispatch: false }
  );
}
```

Create the ACA Action configuration file in `projects/ext-summary/src/assets/ext-summary.plugin.json`

```json
{
  "$schema": "../../../../extension.schema.json",
  "$id": "aca-ext-summary",
  "$version": "1.0.0",
  "$name": "Summarize",
  "$vendor": "Alfresco",
  "$license": "LGPL-3.0",

  "actions": [
    { "id": "summary.fromContext", "type": "SUMMARY", "payload": "$(context.menu.entry)" },
    { "id": "summary.fromToolbar", "type": "SUMMARY", "payload": "$(context.selection.first.entry)" },
    { "id": "summary.fromViewer",  "type": "SUMMARY", "payload": "$(context.preview.node)" }
  ],

  "features": {
    "toolbar": [
      {
        "id": "app.toolbar.more",
        "children": [
          {
            "id": "summary.toolbar.button",
            "order": 90,
            "icon": "description",
            "title": "Summarize",
            "actions": { "click": "summary.fromToolbar" },
            "rules": { "visible": ["app.selection.file"] }
          }
        ]
      }
    ],

    "contextMenu": [
      {
        "id": "summary.context.button",
        "order": 450,
        "icon": "description",
        "title": "Summarize",
        "actions": { "click": "summary.fromContext" },
        "rules": { "visible": ["app.context.file"] }
      }
    ],

    "viewer": {
      "toolbarActions": [
        {
          "id": "app.viewer.toolbar.more",
          "children": [
            {
              "id": "summary.viewer.button",
              "order": 1,
              "icon": "description",
              "title": "Summarize",
              "actions": { "click": "summary.fromViewer" }
            }
          ]
        }
      ]
    }
  }
}
```

Declare the ACA Extension in file `projects/ext-summary/src/lib/ext-summary.module.ts`

```typescript
import { NgModule, Provider, EnvironmentProviders } from '@angular/core';
import { provideExtensionConfig } from '@alfresco/adf-extensions';
import { provideEffects } from '@ngrx/effects';
import { SummaryEffects } from '../effects/summary.effects';

export function provideSummaryExtension(): (Provider | EnvironmentProviders)[] {
  return [
    provideExtensionConfig(['ext-summary.plugin.json']),
    provideEffects(SummaryEffects)
  ];
}

@NgModule({
  providers: [...provideSummaryExtension()]
})
export class ExtSummaryModule {}
```

Export all elements from the module in `projects/ext-summary/src/public-api.ts`

```typescript
export * from './lib/ext-summary.module';
```

## Attach the ACA Extension to the ACA Application

Modify the file `app/src/app/extensions.module.ts` to add the following lines that import the `provideSummaryExtension` function

```typescript
...
import { provideSummaryExtension } from 'projects/ext-summary/src/public-api';
...
export function provideApplicationExtensions(): (Provider | EnvironmentProviders)[] {
  return [
    ...
    ...provideSummaryExtension(),
    ...
  ];
```

Add the ACA Action configuration file in `app/project.json`

```typescript
{
  "name": "content-ce",
  "targets": {
    "build": {
      "executor": "@angular-devkit/build-angular:browser",
      "options": {
        },
        "assets": [
          ...,
          {
            "glob": "ext-summary.plugin.json",
            "input": "projects/ext-summary/src/assets",
            "output": "./assets/plugins"
          }
        ],
        ...
```

Finally, add the Fast API URL to the Proxy to avoid CORS problems in `app/proxy.conf.js`

```typescript
module.exports = {
  ...
  '/agent': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    secure: false,
    logLevel: 'debug'
  }
};
```

## Testing

Start locally the ACA application

```bash
npm start
```

> You should see it listening in port 4200 (no errors)

Verify again that Alfresco Agents Lab stack is running locally and available in http://localhost:8000

Open the browser at http://localhost:4200 and login using default credentials (`admin`/`admin`)

Select a document in the UI and click `Summarize` action

![Screen capture](add-action-to-aca.png)

A toast message will inform that the action is running in the background: "Summary requested for document.pdf"

After a while a new toast message will inform that the action has finished: "Summary completed for document.pdf"

At this point you can verify in the UI that `Description` property for the document has been populated with the summar

## What happened?

A complex integration with Alfresco Repository has been done by using a simple prompt:

*Fetch Markdown for node ${nodeId}, summarize it in 50 words or less and store the result in cm:description property.*
