# Add a new MCP Tool: `get_markdown_content`

This guide walks you from zero to a working MCP tool that fetches the **Markdown rendition** of an Alfresco node via REST, and tests it with **MCP Inspector**.

What we’re building (in plain words)

* An MCP server (Python app) that exposes tools an LLM can call
* A new tool named `get_markdown_content(node_id)` that calls the Alfresco REST API:
  ```
  GET /alfresco/api/-default-/public/alfresco/versions/1/nodes/{nodeId}/renditions/markdown/content
  ```
* It returns the Markdown text of the document (convenient for LLMs)

> We will be extending the Community [Alfresco MCP Server](https://github.com/stevereiner/python-alfresco-mcp-server.git) provided by Steve Reiner

## Requirements

### Runtime

* Python 3.10+ (3.11 recommended)
* Alfresco Repository running locally with a *markdown* rendition available, like https://github.com/aborroy/alfresco-markdown-rendition

### Testing

* Node.js 18+ (for MCP Inspector)

> Check you have them
>
> ```bash
> python --version
> node --version
> npm --version
> ```

If you don’t have Python

* macOS: `brew install python`
* Windows: install from [https://www.python.org/downloads/](https://www.python.org/downloads/) (then use `py` instead of `python`)

If you don’t have Node

* macOS: `brew install node`
* Windows/macOS/Linux: [https://nodejs.org/en/download](https://nodejs.org/en/download)

## Set up development environment

Get the source code

```bash
git clone https://github.com/stevereiner/python-alfresco-mcp-server.git
cd python-alfresco-mcp-server
```

Create the Python Virtual Environment

* macOS/Linux

  ```bash
  python -m venv .venv && source .venv/bin/activate
  ```
* Windows (PowerShell)

  ```powershell
  py -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

> You should see `(.venv)` prefix in your terminal after activation

Install dependencies

```bash
python -m pip install -U pip
pip install -e ".[dev]"
```

## Develop the integration with Alfresco Repository REST API

Create a new file `alfresco_mcp_server/tools/core/get_markdown_content.py`

```python
import httpx
from ...config import config

async def get_markdown_content_impl(
    node_id: str
) -> str:
    try:
        url = (
            f"{config.alfresco_url.rstrip('/')}/alfresco/api/-default-/public/"
            f"alfresco/versions/1/nodes/{node_id}/renditions/markdown/content"
        )
        
        async with httpx.AsyncClient(
            verify=config.verify_ssl,
            timeout=config.timeout,
            auth=(config.username, config.password),
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)

        return resp.text

    except Exception as e:
        return f"Failed to retrieve Markdown for `{node_id}`: {str(e)}"

```

## Declare the new MCP tool

Edit `alfresco_mcp_server/fastmcp_server.py` and add

```python

# Core tools imports
from .tools.core.get_markdown_content import get_markdown_content_impl

# ================== CORE TOOLS ==================

@mcp.tool
async def get_markdown_content(
    node_id: str
) -> str:
    """Fetch the Markdown/Text rendition of an Alfresco node."""
    return await get_markdown_content_impl(node_id)
```

## Testing

Follow Alfresco Docker Compose deployment instructions in [alfresco-deploment](../alfresco-deployment] and verify Alfresco Repository is running in http://localhost:8080/alfresco

Create a `.env` file in the MCP repo root (same folder as `run_server.py`):

```dotenv
ALFRESCO_URL=http://localhost:8080
ALFRESCO_USERNAME=admin
ALFRESCO_PASSWORD=admin
VERIFY_SSL=false
TIMEOUT_SECONDS=30
```

Start the MCP Server

```bash
python3 run_server.py --transport http --host 127.0.0.1 --port 8003
```

> You should see it listening (no errors)

Install the MCP Inspector Tool (only once)

```bash
npm install -g @modelcontextprotocol/inspector
```

Create `mcp.json` in the repo root with this content

```json
{
  "mcpServers": {
    "alfresco": {
      "type": "streamable-http",
      "url": "http://127.0.0.1:8003/mcp",
      "env": {
        "ALFRESCO_URL": "http://localhost:8080",
        "ALFRESCO_USERNAME": "admin",
        "ALFRESCO_PASSWORD": "admin"
      }
    }
  }
}
```

Run the MCP Inspector

```bash
mcp-inspector --config ./mcp.json
...
🚀 MCP Inspector is up and running at:
   http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=519d80542e5a280262c40c757ef90176bf7adbabe51e332cb17a0e3e1f9e9570
```

* Open the printed local URL (e.g., `http://localhost:6274/...`) in your browser
* Navigate to *Connect → Tools → List Tools → `get_markdown_content`*

Find a `uuid` for a Node in Alfresco Repository, like `ab47a9a3-ec77-43b2-87a9-a3ec7783b2e9`

```bash
curl -s -u admin:admin \
  -X POST "http://localhost:8080/alfresco/api/-default-/public/search/versions/1/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "query": "TYPE:\"cm:content\""
    },
    "paging": {
      "maxItems": 5,
      "skipCount": 0
    },
    "sort": [
      { "type": "FIELD", "field": "cm:modified", "ascending": false }
    ],
    "include": ["properties"]
  }'

{
  "list": {
    "pagination": {
    },
    "entries": [
      {
        "entry": {
          "isFile": true,
          "name": "test.odt",
          "id": "ab47a9a3-ec77-43b2-87a9-a3ec7783b2e9",
          "properties": {
          }
        }
      },  
```

In Inspector, set:

* `node_id`: your UUID (e.g., `ab47a9a3-ec77-43b2-87a9-a3ec7783b2e9`)

Click `Run Tool`

Expected output (shape):

```
# Title
This is a simple test document...
```

## Why this design helps the LLM

- Tool name is verb-first and specific: `get_markdown_content`
- Docstring is short and keyword-rich (markdown/text/rendition)
- Parameters are self-descriptive (`node_id`)
- Result returns a fenced markdown block—perfect to feed into downstream LLM steps
