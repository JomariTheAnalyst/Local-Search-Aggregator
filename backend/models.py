from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
import uuid

class SearchQuery(BaseModel):
    """Model for search queries."""
    query: str
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    
class SearchResult(BaseModel):
    """Model for search results."""
    organic: List[Dict[str, Any]] = []
    answerBox: Optional[Dict[str, Any]] = None
    knowledgeGraph: Optional[Dict[str, Any]] = None
    relatedSearches: Optional[List[str]] = None
    searchParameters: Optional[Dict[str, Any]] = None
    
class LLMRequest(BaseModel):
    """Model for LLM generation requests."""
    query: str
    search_results: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    
class LLMResponse(BaseModel):
    """Model for LLM generation responses."""
    answer: str
    request_id: str
    search_query: str
    timestamp: str
    status: str = "success"
    
class APIError(BaseModel):
    """Model for API errors."""
    status_code: int
    detail: str
    request_id: str
    
class HealthCheckResponse(BaseModel):
    """Model for health check responses."""
    status: str
    services: Dict[str, Dict[str, Any]]
    timestamp: str 