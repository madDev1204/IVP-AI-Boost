import os
from dotenv import load_dotenv
from fastmcp import FastMCP
from fogbugz_mcp.app.fogbugz_client import FogBugzClient

load_dotenv()

FOGBUGZ_URL = os.getenv("FOGBUGZ_URL")
FOGBUGZ_TOKEN = os.getenv("FOGBUGZ_TOKEN")

if not FOGBUGZ_URL or not FOGBUGZ_TOKEN:
    raise RuntimeError("FOGBUGZ_URL and FOGBUGZ_TOKEN must be set")

client = FogBugzClient(
    base_url=FOGBUGZ_URL,
    token=FOGBUGZ_TOKEN,
)

mcp = FastMCP(
    name="FogBugz Documentation MCP",
    instructions=(
        "This MCP server provides read-only access to IVP (Indus Valley Partners) Company's FogBugz wikis and articles. "
        "Use `list_wikis` to discover documentation spaces, `list_articles` to list articles "
        "in a wiki, and `view_article` to get detailed content for a specific article. "
        "Note: `view_article` requires `article_id` obtained from `list_articles`."
    ),
)

# -----------------------------
# Tools
# -----------------------------

@mcp.tool()
def list_wikis():
    """
    List all active FogBugz wiki spaces.
    Returns:
      - wiki_id
      - name
      - tagline
      - root_page_id
    """
    return client.list_wikis()


@mcp.tool()
def ping():
    """
    Simple connectivity test.
    """
    return "pong"


@mcp.tool()
def list_articles(wiki_id: int):

    """
    List articles within a specific wiki.
    
    Input:
      - wiki_id: integer (from list_wikis)
    
    Returns:
      - article_id (used for view_article)
      - article_description
      - wiki_page
    """
    return client.list_articles(wiki_id)


@mcp.tool()
def search_articles(query: str):
    """
    Search for FogBugz articles by keyword.
    
    Input:
      - query: string (search term)
    
    Returns:
      - article_id
      - title
    """
    return client.search_articles(query)


@mcp.tool()
def view_article(article_id: int):

    """
    Retrieve the full content of a FogBugz article.
    
    Input:
      - article_id: integer (from list_articles)
    
    Returns:
      - article_id
      - title
      - content
      - revision
      - tags
    """
    return client.view_article(article_id)


def main():
    # Run MCP server using SSE (HTTP) transport
    print("Starting FogBugz MCP server on http://localhost:8000")
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()


