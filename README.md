# AI Search Assistant

A modern web application that combines web search with local LLM processing to provide intelligent, sourced answers to user queries.

## Features

- **AI-Powered Search**: Searches the web for relevant information and summarizes it using a local LLM
- **Modern UI**: Clean, ChatGPT-like interface with dark theme
- **Real-time Streaming**: Responses stream in real-time as they're generated
- **Source Attribution**: View and explore the sources used to generate answers

## Architecture

- **Frontend**: React with TypeScript, styled-components
- **Backend**: FastAPI (Python)
- **Search Provider**: Serper.dev Google Search API
- **LLM**: Local Ollama instance (default: llama3:8b)

## Setup

### Prerequisites

- Node.js 16+ and npm
- Python 3.8+
- Ollama with llama3:8b model installed
- Serper.dev API key

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```
   cp .env.example .env
   ```
   Edit the `.env` file with your Serper.dev API key and Ollama settings

5. Run the backend server:
   ```
   python run.py
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Start the development server:
   ```
   npm start
   ```

4. Access the application at `http://localhost:3000`

## Usage

1. Enter your question in the input field at the bottom of the screen
2. The system will search the web for relevant information
3. Results will be processed by the local LLM to generate a comprehensive answer
4. Sources are provided with each answer for reference

## API Endpoints

- `GET /health`: Health check endpoint
- `POST /unified`: Main endpoint for search and answer generation

## License

MIT 