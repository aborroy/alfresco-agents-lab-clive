# Alfresco Agents Lab (CLive)

End-to-end lab to run Alfresco Community (with Markdown renditions) + an MCP server (with a Markdown tool) + a FastAPI Agent that consumes MCP tools through LlamaIndex. Everything can be started **from the repo root** with a single Compose file.

> The MCP tool added here follows the lab guide: "Add MCP Tool" in `lab-material/add-mcp-tool.md`

## Repository layout

```
/
├─ alfresco-deployment/          # Complete Alfresco CE deployment (repo, solr, share, ACA, transforms, proxy)
├─ alfresco-mcp-server/          # Containerized MCP server wired to Alfresco
│  ├─ compose.yaml
│  ├─ Dockerfile
│  └─ get_markdown_content.py    # Tool implementation (see “Added MCP tool”)
├─ fastapi-agent/                # FastAPI service (Agent) with LlamaIndex + MCP tools
│  ├─ main.py
│  └─ dockerfile
├─ lab-material/
│  └─ add-mcp-tool.md            # Step-by-step guide for adding the Markdown tool
└─ compose.yaml                  # Root Compose that includes the two sub-stacks + agent
```

## TL;DR – Run the whole thing

1. Prereqs

* Docker Desktop / Engine with Docker Compose v2 (supports `include:` in `compose.yaml`)
* Ollama running on your host with required models

  ```bash
  # for the Markdown transformer
  ollama pull llava
  # for the agent (or change OLLAMA_MODEL in .env)
  ollama pull gpt-oss
  ```

  Ollama should listen on `http://localhost:11434` (used via `host.docker.internal` inside containers)

2. Up the full stack from the repo root

```bash
docker compose up --build
```

3. Open the UIs

* Alfresco Content App: [http://localhost:8080/](http://localhost:8080/)
* Alfresco Repository: [http://localhost:8080/alfresco/](http://localhost:8080/alfresco/)
* MCP Server (health/endpoint): [http://localhost:8003/mcp](http://localhost:8003/mcp)
* Agent API (FastAPI): [http://localhost:8000/](http://localhost:8000/)  (health), `POST /agent` (run)

## Added MCP tool (Markdown rendition)

This lab adds a lightweight tool so the MCP server can fetch the Markdown/Text rendition of an Alfresco node

* Implementation: `alfresco-mcp-server/get_markdown_content.py`
* Registration: the server is patched per the guide so the tool is exposed at runtime
* Source steps are documented in `lab-material/add-mcp-tool.md`

Original Alfresco MCP Server source code is available in https://github.com/stevereiner/python-alfresco-mcp-server

> The Alfresco Repository is already configured with
> `-DlocalTransform.md.url=http://transform-md:8090/`
> and the `transform-md` service expects Ollama with `llava` on your host

## Using the Agent

The Agent consumes **MCP tools** from `alfresco-mcp-server` and runs prompts with your chosen LLM

Run an agent turn, like in following samples

```bash
curl -sS http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What tools do you have?","instructions": "Be helpful and concise"}'
```

```bash
curl -sS http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Fetch Markdown for node 947c51e2-6ffd-4eb8-bc51-e26ffd1eb8b6 and summarize it"}'
```