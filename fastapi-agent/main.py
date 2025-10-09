import os
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

# Config via env - no defaults, everything from .env
LLM_CHOICE = os.getenv("LLM_CHOICE")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL")
OLLAMA_TIMEOUT = float(
    os.getenv("OLLAMA_TIMEOUT", "120.0")
)  # Keep this default for safety
LITELLM_MODEL = os.getenv("LITELLM_MODEL")
LITELLM_API_KEY = os.getenv("LITELLM_API_KEY")
LITELLM_API_BASE = os.getenv("LITELLM_API_BASE")

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL")

# Log startup configuration
logger.info("=" * 60)
logger.info("FASTAPI AGENT STARTING UP")
logger.info("=" * 60)
logger.info("Configuration:")
logger.info(f"  LLM_CHOICE: {LLM_CHOICE}")
logger.info(f"  OLLAMA_MODEL: {OLLAMA_MODEL}")
logger.info(f"  OLLAMA_BASE_URL: {OLLAMA_BASE_URL}")
logger.info(f"  OLLAMA_TIMEOUT: {OLLAMA_TIMEOUT}")
logger.info(f"  LITELLM_MODEL: {LITELLM_MODEL}")
logger.info(f"  LITELLM_API_BASE: {LITELLM_API_BASE}")
logger.info(
    f"  LITELLM_API_KEY: {'*' * (len(LITELLM_API_KEY) - 4) + LITELLM_API_KEY[-4:] if LITELLM_API_KEY else 'None'}"
)
logger.info(f"  MCP_SERVER_URL: {MCP_SERVER_URL}")
logger.info("=" * 60)

app = FastAPI(title="Agent with Ollama / LiteLLM + MCP Tools")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AgentRequest(BaseModel):
    instructions: Optional[str] = None
    prompt: str


class AgentResponse(BaseModel):
    output: str
    debug: Optional[Any] = None


@app.get("/")
async def health():
    return {"status": "ok", "service": "fastapi-agent"}


@app.get("/health")
async def detailed_health():
    """Detailed health check endpoint"""
    try:
        # Check if we can build LLM
        llm = build_llm()
        llm_status = "ok"
        llm_type = type(llm).__name__
    except Exception as e:
        llm_status = f"error: {str(e)}"
        llm_type = "unknown"

    # Check MCP connection
    try:
        if MCP_SERVER_URL:
            # Don't actually fetch tools in health check to avoid timeouts
            mcp_status = "configured"
        else:
            mcp_status = "not_configured"
    except Exception as e:
        mcp_status = f"error: {str(e)}"

    return {
        "status": "ok",
        "service": "fastapi-agent",
        "llm": {"status": llm_status, "type": llm_type, "choice": LLM_CHOICE},
        "mcp": {"status": mcp_status, "url": MCP_SERVER_URL},
    }


def build_llm():
    """
    Build the selected LLM instance.
    """
    logger.info(f"Building LLM with choice: {LLM_CHOICE}")

    if LLM_CHOICE.lower() == "ollama":
        logger.info("Configuring Ollama LLM:")
        logger.info(f"  Model: {OLLAMA_MODEL}")
        logger.info(f"  Base URL: {OLLAMA_BASE_URL}")
        logger.info(f"  Timeout: {OLLAMA_TIMEOUT}")

        # Ollama with configurable base URL for Docker/remote access
        llm = Ollama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            request_timeout=OLLAMA_TIMEOUT,
            # Add additional options for better JSON handling
            additional_kwargs={
                "temperature": 0.1,  # Lower temperature for more consistent output
                "top_p": 0.9,
            },
        )
        logger.info("Ollama LLM created successfully")

    elif LLM_CHOICE.lower() == "litellm":
        logger.info("Configuring LiteLLM:")
        logger.info(f"  Model: {LITELLM_MODEL}")
        logger.info(f"  API Base: {LITELLM_API_BASE}")
        logger.info(
            f"  API Key: {'*' * (len(LITELLM_API_KEY) - 4) + LITELLM_API_KEY[-4:] if LITELLM_API_KEY else 'None'}"
        )

        # LiteLLM with Hyland ML platform support
        llm = LiteLLM(
            model=LITELLM_MODEL,
            api_key=LITELLM_API_KEY,
            api_base=LITELLM_API_BASE,
            # Lower temperature for more consistent JSON generation
            temperature=0.1,
        )
        logger.info("LiteLLM created successfully")

    else:
        error_msg = f"Unsupported LLM_CHOICE: {LLM_CHOICE}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return llm


