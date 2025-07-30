import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

# Server Configuration
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DEBUG = os.environ.get("DEBUG", "True").lower() in ["true", "1", "t", "yes"]

# API Configuration
APP_TITLE = "Local AI Search Assistant"
APP_DESCRIPTION = "Backend API for search and LLM integration"
APP_VERSION = "0.1.0"

# CORS Configuration
CORS_ORIGINS = ["*"]

# Serper.dev API Configuration
SERPER_API_KEY = os.environ.get("SERPER_API_KEY", "bf7beacd05f11a1c047f055733fc7f86cd4bb2b2")
SERPER_API_URL = "https://google.serper.dev/search"

# Ollama Configuration
# Ensure no trailing slash and no API path
ollama_url = os.environ.get("OLLAMA_API_URL", "http://localhost:11434").rstrip('/')
# Remove /api/generate if it's in the URL
if ollama_url.endswith("/api/generate"):
    ollama_url = ollama_url.replace("/api/generate", "")
OLLAMA_API_URL = ollama_url
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3:8b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "180"))  # 3 minutes timeout
OLLAMA_MAX_TOKENS = int(os.environ.get("OLLAMA_MAX_TOKENS", "2048"))  # Maximum tokens to generate

# Create a settings class for compatibility
class Settings:
    HOST = HOST
    PORT = PORT
    DEBUG = DEBUG
    APP_TITLE = APP_TITLE
    APP_DESCRIPTION = APP_DESCRIPTION
    APP_VERSION = APP_VERSION
    CORS_ORIGINS = CORS_ORIGINS
    SERPER_API_KEY = SERPER_API_KEY
    SERPER_API_URL = SERPER_API_URL
    OLLAMA_API_URL = OLLAMA_API_URL
    OLLAMA_MODEL = OLLAMA_MODEL
    OLLAMA_TIMEOUT = OLLAMA_TIMEOUT
    OLLAMA_MAX_TOKENS = OLLAMA_MAX_TOKENS

# Create a global settings object
settings = Settings() 