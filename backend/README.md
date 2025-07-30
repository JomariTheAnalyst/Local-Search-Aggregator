# Local AI Search Assistant

A FastAPI backend that integrates with Serper.dev for web search and a local LLM (via Ollama) to generate answers.

## Features

- `/search` endpoint for querying Serper.dev
- `/generate` endpoint for generating answers using a local LLM
- `/search-and-generate` combined endpoint for a one-step search and answer
- CORS middleware for frontend integration
- Swagger UI documentation at `/docs`

## Requirements

- Python 3.8+
- Serper.dev API key
- Ollama with llama3:8b model installed

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd <repository-directory>
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file and update it with your API keys:

```bash
cp .env.example .env
# Edit .env with your Serper.dev API key
```

## Running the API

```bash
uvicorn main:app --reload
```

The API will be available at http://localhost:8000.

## API Documentation

Visit http://localhost:8000/docs for the Swagger UI documentation.

## API Endpoints

### GET /

Root endpoint to verify the API is running.

### POST /search

Search endpoint that forwards queries to Serper.dev and returns results.

Request body:
```json
{
  "query": "your search query"
}
```

### POST /generate

Generate an answer using the local LLM based on search results.

Request body:
```json
{
  "query": "your search query",
  "search_results": {
    "searchParameters": { ... },
    "organic": [ ... ],
    "answerBox": { ... },
    "knowledgeGraph": { ... },
    "relatedSearches": [ ... ]
  }
}
```

### POST /search-and-generate

Combined endpoint that searches and generates an answer in one request.

Request body:
```json
{
  "query": "your search query"
}
```

Response:
```json
{
  "search_results": { ... },
  "answer": "Generated answer from LLM"
}
``` 