async def fetch_mcp_tools() -> List[Any]:
    """
    Fetch MCP tools from the MCP server and convert to LlamaIndex tools.
    """
    if MCP_SERVER_URL is None:
        logger.warning("MCP_SERVER_URL is None, returning empty tools list")
        return []

    logger.info(f"Attempting to fetch MCP tools from: {MCP_SERVER_URL}")

    try:
        # Create client
        client = BasicMCPClient(MCP_SERVER_URL)
        logger.info(f"Created MCP client: {type(client).__name__}")

        # Fetch tools
        tools = await aget_tools_from_mcp_url(
            MCP_SERVER_URL,
            client=client,
            allowed_tools=None,
        )

        logger.info(f"Successfully fetched {len(tools)} tools from MCP server")

        # Log details about each tool
        for i, tool in enumerate(tools):
            tool_info = {
                "index": i,
                "type": type(tool).__name__,
                "name": getattr(tool, "name", "unknown"),
                "description": getattr(tool, "description", "no description")[:100],
            }
            if hasattr(tool, "metadata"):
                tool_info.update(
                    {
                        "metadata_name": getattr(tool.metadata, "name", "unknown"),
                        "metadata_description": getattr(
                            tool.metadata, "description", "no description"
                        )[:100],
                    }
                )
            logger.info(f"Tool {i}: {tool_info}")

        return tools

    except Exception as e:
        logger.error(f"Error fetching MCP tools from {MCP_SERVER_URL}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.exception("MCP fetch error traceback:")
        return []


@app.post("/agent", response_model=AgentResponse)
async def run_agent(req: AgentRequest):
    # Log the incoming request
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
            logger.info(f"Model: {llm.model}")

        # Fetch tools from MCP server
        logger.info("Fetching MCP tools...")
        mcp_tools = await fetch_mcp_tools()
        logger.info(f"MCP tools fetched: {len(mcp_tools)} tools available")

        # Log tool names for debugging
        tool_names = []
        for tool in mcp_tools:
            if hasattr(tool, "metadata") and hasattr(tool.metadata, "name"):
                tool_names.append(tool.metadata.name)
            elif hasattr(tool, "name"):
                tool_names.append(tool.name)
        logger.info(f"Available tools: {tool_names}")

        # Build the agent with more conservative settings
        logger.info("Building agent workflow...")
        agent = AgentWorkflow.from_tools_or_functions(
            mcp_tools,
            llm=llm,
            system_prompt=req.instructions,
            verbose=False,
        )
        logger.info("Agent workflow built successfully")

        # Add specific instruction to be careful with JSON formatting
        enhanced_prompt = f"""
        {req.prompt}
        
        IMPORTANT: When calling tools, ensure all JSON parameters are properly formatted. 
        Avoid long text descriptions that might contain special characters.
        Keep tool parameters concise and well-formatted.
        """

        logger.info(f"Enhanced prompt: {enhanced_prompt}")
        logger.info("Starting agent execution...")

        result = await agent.run(enhanced_prompt)

        logger.info("Agent execution completed")
        logger.info(f"Result type: {type(result)}")
        logger.info(f"Result attributes: {dir(result)}")

        # Extract text from AgentOutput -> ChatMessage -> TextBlock
        text = "No output generated"

        if hasattr(result, "response") and hasattr(result.response, "blocks"):
            logger.info(f"Found response with {len(result.response.blocks)} blocks")
            for i, block in enumerate(result.response.blocks):
                logger.info(f"Block {i}: type={type(block)}, attributes={dir(block)}")
                if hasattr(block, "text"):
                    text = block.text
                    logger.info(
                        f"Extracted text from block {i}: {text[:200]}{'...' if len(text) > 200 else ''}"
                    )
                    break
        else:
            logger.warning("No response blocks found, using fallback")
            if hasattr(result, "response"):
                logger.info(f"Response type: {type(result.response)}")
                logger.info(f"Response content: {str(result.response)[:500]}")

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
        logger.error(f"Error message: {str(e)}")
        logger.exception("Full traceback:")

        # Check if it's a JSON parsing error from Ollama
        if "error parsing tool call" in str(e):
            error_response = {
                "output": "I encountered an issue with tool formatting. Please try a simpler request or rephrase your question.",
                "debug": {"error": str(e)},
            }
            logger.info("Returning user-friendly error for JSON parsing issue")
            logger.info(f"Error response: {error_response}")
            return error_response

        logger.error("Raising HTTP exception for unhandled error")
        raise HTTPException(status_code=500, detail=f"agent error: {e}")
