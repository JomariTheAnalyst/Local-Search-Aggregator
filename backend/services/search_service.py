import httpx
import json
import time
from fastapi import HTTPException
from typing import Dict, Any

from config import settings

async def search_serper(query: str, timeout: float = 60.0) -> Dict[Any, Any]:
    """
    Send a search query to Serper.dev API and return results.
    
    Args:
        query: The search query string
        timeout: Timeout in seconds for the request
        
    Returns:
        Dict containing search results
        
    Raises:
        HTTPException: If there's an error with the API request
    """
    headers = {
        "X-API-KEY": settings.SERPER_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "q": query,
        "gl": "us",
        "hl": "en"
    }
    
    try:
        print(f"Sending search request to Serper.dev for query: {query}")
        print(f"Using API key: {settings.SERPER_API_KEY[:5]}...{settings.SERPER_API_KEY[-5:]}")
        print(f"Serper.dev API URL: {settings.SERPER_API_URL}")
        print(f"Request timeout: {timeout} seconds")
        
        async with httpx.AsyncClient() as client:
            print("Sending request to Serper.dev...")
            start_time = time.time()
            
            response = await client.post(
                settings.SERPER_API_URL,
                headers=headers,
                json=payload,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            print(f"Search request completed in {elapsed:.2f} seconds")
            print(f"Response status code: {response.status_code}")
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Return the search results
            result = response.json()
            print(f"Search completed successfully with {len(result.get('organic', []))} organic results")
            
            # Log some details about the results
            if 'organic' in result and len(result['organic']) > 0:
                print(f"First result title: {result['organic'][0].get('title', 'No title')}")
                print(f"First result link: {result['organic'][0].get('link', 'No link')}")
                print(f"First result snippet preview: {result['organic'][0].get('snippet', 'No snippet')[:100]}...")
            
            if 'answerBox' in result and result['answerBox']:
                print("Answer box found in results")
                if 'answer' in result['answerBox']:
                    print(f"Answer box content: {result['answerBox']['answer'][:100]}...")
                elif 'snippet' in result['answerBox']:
                    print(f"Answer box snippet: {result['answerBox']['snippet'][:100]}...")
            
            print(f"Total result size: {len(json.dumps(result))} bytes")
            return result
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP Status Error in search: {str(e)}")
        print(f"Response status code: {e.response.status_code if hasattr(e, 'response') else 'Unknown'}")
        print(f"Response content: {e.response.text if hasattr(e, 'response') else 'No response'}")
        
        if hasattr(e, 'response') and e.response.status_code == 403:
            raise HTTPException(
                status_code=403, 
                detail="Authentication failed with Serper.dev API. Please check your API key."
            )
        raise HTTPException(
            status_code=e.response.status_code if hasattr(e, 'response') else 500, 
            detail=f"Search API error: {str(e)}"
        )
    except httpx.RequestError as e:
        print(f"Request Error in search: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        if isinstance(e, httpx.TimeoutException):
            print("Request timed out")
            raise HTTPException(status_code=504, detail=f"Search request timed out after {timeout} seconds")
        elif isinstance(e, httpx.ConnectError):
            print("Connection error")
            raise HTTPException(status_code=503, detail="Could not connect to search API")
        else:
            raise HTTPException(status_code=500, detail=f"Request error: {str(e)}")
    except Exception as e:
        print(f"Unexpected error in search: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}") 