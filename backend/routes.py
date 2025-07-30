from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends, Query
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, List, AsyncGenerator, Optional, Callable
import httpx
import json
import asyncio
from datetime import datetime
import uuid
import time
import logging
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import traceback
import asyncio
import functools

from models import SearchQuery, LLMRequest, SearchResult, HealthCheckResponse, APIError, LLMResponse
from services.search_service import search_serper
from services.llm_service import generate_answer, generate_answer_streaming
from config import settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("LocalAssistant")

# Create router
router = APIRouter()

# In-memory cache for search results
# Using a dict with query_id as key and search results as value
search_cache = {}

# Active streams tracking
active_streams = {}

# Maximum iterations for LLM generation
MAX_LLM_ITERATIONS = 150  # Increased from 30 to 150

class StreamRequest(BaseModel):
    """Model for stream requests combining search and generation."""
    query: str
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = "en"
    max_search_results: Optional[int] = 5
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048  # Increased from 1024 to 2048
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 40
    timeout: Optional[int] = 180  # 3 minutes timeout

@router.get("/")
async def root():
    """Root endpoint to verify the API is running."""
    return {"status": "online", "message": "Local AI Search Assistant API is running"}

@router.get("/health")
async def health_check():
    """
    Health check endpoint to verify all services are working.
    Tests the connectivity to Ollama LLM API and Serper.dev search API.
    """
    logger.info("Health check requested")
    request_id = str(uuid.uuid4())
    logger.info(f"Health check request_id: {request_id}")
    
    start_time = time.time()
    services = {}
    overall_status = "healthy"
    
    # Check Ollama API
    try:
        logger.info(f"[{request_id}] Checking Ollama API")
        api_url = settings.OLLAMA_API_URL
        if not api_url.endswith("/api/tags"):
            api_url = f"{api_url}/api/tags"
            
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(api_url)
            response.raise_for_status()
            
            # Check if the model is available
            models = response.json().get("models", [])
            model_available = any(m.get("name") == settings.OLLAMA_MODEL for m in models)
            
            services["ollama"] = {
                "status": "healthy" if model_available else "degraded",
                "detail": f"Model {settings.OLLAMA_MODEL} {'found' if model_available else 'not found'}",
                "latency_ms": int((time.time() - start_time) * 1000)
            }
            
            if not model_available:
                overall_status = "degraded"
                logger.warning(f"[{request_id}] Ollama model {settings.OLLAMA_MODEL} not found")
    except Exception as e:
        logger.error(f"[{request_id}] Ollama API check failed: {str(e)}")
        services["ollama"] = {
            "status": "unhealthy",
            "detail": f"Error: {str(e)}",
            "latency_ms": int((time.time() - start_time) * 1000)
        }
        overall_status = "unhealthy"
    
    # Check Serper.dev API
    search_start_time = time.time()
    try:
        logger.info(f"[{request_id}] Checking Serper.dev API")
        headers = {
            "X-API-KEY": settings.SERPER_API_KEY,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                settings.SERPER_API_URL,
                headers=headers,
                json={"q": "test", "gl": "us", "hl": "en"}
            )
            response.raise_for_status()
            
            services["search_api"] = {
                "status": "healthy",
                "detail": "Serper.dev API is responsive",
                "latency_ms": int((time.time() - search_start_time) * 1000)
            }
    except Exception as e:
        logger.error(f"[{request_id}] Serper.dev API check failed: {str(e)}")
        services["search_api"] = {
            "status": "unhealthy",
            "detail": f"Error: {str(e)}",
            "latency_ms": int((time.time() - search_start_time) * 1000)
        }
        overall_status = "unhealthy"
    
    # Add cache status
    services["cache"] = {
        "status": "healthy",
        "detail": f"{len(search_cache)} items in cache",
        "latency_ms": 0
    }
    
    response = HealthCheckResponse(
        status=overall_status,
        services=services,
        timestamp=datetime.now().isoformat()
    )
    
    logger.info(f"[{request_id}] Health check completed with status: {overall_status}")
    return response

# Cleanup task to remove old entries from active_streams
async def cleanup_active_streams():
    """
    Clean up active streams that are too old.
    """
    while True:
        try:
            await asyncio.sleep(60)  # Run every minute
            now = time.time()
            keys_to_remove = []
            
            for request_id, stream_data in active_streams.items():
                # Remove streams older than 15 minutes
                if now - stream_data["start_time"] > 15 * 60:
                    keys_to_remove.append(request_id)
            
            for key in keys_to_remove:
                del active_streams[key]
                
            logger.info(f"Cleaned up {len(keys_to_remove)} old streams. Active streams: {len(active_streams)}")
        except Exception as e:
            logger.error(f"Error in cleanup_active_streams: {str(e)}")

