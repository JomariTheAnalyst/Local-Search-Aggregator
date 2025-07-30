from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn
import logging
from routes import router
from config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LocalAssistant")

app = FastAPI(title="Local AI Search Assistant API")

# Add CORS middleware with proper configuration for EventSource
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Type", "X-Requested-With"],
)

# Include router
app.include_router(router)

# Add a simple root endpoint
@app.get("/")
async def root():
    return {"message": "Local AI Search Assistant API is running"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    ) 