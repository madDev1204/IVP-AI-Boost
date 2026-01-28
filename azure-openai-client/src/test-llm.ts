import OpenAI from "openai";
import * as dotenv from "dotenv";
import * as path from "node:path";

dotenv.config({ path: path.join(__dirname, "..", ".env") });

const AZURE_OPENAI_API_KEY = process.env.AZURE_OPENAI_API_KEY || "";
const AZURE_OPENAI_ENDPOINT = process.env.AZURE_OPENAI_ENDPOINT || "";
const AZURE_OPENAI_MODEL = process.env.AZURE_OPENAI_MODEL || "";

async function testLLM() {
    console.log("Testing LLM Connectivity...");
    console.log(`Endpoint: ${AZURE_OPENAI_ENDPOINT}`);
    console.log(`Model: ${AZURE_OPENAI_MODEL}`);
    console.log(`API Key: ${AZURE_OPENAI_API_KEY.substring(0, 5)}...`);

    // Try both with and without /v1 suffix if it's a proxy
    const endpointsToTry = [
        AZURE_OPENAI_ENDPOINT,
        AZURE_OPENAI_ENDPOINT.endsWith('/') ? AZURE_OPENAI_ENDPOINT + 'v1' : AZURE_OPENAI_ENDPOINT + '/v1'
    ];

    for (const url of endpointsToTry) {
        console.log(`\n--- Attempting with baseURL: ${url} ---`);
        const openai = new OpenAI({
            apiKey: AZURE_OPENAI_API_KEY,
            baseURL: url,
            defaultHeaders: {
                "api-key": AZURE_OPENAI_API_KEY,
            }
        });

        try {
            const response = await openai.chat.completions.create({
                model: AZURE_OPENAI_MODEL,
                messages: [{ role: "user", content: "Say hello" }],
                max_tokens: 10
            });
            console.log("SUCCESS!");
            console.log("AI Response:", response.choices[0].message.content);
            return;
        } catch (error: any) {
            console.error(`FAILED: ${error.message}`);
            if (error.response) {
                console.error("Status:", error.status);
                console.error("Data:", error.data);
            }
        }
    }
}

testLLM();
