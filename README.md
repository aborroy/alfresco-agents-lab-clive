# FastAPI Agent

A FastAPI service that runs AI agents with Ollama/LiteLLM and MCP tools.

## Project Structure

This is organized as a monorepo-friendly structure:
```
├── docker-compose.yaml          # Root docker-compose for all services
├── .env                         # Root environment for docker-compose
├── fastapi-agent/              # FastAPI service
│   ├── main.py                 # FastAPI application
│   ├── pyproject.toml          # Python dependencies
│   ├── dockerfile              # Container build
│   ├── .env                    # Local development config
│   └── .env.example            # Configuration template
└── README.md                   # This file
```

## Quick Start

### Without Docker (using uv)

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Navigate to the service directory
cd fastapi-agent

# Install dependencies and run
uv sync
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### With Docker

```bash
# From the root directory
docker-compose up --build
```

**Note**: Environment variables for Docker are read from the root `.env` file.

## Configuration

All configuration is loaded from `fastapi-agent/.env` file. You can choose between two LLM providers:

### Option 1: Self-hosted with Ollama

```env
# LLM Configuration
LLM_CHOICE=ollama
OLLAMA_MODEL=gpt-oss:20b
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=300

# MCP Tools
MCP_SERVER_URL=http://localhost:8003/mcp
```

### Option 2: Claude via Hyland ML Platform

```env
# LLM Configuration
LLM_CHOICE=litellm
LITELLM_MODEL=litellm_proxy/anthropic.claude-sonnet-4-20250514-v1:0
LITELLM_API_KEY=sk-7onSBXvm_SctdjwSZCBBeg
LITELLM_API_BASE=https://api.ai.dev.experience.hyland.com/litellm

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