@router.on_event("startup")
async def setup_cleanup():
    """Set up background task to clean up active streams."""
    asyncio.create_task(cleanup_active_streams())

@router.options("/unified")
async def options_unified():
    """
    Handle OPTIONS request for CORS preflight for the unified endpoint.
    """
    return {
        "allow": "GET, POST, OPTIONS",
        "content": "text/event-stream"
    }

@router.get("/unified")
@router.post("/unified")
async def unified_endpoint(request: Request, stream_request: StreamRequest = None, background_tasks: BackgroundTasks = None):
    """
    Unified endpoint that handles the complete flow in one request:
    1. Search the web
    2. Stream search results to the client
    3. Generate LLM summary based on search results
    4. Stream the LLM response to the client
    
    All in a single SSE stream.
    
    Can be called either with:
    - GET request with query parameters
    - POST request with JSON body
    """
    # If no StreamRequest was provided, try to get parameters from query
    if stream_request is None:
        query_params = request.query_params
        query = query_params.get("query")
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")
            
        # Create a StreamRequest from query parameters
        stream_request = StreamRequest(
            query=query,
            request_id=query_params.get("request_id", str(uuid.uuid4())),
            session_id=query_params.get("session_id"),
            model=query_params.get("model"),
            language=query_params.get("language", "en"),
            max_search_results=int(query_params.get("max_search_results", 5)),
            temperature=float(query_params.get("temperature", 0.7)),
            max_tokens=int(query_params.get("max_tokens", 4096)),
            top_p=float(query_params.get("top_p", 0.9)),
            top_k=int(query_params.get("top_k", 40)),
            timeout=int(query_params.get("timeout", 300))
        )
    
    # If no background_tasks was provided, create one
    if background_tasks is None:
        background_tasks = BackgroundTasks()
    
    request_id = stream_request.request_id or str(uuid.uuid4())
    session_id = stream_request.session_id or request_id
    
    # Track the stream
    active_streams[request_id] = {
        "start_time": time.time(),
        "session_id": session_id,
        "query": stream_request.query,
        "disconnected": False
    }
    
    logger.info(f"[{request_id}] Unified endpoint called with query: {stream_request.query}")
    
    # Add a background task to clean up this stream when done
    background_tasks.add_task(lambda: active_streams.pop(request_id, None))
    
    async def generate_unified_stream():
        """Generate the unified SSE stream with search results and LLM response."""
        
        # Helper function to format SSE messages
        def format_sse(event_type: str, data: Any, metadata: Dict[str, Any] = None) -> str:
            message = {
                "type": event_type,
                "data": data,
                "request_id": request_id,
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }
            
            if metadata:
                message["metadata"] = metadata
                
            return f"data: {json.dumps(message)}\n\n"
        
        try:
            # 1. Initial status message
            yield format_sse("status", "Processing query", {"step": "init"})
            
            # Helper function to check if client disconnected
            def is_disconnected():
                return request_id in active_streams and active_streams[request_id].get("disconnected", False)
            
            # 2. Search phase
            yield format_sse("status", "Searching the web...", {"step": "search_start"})
            search_start = time.time()
            
            try:
                # Perform the search
                search_results = await search_serper(stream_request.query, timeout=30.0)
                search_time = time.time() - search_start
                
                if is_disconnected():
                    logger.info(f"[{request_id}] Client disconnected during search")
                    return
                
                # Log search completion
                organic_count = len(search_results.get('organic', []))
                logger.info(f"[{request_id}] Search completed in {search_time:.2f}s with {organic_count} results")
                
                # Stream search status
                yield format_sse("status", "Search completed", {
                    "step": "search_complete",
                    "time_taken": search_time,
                    "result_count": organic_count
                })
                
                # Stream search results (limited to max_search_results)
                if search_results.get('organic'):
                    max_results = min(stream_request.max_search_results, len(search_results['organic']))
                    
                    for idx, result in enumerate(search_results['organic'][:max_results]):
                        if is_disconnected():
                            return
                            
                        yield format_sse("search_result", result, {
                            "position": idx + 1,
                            "total": max_results
                        })
                        
                        # Small delay between results for UI rendering
                        await asyncio.sleep(0.05)
                
            except Exception as e:
                logger.error(f"[{request_id}] Search error: {str(e)}")
                yield format_sse("error", f"Search error: {str(e)}", {
                    "step": "search_error",
                    "error_type": type(e).__name__
                })
                
                # Use empty results as fallback
                search_results = {"organic": []}
            
            # 3. LLM generation phase
            if is_disconnected():
                return
                
            yield format_sse("status", "Generating answer...", {"step": "generation_start"})
            generation_start = time.time()
            
            try:
                # Prepare LLM parameters
                llm_params = {
                    "temperature": stream_request.temperature,
                    "max_tokens": stream_request.max_tokens,
                    "top_p": stream_request.top_p,
                    "top_k": stream_request.top_k
                }
                
                # Stream LLM generation
                total_tokens = 0
                chunk_count = 0
                has_content = False
                
                # Generate answer with search results
                async for chunk in generate_answer_streaming(
                    stream_request.query,
                    search_results,
                    max_iterations=MAX_LLM_ITERATIONS,
                    timeout=stream_request.timeout
                ):
                    if is_disconnected():
                        logger.info(f"[{request_id}] Client disconnected during generation")
                        return
                    
                    if chunk:
                        has_content = True
                        chunk_count += 1
                        total_tokens += len(chunk.split())
                        
                        yield format_sse("answer_chunk", chunk, {
                            "step": "generation_chunk",
                            "chunk_id": chunk_count,
                            "tokens": len(chunk.split())
                        })
                        
                        # Add a small delay between chunks to prevent overwhelming the client
                        await asyncio.sleep(0.01)
                
                # If no content was generated, provide a fallback
                if not has_content:
                    fallback = "I couldn't generate a specific answer based on the search results. Please try rephrasing your question."
                    yield format_sse("answer_chunk", fallback, {"step": "fallback"})
                
                # Generation complete
                generation_time = time.time() - generation_start
                logger.info(f"[{request_id}] Generation completed in {generation_time:.2f}s, {total_tokens} tokens, {chunk_count} chunks")
                
                yield format_sse("status", "Generation completed successfully", {
                    "step": "generation_complete",
                    "time_taken": generation_time,
                    "total_tokens": total_tokens,
                    "chunk_count": chunk_count,
                    "is_complete": True
                })
                
            except Exception as e:
                logger.error(f"[{request_id}] Generation error: {str(e)}")
                logger.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
                
                yield format_sse("error", f"Generation error: {str(e)}", {
                    "step": "generation_error",
                    "error_type": type(e).__name__
                })
                
                # Provide a fallback response
                fallback = "I apologize, but I encountered an error while generating your answer. Please try again."
                yield format_sse("answer_chunk", fallback, {"step": "fallback"})
            
            # 4. Complete the stream
            total_time = time.time() - search_start
            yield format_sse("status", "Request completed", {
                "step": "complete",
                "total_time": total_time
            })
            
            # End of stream marker
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"[{request_id}] Unhandled exception in unified stream: {str(e)}")
            logger.error(f"[{request_id}] Traceback: {traceback.format_exc()}")
            
            try:
                yield format_sse("error", f"Unhandled error: {str(e)}", {
                    "step": "fatal_error",
                    "error_type": type(e).__name__
                })
                yield "data: [DONE]\n\n"
            except:
                pass
    
    # Return the streaming response
    return StreamingResponse(
        generate_unified_stream(),
        media_type="text/event-stream",
        background=background_tasks,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, X-Requested-With",
            "X-Accel-Buffering": "no"  # Disable buffering for Nginx if used
        }
    )

# Cleanup task to remove old entries from the cache
@router.on_event("startup")
async def setup_cache_cleanup():
    """Set up background task to clean up the search cache periodically."""
    async def cleanup_cache():
        while True:
            try:
                # Sleep for 30 minutes
                await asyncio.sleep(30 * 60)
                
                # Get current time
                now = datetime.now()
                
                # Remove entries older than 2 hours
                keys_to_remove = []
                for key, value in search_cache.items():
                    timestamp = datetime.fromisoformat(value["timestamp"])
                    if (now - timestamp).total_seconds() > 2 * 60 * 60:  # 2 hours in seconds
                        keys_to_remove.append(key)
                
                # Remove the old entries
                for key in keys_to_remove:
                    del search_cache[key]
                    
                logger.info(f"Cache cleanup: removed {len(keys_to_remove)} old entries")
            except Exception as e:
                logger.error(f"Error in cache cleanup: {str(e)}")
    
    # Start the background task
    asyncio.create_task(cleanup_cache()) 