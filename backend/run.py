import uvicorn
from config import settings

if __name__ == "__main__":
    print("Starting Local AI Search Assistant API...")
    print(f"API will be available at http://{settings.HOST}:{settings.PORT}")
    print("Documentation available at http://localhost:8000/docs")
    print(f"Using Ollama model: {settings.OLLAMA_MODEL}")
    print(f"Using Serper API key: {settings.SERPER_API_KEY[:5]}...{settings.SERPER_API_KEY[-5:]}")
    
    # Run the server with increased timeout for long-running requests
    uvicorn.run(
        "main:app", 
        host=settings.HOST, 
        port=settings.PORT, 
        reload=settings.DEBUG,
        timeout_keep_alive=120,
        log_level="info"
    ) 