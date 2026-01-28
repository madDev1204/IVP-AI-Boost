export interface Request {
    prompt: string;
    maxTokens?: number;
    temperature?: number;
    question: string;
}

export interface Response {
    id: string;
    object: string;
    created: number;
    choices: Array<{
        text: string;
        index: number;
        logprobs?: any;
        finish_reason: string;
    }>;
}