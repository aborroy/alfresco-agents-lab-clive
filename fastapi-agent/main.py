import os
import asyncio
import logging
from typing import Optional, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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

# -----------------------------
# Config via env
# -----------------------------
LLM_CHOICE = os.getenv("LLM_CHOICE")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TIMEOUT = float(os.getenv("OLLAMA_TIMEOUT", "120.0"))  # safe default

LITELLM_MODEL = os.getenv("LITELLM_MODEL")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY")
LITELLM_API_BASE = os.getenv("LITELLM_API_BASE")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")

# Log startup configuration
logger.info("=" * 60)
logger.info("FASTAPI AGENT STARTING UP")
logger.info("=" * 60)
logger.info("Configuration:")
logger.info(f" LLM_CHOICE: {LLM_CHOICE}")
logger.info(f" OLLAMA_MODEL: {OLLAMA_MODEL}")
logger.info(f" OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")
logger.info(f" OLLAMA_TIMEOUT: {OLLAMA_TIMEOUT}")
logger.info(f" LITELLM_MODEL: {LITELLM_MODEL}")
logger.info(f" LITELLM_API_BASE: {LITELLM_API_BASE}")
logger.info(
    f" LITELLM_API_KEY: {'*' * (len(LITELLM_API_KEY) - 4) + LITELLM_API_KEY[-4:] if LITELLM_API_KEY else 'None'}"
)
logger.info(f" MCP_SERVER_URL: {MCP_SERVER_URL}")
logger.info("=" * 60)

app = FastAPI(title="Agent with Ollama / LiteLLM + MCP Tools")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Models
# -----------------------------
class AgentRequest(BaseModel):
    instructions: Optional[str] = None
    prompt: str


class AgentResponse(BaseModel):
    output: str
    debug: Optional[Any] = None


# -----------------------------
# LLM builder
# -----------------------------
def build_llm():
    """Build the selected LLM instance."""
    if not LLM_CHOICE:
        raise ValueError("LLM_CHOICE is not set")

    logger.info(f"Building LLM with choice: {LLM_CHOICE}")

    if LLM_CHOICE.lower() == "ollama":
        logger.info("Configuring Ollama LLM:")
        logger.info(f" Model: {OLLAMA_MODEL}")
        logger.info(f" Base URL: {OLLAMA_BASE_URL}")
        logger.info(f" Timeout: {OLLAMA_TIMEOUT}")

        if not OLLAMA_MODEL or not OLLAMA_BASE_URL:
            raise ValueError("OLLAMA_MODEL and OLLAMA_BASE_URL must be set for Ollama")

        llm = Ollama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            request_timeout=OLLAMA_TIMEOUT,
            additional_kwargs={
                "temperature": 0.1,  # low temp for consistent tool calls
                "top_p": 0.9,
            },
        )
        logger.info("Ollama LLM created successfully")
        return llm

    if LLM_CHOICE.lower() == "litellm":
        logger.info("Configuring LiteLLM:")
        logger.info(f" Model: {LITELLM_MODEL}")
        logger.info(f" API Base: {LITELLM_API_BASE}")
        logger.info(
            f" API Key: {'*' * (len(LITELLM_API_KEY) - 4) + LITELLM_API_KEY[-4:] if LITELLM_API_KEY else 'None'}"
        )

        if not (LITELLM_MODEL and LITELLM_API_BASE and LITELLM_API_KEY):
            raise ValueError("LITELLM_MODEL, LITELLM_API_BASE and LITELLM_API_KEY must be set for LiteLLM")

        llm = LiteLLM(
            model=LITELLM_MODEL,
            api_key=LITELLM_API_KEY,
            api_base=LITELLM_API_BASE,
            temperature=0.1,  # consistent JSON generation
        )
        logger.info("LiteLLM created successfully")
        return llm

    error_msg = f"Unsupported LLM_CHOICE: {LLM_CHOICE}"
    logger.error(error_msg)
    raise ValueError(error_msg)


# ------------------------------
# MCP tools: cached, atomic init
# ------------------------------
_MCP_TOOLS: List[Any] | None = None
_MCP_INIT_LOCK = asyncio.Lock()
_MCP_INIT_ERROR: Exception | None = None


async def get_mcp_tools_cached() -> List[Any]:
    """
    Ensure MCP tools are fetched once and reused.
    If another request is already initializing, wait for it.
    If init fails, raise so the caller sees a 503/500 instead of silently proceeding.
    """
    global _MCP_TOOLS, _MCP_INIT_ERROR

    if _MCP_TOOLS is not None:
        return _MCP_TOOLS

    async with _MCP_INIT_LOCK:
        if _MCP_TOOLS is not None:  # re-check after acquiring the lock
            return _MCP_TOOLS

        if not MCP_SERVER_URL:
            raise RuntimeError("MCP_SERVER_URL is not configured")

        logger.info(f"Attempting to fetch MCP tools from: {MCP_SERVER_URL}")
        last_exc: Exception | None = None

        # A couple of short retries help with cold MCP servers
        for attempt in range(1, 4):
            try:
                client = BasicMCPClient(MCP_SERVER_URL)
                tools = await aget_tools_from_mcp_url(
                    MCP_SERVER_URL, client=client, allowed_tools=None
                )

                if not tools:
                    raise RuntimeError("MCP returned zero tools")

                # Log details about each tool (briefly)
                tool_names = []
                for i, tool in enumerate(tools):
                    name = getattr(tool, "name", None)
                    if not name and hasattr(tool, "metadata"):
                        name = getattr(tool.metadata, "name", None)
                    tool_names.append(name or f"tool_{i}")
                logger.info(f"Cached {len(tools)} MCP tools: {tool_names}")

                _MCP_TOOLS = tools
                _MCP_INIT_ERROR = None
                return _MCP_TOOLS

            except Exception as e:
                last_exc = e
                logger.warning(f"MCP fetch attempt {attempt} failed: {type(e).__name__}: {e}")
                await asyncio.sleep(0.5 * attempt)

        _MCP_INIT_ERROR = last_exc or RuntimeError("Unknown MCP init error")
        raise _MCP_INIT_ERROR


