import os
import sys
import asyncio
import operator
from typing import TypedDict, Annotated, Sequence
import dotenv
from pydantic import BaseModel, Field
from fastmcp import FastMCP

# Check dependencies
try:
    from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage
    from langchain_core.tools import StructuredTool
    from langchain_openai import ChatOpenAI
    from langgraph.graph import StateGraph, END
    from fogbugz_mcp.app.fogbugz_client import FogBugzClient
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

# Load environment variables
dotenv.load_dotenv(os.path.join(os.getcwd(), "azure-openai-client", ".env"))
# Load from root (where the main keys seem to be)
dotenv.load_dotenv(os.path.join(os.getcwd(), ".env"))

# --- Initialize FogBugz Client ---
FOGBUGZ_URL = os.getenv("FOGBUGZ_URL")
FOGBUGZ_TOKEN = os.getenv("FOGBUGZ_TOKEN")

if not FOGBUGZ_URL or not FOGBUGZ_TOKEN:
    print("\nCRITICAL ERROR: FOGBUGZ_URL or FOGBUGZ_TOKEN is missing!")
    print(f"Current working dir: {os.getcwd()}")
    print("Checked paths for .env:")
    print(f" - {os.path.join(os.getcwd(), 'azure-openai-client', '.env')}")
    print(f" - {os.path.join(os.getcwd(), '.env')}")
    # Don't exit yet, let the code fail later if needed, but warn loudly
    
# Initialize the client directly (no more subprocess server)
fb_client = FogBugzClient(base_url=FOGBUGZ_URL or "", token=FOGBUGZ_TOKEN or "")

# --- Define LangChain Tools ---
# These tools wrap the underlying FogBugzClient methods

class ListWikisInput(BaseModel):
    pass

def list_wikis_tool():
    """List all active FogBugz wiki spaces."""
    return str(fb_client.list_wikis())

class ListArticlesInput(BaseModel):
    wiki_id: int = Field(..., description="The ID of the wiki to list articles from")

def list_articles_tool(wiki_id: int):
    """List articles within a specific wiki."""
    return str(fb_client.list_articles(wiki_id))

class SearchArticlesInput(BaseModel):
    query: str = Field(..., description="The search query")

def search_articles_tool(query: str):
    """Search for FogBugz articles by keyword."""
    return str(fb_client.search_articles(query))

class ViewArticleInput(BaseModel):
    article_id: int = Field(..., description="The ID of the article to view")

def view_article_tool(article_id: int):
    """Retrieve the full content of a FogBugz article."""
    return str(fb_client.view_article(article_id))

lc_tools = [
     StructuredTool.from_function(
        func=list_wikis_tool,
        name="list_wikis",
        description="List all active FogBugz wiki spaces.",
        args_schema=ListWikisInput
    ),
    StructuredTool.from_function(
        func=list_articles_tool,
        name="list_articles",
        description="List articles within a specific wiki.",
        args_schema=ListArticlesInput
    ),
    StructuredTool.from_function(
        func=search_articles_tool,
        name="search_articles",
        description="Search for FogBugz articles by keyword.",
        args_schema=SearchArticlesInput
    ),
    StructuredTool.from_function(
        func=view_article_tool,
        name="view_article",
        description="Retrieve the full content of a FogBugz article.",
        args_schema=ViewArticleInput
    )
]

# --- LLM Setup ---
api_key = os.environ.get("OPENAI_API_KEY")
azure_key = os.environ.get("AZURE_OPENAI_API_KEY")

if azure_key:
    from langchain_openai import AzureChatOpenAI
    llm = AzureChatOpenAI(
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=azure_key,
        azure_deployment=os.environ.get("AZURE_OPENAI_MODEL", "gpt-4"),
        api_version="2023-05-15",
        temperature=0
    )
else:
    try:
        llm = ChatOpenAI(model="gpt-4", temperature=0)
    except Exception:
        llm = None
        print("Warning: No LLM configuration found.")

if llm:
    llm_with_tools = llm.bind_tools(lc_tools)

# --- Agent Graph Definition ---
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

async def call_model(state: AgentState):
    if not llm:
        return {"messages": [BaseMessage(content="Error: processing not configured.", type="ai")]}
    response = await llm_with_tools.ainvoke(state["messages"])
    return {"messages": [response]}

async def call_tools(state: AgentState):
    last_message = state["messages"][-1]
    outputs = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        tool = next((t for t in lc_tools if t.name == tool_name), None)
        if tool:
            try:
                # StructuredTool handles sync/async
                res = await tool.ainvoke(tool_args)
                outputs.append(ToolMessage(content=str(res), tool_call_id=tool_id, name=tool_name))
            except Exception as e:
                outputs.append(ToolMessage(content=str(e), tool_call_id=tool_id, name=tool_name))
        else:
            outputs.append(ToolMessage(content=f"Tool {tool_name} not found", tool_call_id=tool_id, name=tool_name))
            
    return {"messages": outputs}

def should_continue(state: AgentState):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"
    return END

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tools", call_tools)

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

app = workflow.compile()

# --- FastMCP Server Setup ---
mcp = FastMCP("Deep Agent Server")

@mcp.tool()
async def ask_agent(query: str) -> str:
    """
    Ask the Deep Agent a question. The agent has access to all FogBugz documentation tools.
    """
    print(f"\n[Deep Agent Server] Received Query: {query}")
    
    final_response = "No response generated."
    
    # Run the graph
    inputs = {"messages": [HumanMessage(content=query)]}
    async for event in app.astream(inputs, stream_mode="values"):
        last_msg = event["messages"][-1]
        # Check if it is an AI message without tool calls -> final answer
        if hasattr(last_msg, 'tool_calls') and not last_msg.tool_calls and last_msg.type == 'ai':
            final_response = last_msg.content
            
    print(f"[Deep Agent Server] Final Response Preview: {final_response[:50]}...")
    return final_response

@mcp.tool()
def search_articles(query: str) -> str:
    """Direct search tool (legacy/fast)"""
    return str(fb_client.search_articles(query))

@mcp.tool()
def view_article(article_id: int) -> str:
    """Direct view tool (legacy/fast)"""
    return str(fb_client.view_article(article_id))

@mcp.tool()
def list_wikis() -> str:
    """Direct list wikis tool"""
    return str(fb_client.list_wikis())

@mcp.tool()
def list_articles(wiki_id: int) -> str:
    """Direct list articles tool"""
    return str(fb_client.list_articles(wiki_id))

if __name__ == "__main__":
    print("Starting Deep Agent MCP Server on port 8000...")
    # This runs the SSE server
    mcp.run(transport="sse")
