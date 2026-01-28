# Azure OpenAI Client

This project provides a simple client for interacting with the Azure OpenAI service. It allows you to send questions to the Azure OpenAI API and receive responses.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [API](#api)
- [Contributing](#contributing)
- [License](#license)

## Installation

To install the necessary dependencies, run the following command:

```
npm install
```

## Usage

To use the Azure OpenAI client, you need to initialize it with your Azure OpenAI API key. Here’s a quick example:

```typescript
import { AzureOpenAIClient } from './src/client';

const client = new AzureOpenAIClient();
client.setApiKey('YOUR_AZURE_OPENAI_API_KEY');

client.askQuestion('What is the capital of France?')
    .then(response => {
        console.log(response);
    })
    .catch(error => {
        console.error(error);
    });
```

## API

### AzureOpenAIClient

- `setApiKey(apiKey: string)`: Sets the API key for the Azure OpenAI service.
- `askQuestion(question: string)`: Sends a question to the Azure OpenAI service and returns the response.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.