# Optional warm-start: prebuild LLM and MCP tools so the first call never races
@app.on_event("startup")
async def _warm_start():
    try:
        build_llm()
    except Exception as e:
        logger.warning(f"LLM warm start skipped/failed: {e}")

    try:
        await get_mcp_tools_cached()
        logger.info("MCP warm start completed")
    except Exception as e:
        logger.warning(f"MCP warm start skipped/failed: {e}")


# -----------------------------
# Health endpoints
# -----------------------------
@app.get("/")
async def health():
    return {"status": "ok", "service": "fastapi-agent"}


@app.get("/health")
async def detailed_health():
    """Detailed health check endpoint."""
    try:
        llm = build_llm()
        llm_status = "ok"
        llm_type = type(llm).__name__
    except Exception as e:
        llm_status = f"error: {str(e)}"
        llm_type = "unknown"

    # We don't force fetching tools here (avoid long health checks)
    mcp_status = "configured" if MCP_SERVER_URL else "not_configured"

    return {
        "status": "ok",
        "service": "fastapi-agent",
        "llm": {"status": llm_status, "type": llm_type, "choice": LLM_CHOICE},
        "mcp": {"status": mcp_status, "url": MCP_SERVER_URL},
    }


# -----------------------------
# Agent endpoint
# -----------------------------
@app.post("/agent", response_model=AgentResponse)
async def run_agent(req: AgentRequest):
    logger.info("=" * 50)
    logger.info("NEW AGENT REQUEST")
    logger.info("=" * 50)
    logger.info(f"Request payload: {req.dict()}")
    logger.info(f"LLM Choice: {LLM_CHOICE}")
    logger.info(f"MCP Server URL: {MCP_SERVER_URL}")

    try:
        # Build LLM
        logger.info("Building LLM...")
        llm = build_llm()
        logger.info(f"LLM built successfully: {type(llm).__name__}")
        if hasattr(llm, "model"):
            logger.info(f"Model: {getattr(llm, 'model', '')}")

        # Fetch (cached) tools from MCP server; raise on failure
        logger.info("Fetching MCP tools (cached)...")
        mcp_tools = await get_mcp_tools_cached()
        logger.info(f"MCP tools available: {len(mcp_tools)}")

        # Build the agent workflow
        logger.info("Building agent workflow...")
        agent = AgentWorkflow.from_tools_or_functions(
            mcp_tools,
            llm=llm,
            system_prompt=req.instructions,
            verbose=False,
        )
        logger.info("Agent workflow built successfully")

        # Nudge the model to keep tool JSON clean
        enhanced_prompt = (
            f"{req.prompt}\n"
            "IMPORTANT: When calling tools, ensure all JSON parameters are properly formatted. "
            "Avoid long free-form text inside parameters; keep values concise and valid JSON."
        )
        logger.info(f"Enhanced prompt: {enhanced_prompt}")

        logger.info("Starting agent execution...")
        result = await agent.run(enhanced_prompt)
        logger.info("Agent execution completed")

        # Extract text from AgentOutput -> ChatMessage -> TextBlock
        text = "No output generated"
        if hasattr(result, "response") and hasattr(result.response, "blocks"):
            logger.info(f"Found response with {len(result.response.blocks)} blocks")
            for i, block in enumerate(result.response.blocks):
                if hasattr(block, "text") and block.text:
                    text = block.text
                    logger.info(
                        f"Extracted text from block {i}: {text[:200]}{'...' if len(text) > 200 else ''}"
                    )
                    break
        else:
            logger.warning("No response blocks found, using fallback")

        response_data = {"output": text, "debug": {"repr": repr(result)}}

        logger.info("=" * 50)
        logger.info("AGENT RESPONSE SUCCESS")
        logger.info("=" * 50)
        logger.info(f"Response output length: {len(text)} characters")
        logger.info(f"Response preview: {text[:200]}{'...' if len(text) > 200 else ''}")

        return response_data

    except Exception as e:
        logger.error("=" * 50)
        logger.error("AGENT REQUEST FAILED")
        logger.error("=" * 50)
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}", exc_info=True)

        # Friendly message for common tool-call JSON issues
        if "error parsing tool call" in str(e):
            return {
                "output": (
                    "I encountered an issue with tool formatting. "
                    "Please try a simpler request or rephrase your question."
                ),
                "debug": {"error": str(e)},
            }

        # If MCP cache failed to initialize, surface a 503 so callers understand it's transient
        if isinstance(e, RuntimeError) and ("MCP" in str(e) or "tools" in str(e)):
            raise HTTPException(status_code=503, detail=f"service warming up: {e}")

        raise HTTPException(status_code=500, detail=f"agent error: {e}")