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

