import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import * as readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import * as dotenv from "dotenv";
import * as path from "node:path";

// Load environment variables
dotenv.config({ path: path.join(__dirname, "..", ".env") });

async function runClient() {
    const rl = readline.createInterface({ input, output });

    console.log("\n--- Deep Agent MCP Client ---");
    console.log("Connecting to Deep Agent MCP server via SSE...");

    // Connect to the server (Deep Agent running on port 8000)
    const transport = new SSEClientTransport(new URL("http://localhost:8000/sse"));
    const mcpClient = new Client(
        {
            name: "deep-agent-client",
            version: "1.0.0",
        },
        {
            capabilities: {},
        }
    );

    try {
        await mcpClient.connect(transport);
        console.log("Connected to Deep Agent MCP server!");

        // List tools to verify connection and capability
        const toolsResult = await mcpClient.listTools();
        const tools = toolsResult.tools.map(t => t.name);
        console.log(`Available Tools: ${tools.join(", ")}`);

        if (!tools.includes("ask_agent")) {
            console.warn("WARNING: 'ask_agent' tool not found. Ensure you are running the Deep Agent server.");
        }

        while (true) {
            const question = await rl.question("\nAsk Deep Agent (or 'exit'): ");

            if (question.toLowerCase() === "exit") {
                break;
            }

            console.log(`\nProcessing query: "${question}"...`);

            try {
                // Determine which tool to use. If 'ask_agent' is available, use it.
                // Otherwise fall back to search_articles (legacy), though we really want ask_agent.

                if (tools.includes("ask_agent")) {
                    const result: any = await mcpClient.callTool(
                        {
                            name: "ask_agent",
                            arguments: { query: question }
                        },
                        undefined,
                        { timeout: 300000 } // 5 minute timeout for deep reasoning
                    );

                    if (result.content && result.content[0]) {
                        console.log("\n==================== AGENT RESPONSE ====================");
                        console.log(result.content[0].text);
                        console.log("========================================================\n");
                    } else {
                        console.log("No response content from agent.");
                    }

                } else {
                    console.error("Deep Agent tool not available.");
                }

            } catch (toolError: any) {
                console.error("Error asking agent:", toolError.message);
            }
        }


    } catch (error: any) {
        console.error("Error connecting to MCP server:", error.message);
        console.error("Make sure 'run_mcp_langgraph.py' is running!");
    } finally {
        rl.close();
    }
}

runClient();