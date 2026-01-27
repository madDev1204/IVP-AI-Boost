import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";
import * as readline from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import OpenAI from "openai";
import * as dotenv from "dotenv";
import * as path from "node:path";

// Load environment variables from the same directory
dotenv.config({ path: path.join(__dirname, "..", ".env") });

const AZURE_OPENAI_API_KEY = process.env.AZURE_OPENAI_API_KEY || "";
const AZURE_OPENAI_ENDPOINT = process.env.AZURE_OPENAI_ENDPOINT || "";
const AZURE_OPENAI_MODEL = process.env.AZURE_OPENAI_MODEL || "gpt-4.1";

class AzureOpenAIClient {
    private openai: OpenAI;

    constructor() {
        console.log(`\n--- AI CONNECTION CHECK ---`);
        console.log(`Endpoint: ${AZURE_OPENAI_ENDPOINT}`);
        console.log(`Model: ${AZURE_OPENAI_MODEL}`);
        console.log(`Key: ${AZURE_OPENAI_API_KEY.substring(0, 5)}...`);

        // Many local proxies require standard headers.
        this.openai = new OpenAI({
            apiKey: AZURE_OPENAI_API_KEY,
            baseURL: AZURE_OPENAI_ENDPOINT,
            maxRetries: 2,
            timeout: 30000, // 30 seconds
            defaultHeaders: {
                "api-key": AZURE_OPENAI_API_KEY,
            }
        });
    }

    async askWithContext(question: string, context: string): Promise<string> {
        if (!context || context.trim().length === 0) {
            return "Note: No relevant documentation was found in FogBugz for this question. The AI answer below is based on general knowledge.\n\n---";
        }

        console.log(`Sending request to AI (${context.length} characters of context)...`);

        const messages: any[] = [
            { role: "system", content: "You are a helpful assistant for IVP (Indus Valley Partners). Answer based on the provided FogBugz context." },
            { role: "user", content: `Context: ${context}\n\nQuestion: ${question}` }
        ];

        try {
            const response = await this.openai.chat.completions.create({
                model: AZURE_OPENAI_MODEL,
                messages: messages,
                temperature: 0.1,
            });

            return response.choices[0]?.message?.content || "AI returned an empty response.";
        } catch (error: any) {
            console.error("\n[AI CONNECTION ERROR]");
            console.error(`- Error: ${error.message}`);
            if (error.status) console.error(`- Status: ${error.status}`);

            if (error.message.includes("404") || error.message.includes("not found")) {
                return `AI Error: The endpoint was not found (404). Check if '${AZURE_OPENAI_ENDPOINT}' should have '/v1' at the end.`;
            }
            if (error.message.includes("401")) {
                return "AI Error: Unauthorized (401). Check your API key.";
            }

            return `AI Error: ${error.message}`;
        }
    }
}



async function runClient() {
    const rl = readline.createInterface({ input, output });
    const aiClient = new AzureOpenAIClient();

    console.log("Connecting to FogBugz MCP server via SSE...");
    const transport = new SSEClientTransport(new URL("http://localhost:8000/sse"));
    const mcpClient = new Client(
        {
            name: "fogbugz-client",
            version: "1.0.0",
        },
        {
            capabilities: {},
        }
    );

    try {
        await mcpClient.connect(transport);
        console.log("Connected to FogBugz MCP server!");

        // Initial sanity check
        try {
            await mcpClient.callTool({ name: "ping" });
            console.log("MCP Tool communication verified.");
        } catch (e) {
            console.warn("MCP Tool communication warning (ping failed).");
        }

        while (true) {
            const question = await rl.question("\nAsk a question about IVP/FogBugz (or 'exit'): ");

            if (question.toLowerCase() === "exit") {
                break;
            }

            console.log(`\n1. Searching for documentation relevant to: "${question}"...`);
            console.log("   (Note: The first search may take ~1 minute to index 69 wikis. Please check the SERVER terminal for progress.)");

            try {
                // INCREASED TIMEOUT to 3 minutes for initial indexing
                const searchResult: any = await mcpClient.callTool(
                    { name: "search_articles", arguments: { query: question } },
                    undefined,
                    { timeout: 180000 }
                );

                if (!searchResult.content || searchResult.content.length === 0) {
                    console.log("DEBUG: Server returned no content block for search.");
                    console.log("No relevant documentation found.");
                    continue;
                }

                let articles;
                try {
                    const rawText = searchResult.content[0].text;
                    articles = JSON.parse(rawText);
                    // console.log(`DEBUG: Successfully parsed ${articles.length} articles from search results.`); // Removed as per instruction
                } catch (parseError) {
                    console.error("DEBUG: Failed to parse search result text as JSON.");
                    continue;
                }

                if (articles.length === 0) {
                    console.log("No relevant documentation found.");
                    continue;
                }

                console.log(`Found ${articles.length} relevant article(s). Generating answer...`);

                let combinedContext = "";
                const topArticles = articles.slice(0, 3);

                for (const art of topArticles) {
                    console.log(`   - Reading: ${art.title}...`);
                    const viewResult: any = await mcpClient.callTool({
                        name: "view_article",
                        arguments: { article_id: art.article_id },
                    });

                    try {
                        const articleData = JSON.parse(viewResult.content[0].text);
                        combinedContext += `\n--- ARTICLE: ${art.title} ---\n${articleData.content || ""}\n`;
                        // console.log(`     [Done] Retrieved ${contentSnippet.length} characters.`); // Removed as per instruction
                    } catch (e) {
                        const fallbackText = viewResult.content[0].text;
                        combinedContext += `\n--- ARTICLE: ${art.title} ---\n${fallbackText}\n`;
                        // console.log(`     [Done] Retrieved ${fallbackText.length} characters (unparsed).`); // Removed as per instruction
                    }
                }

                console.log(`2. Sending context to AI at ${AZURE_OPENAI_ENDPOINT}...`);
                const answer = await aiClient.askWithContext(question, combinedContext);

                console.log("\n==================== AI RESPONSE ====================");
                console.log(answer);
                console.log("====================================================\n");

            } catch (toolError: any) {
                if (toolError.message.includes("timeout")) {
                    console.error("\nERROR: Search timed out. Initial indexing of 69 wikis is very slow.");
                    console.error("Please ensure the SERVER terminal completes its scan before trying again.");
                } else {
                    console.error("ERROR during processing loop:", toolError.message);
                }
            }
        }


    } catch (error: any) {
        console.error("Error connecting to MCP server:", error.message);
    } finally {
        rl.close();
    }
}

runClient();