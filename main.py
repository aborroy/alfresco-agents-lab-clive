import os
import logging
from typing import Optional, Any, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

from llama_index.core.agent.workflow import AgentWorkflow

# LLM imports
from llama_index.llms.ollama import Ollama
from llama_index.llms.litellm import LiteLLM

# MCP / tooling imports
from llama_index.tools.mcp import aget_tools_from_mcp_url
from llama_index.tools.mcp import BasicMCPClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-service")

load_dotenv()

# Config via env - no defaults, everything from .env
LLM_CHOICE = os.getenv("LLM_CHOICE")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TIMEOUT = float(
    os.getenv("OLLAMA_TIMEOUT", "120.0")
)  # Keep this default for safety
LITELLM_MODEL = os.getenv("LITELLM_MODEL")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")

app = FastAPI(title="Agent with Ollama / LiteLLM + MCP Tools")


class AgentRequest(BaseModel):
    instructions: Optional[str] = None
    prompt: str


class AgentResponse(BaseModel):
    output: str
    debug: Optional[Any] = None


@app.get("/")
async def health():
    return {"status": "ok"}


def build_llm():
    """
    Build the selected LLM instance.
    """
    if LLM_CHOICE.lower() == "ollama":
        # Ollama with configurable base URL for Docker/remote access
        llm = Ollama(
            model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL, request_timeout=OLLAMA_TIMEOUT
        )
    elif LLM_CHOICE.lower() == "litellm":
        llm = LiteLLM(model=LITELLM_MODEL)
    else:
        raise ValueError(f"Unsupported LLM_CHOICE: {LLM_CHOICE}")
    return llm


async def fetch_mcp_tools() -> List[Any]:
    """
    Fetch MCP tools from the MCP server and convert to LlamaIndex tools.
    """
    if MCP_SERVER_URL is None:
        return []
    # Use asynchronous fetch
    try:
        tools = await aget_tools_from_mcp_url(
            MCP_SERVER_URL,
            client=BasicMCPClient(MCP_SERVER_URL),
            allowed_tools=None,
        )
        logger.info(f"Fetched {len(tools)} tools from MCP")
        return tools
    except Exception as e:
        logger.error(f"Error fetching MCP tools: {e}")
        return []


@app.post("/agent", response_model=AgentResponse)
async def run_agent(req: AgentRequest):
    try:
        llm = build_llm()

        # Fetch tools from MCP server
        mcp_tools = await fetch_mcp_tools()

        # Build the agent
        agent = AgentWorkflow.from_tools_or_functions(
            mcp_tools,
            llm=llm,
            system_prompt=req.instructions,
            verbose=False,
        )
        result = await agent.run(req.prompt)

        # Extract text from AgentOutput -> ChatMessage -> TextBlock
        text = "No output generated"

        if hasattr(result, "response") and hasattr(result.response, "blocks"):
            for block in result.response.blocks:
                if hasattr(block, "text"):
                    text = block.text
                    break

        return {"output": text, "debug": {"repr": repr(result)}}
    except Exception as e:
        logger.exception("Agent run failed")
        raise HTTPException(status_code=500, detail=f"agent error: {e}")
