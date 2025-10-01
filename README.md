# FastAPI Agent

A FastAPI service that runs AI agents with Ollama/LiteLLM and MCP tools.

## Quick Start

### Without Docker (using uv)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies and run
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### With Docker

```bash
docker-compose up --build
```

## Configuration

All configuration is loaded from `.env` file. Create it with your local settings:

```env
# LLM Configuration
LLM_CHOICE=ollama
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=300
LITELLM_MODEL=gpt-3.5-turbo

# MCP Tools
MCP_SERVER_URL=http://localhost:8003/mcp
```

### Docker

When running with Docker, the `docker-compose.yaml` automatically overrides the URLs to use `host.docker.internal` so the container can access services on your host machine. Your `.env` file stays the same for both local and Docker usage.

## Usage

POST to `/agent` with:
```json
{
  "prompt": "What tools do you have?",
  "instructions": "Be helpful and concise"
}
```
