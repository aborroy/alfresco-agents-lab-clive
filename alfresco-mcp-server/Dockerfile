# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/alfresco-mcp

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

# Clone the server source
RUN git clone --depth=1 https://github.com/stevereiner/python-alfresco-mcp-server.git .

# Copy your new tool into the source tree
COPY get_markdown_content.py ./alfresco_mcp_server/tools/core/get_markdown_content.py

# Patch fastmcp_server.py with the lab snippet
RUN sed -i '/# Core tools imports/a from .tools.core.get_markdown_content import get_markdown_content_impl' \
       ./alfresco_mcp_server/fastmcp_server.py \
 && sed -i '/# ================== CORE TOOLS ==================/a \
@mcp.tool\nasync def get_markdown_content(\n    node_id: str\n) -> str:\n    """Fetch the Markdown/Text rendition of an Alfresco node."""\n    return await get_markdown_content_impl(node_id)\n' \
       ./alfresco_mcp_server/fastmcp_server.py

# Install from source
RUN python -m pip install --upgrade pip \
 && pip install -e .

RUN useradd -u 10001 -m appuser
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV ALFRESCO_URL="http://localhost:8080" \
    ALFRESCO_USERNAME="admin" \
    ALFRESCO_PASSWORD="admin" \
    ALFRESCO_VERIFY_SSL="false" \
    LOG_LEVEL="INFO"

EXPOSE 8003

USER appuser
ENV TRANSPORT="http" HOST="0.0.0.0" PORT="8003"

ENTRYPOINT ["python", "run_server.py"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8003"]