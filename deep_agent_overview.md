# 🧠 Deep Agent — Architecture Overview

## 🔍 What It Really Is

Despite the name **“Deep Agent”** in the code, this is **not a special LangGraph or LangChain agent type**.  
The name appears only once:

```python
mcp = FastMCP("Deep Agent Server")
```

That line simply names the **FastMCP server instance** — it’s a **label**, not a technical designation.

---

## ⚙️ Actual Agent Type

This project implements a:

> **LangGraph-based, tool-using, multi-step reasoning agent**  
> exposed as a **FastMCP (Model Context Protocol) server**.

---

## 🧩 Core Components

| Layer | Technology | Role |
|-------|-------------|------|
| **LLM Backbone** | `ChatOpenAI` / `AzureChatOpenAI` | Performs reasoning and tool selection |
| **Orchestration** | `LangGraph` | Controls the flow between reasoning and tool calls |
| **Tools** | `StructuredTool` from LangChain | Wraps `FogBugzClient` API methods |
| **Interface** | `FastMCP` | Exposes the agent over SSE as an MCP service |
| **Data Source** | `FogBugzClient` | Provides wiki and article data from FogBugz |

---

## 🧠 Reasoning Loop

The agent uses a **LangGraph StateGraph** with two main nodes:

```text
[agent] → [tools] → [agent] → END
```

1. **agent node** — calls the LLM (`llm_with_tools.ainvoke`)
2. **tools node** — executes any tool calls (`StructuredTool.ainvoke`)
3. **conditional edge** — if tool calls exist → go to `tools`; else → `END`

This creates a **multi-turn reasoning process**, allowing the LLM to:
- Think
- Act (invoke a FogBugz tool)
- Observe (receive tool output)
- Reflect (produce the final answer)

---

## 🧰 Available Tools

Each tool wraps a `FogBugzClient` method:

| Tool Name | Description |
|------------|--------------|
| `list_wikis` | Lists all active FogBugz wiki spaces |
| `list_articles` | Lists articles within a wiki |
| `search_articles` | Searches articles by keyword |
| `view_article` | Retrieves the full content of an article |

These are available both:
- To the **LLM agent** via `StructuredTool`, and  
- As **direct FastMCP endpoints** for legacy/fast access.

---

## 🔗 MCP Server Layer

The FastMCP server wraps the agent into a **Model Context Protocol** service with:

- `ask_agent(query: str)` — full reasoning + tool invocation
- Direct tools (`search_articles`, `view_article`, `list_wikis`, `list_articles`)

It runs as a streaming SSE server:

```bash
Starting Deep Agent MCP Server on port 8000...
```

---

## 🧭 Verification

You can confirm the real components at runtime:

```python
print(type(app))  # → langgraph.graph.compiled.CompiledGraph
print(type(llm))  # → ChatOpenAI or AzureChatOpenAI
print(type(mcp))  # → fastmcp.core.FastMCP
```

---

## ✅ Summary

| Term | Meaning |
|------|----------|
| **“Deep Agent”** | Just a project/server name |
| **Actual Type** | LangGraph-based, LangChain tool-using, LLM-driven MCP agent |
| **Primary Function** | Query and reason over FogBugz wiki data |
| **Behavior** | Multi-step reasoning loop with tool execution and streaming responses |
