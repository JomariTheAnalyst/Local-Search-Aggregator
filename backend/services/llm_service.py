import httpx
import json
import asyncio
from fastapi import HTTPException
from typing import Dict, Any, Union, Optional, AsyncGenerator

from config import settings
from models import SearchResult

async def generate_answer(query: str, search_results: Union[Dict[Any, Any], SearchResult]) -> str:
    """
    Generate an answer using the local LLM (Ollama) based on search results.
    Optimized for handling longer, more complex queries.
    
    Args:
        query: The original search query
        search_results: The search results from Serper.dev (either as Dict or SearchResult)
        
    Returns:
        Generated answer from the LLM
        
    Raises:
        HTTPException: If there's an error with the LLM API request
    """
    # Ensure search_results is a dictionary
    if isinstance(search_results, SearchResult):
        search_results_dict = dict(search_results)
    else:
        search_results_dict = search_results
    
    # Format the prompt with search results
    prompt = format_optimized_prompt(query, search_results_dict)
    
    # Use the direct Ollama API URL - ensure no path duplication
    api_url = settings.OLLAMA_API_URL
    if not api_url.endswith("/api/generate"):
        api_url = f"{api_url}/api/generate"
    
    # Set generation parameters optimized for llama3:8b
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": 1024,
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40
        }
    }
    
    try:
        # Print debug information
        print(f"Sending request to Ollama at: {api_url}")
        print(f"Using model: {settings.OLLAMA_MODEL}")
        print(f"Payload length: {len(prompt)} characters")
        print(f"Payload preview: {prompt[:100]}...")  # Only print the first 100 chars
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                json=payload,
                timeout=300.0  # Increased timeout for longer queries
            )
            
            # Check if the request was successful
            response.raise_for_status()
            
            result = response.json()
            answer = result.get("response", "")
            
            # Check if we got a valid answer
            if not answer or len(answer.strip()) < 10:
                return fallback_answer(query)
                
            return answer
            
    except httpx.HTTPStatusError as e:
        error_detail = f"LLM API error: {str(e)}"
        print(f"HTTP Status Error: {error_detail}")
        print(f"Response content: {e.response.text}")
        if e.response.status_code == 404:
            error_detail = f"LLM API error: Model '{settings.OLLAMA_MODEL}' not found or Ollama server not running at {api_url}"
        # Return fallback answer instead of raising exception
        return fallback_answer(query)
    except httpx.RequestError as e:
        error_detail = f"LLM request error: {str(e)}"
        print(f"Request Error: {error_detail}")
        # Return fallback answer instead of raising exception
        return fallback_answer(query)
    except Exception as e:
        error_detail = f"Unexpected LLM error: {str(e)}"
        print(f"Unexpected Error: {error_detail}")
        # Return fallback answer instead of raising exception
        return fallback_answer(query)

async def generate_answer_streaming(
    query: str, 
    search_results: Union[Dict[Any, Any], SearchResult], 
    max_iterations: int = 100,
    timeout: int = None
) -> AsyncGenerator[str, None]:
    """
    Generate an answer using the local LLM (Ollama) with streaming support.
    Enhanced to ensure complete generation of responses.
    
    Args:
        query: The original search query
        search_results: The search results from Serper.dev
        max_iterations: Maximum number of iterations (chunks) to generate
        timeout: Timeout in seconds for the LLM API call
        
    Yields:
        Chunks of the generated answer as they become available
    """
    # Use provided timeout or fall back to config value
    timeout = timeout or settings.OLLAMA_TIMEOUT
    
    # Ensure search_results is a dictionary
    if isinstance(search_results, SearchResult):
        search_results_dict = dict(search_results)
    else:
        search_results_dict = search_results
    
    # Format the prompt with search results
    prompt = format_optimized_prompt(query, search_results_dict)
    
    # Use the direct Ollama API URL - ensure no path duplication
    api_url = settings.OLLAMA_API_URL
    if not api_url.endswith("/api/generate"):
        api_url = f"{api_url}/api/generate"
    
    # Set generation parameters optimized for complete responses
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "stream": True,
        "options": {
            "num_predict": settings.OLLAMA_MAX_TOKENS,  # Use the configured max tokens
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "stop": ["<|im_end|>", "<|endoftext|>"]  # Add explicit stop tokens
        }
    }
    
    try:
        # Print debug information
        print(f"Sending streaming request to Ollama at: {api_url}")
        print(f"Using model: {settings.OLLAMA_MODEL}")
        print(f"Max tokens: {settings.OLLAMA_MAX_TOKENS}")
        print(f"Timeout: {timeout} seconds")
        print(f"Payload length: {len(prompt)} characters")
        
        # Track if we've received any valid chunks
        has_yielded = False
        buffer = ""
        iterations = 0
        end_token = "END OF RESPONSE"
        
        # Track completion indicators
        completion_indicators = [
            "In conclusion", 
            "To summarize", 
            "In summary",
            "Thank you for your question",
            "I hope this helps",
            end_token  # Special completion token from the prompt
        ]
        
        # Create a flag to track if we've detected a natural completion
        natural_completion_detected = False
        
        # Set timeout for streaming responses
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", api_url, json=payload) as response:
                    response.raise_for_status()
                    print(f"LLM streaming response status: {response.status_code}")
                    
                    # Process the streaming response
                    async for chunk in response.aiter_text():
                        try:
                            # Each chunk is a JSON object with a "response" field
                            print(f"Raw LLM chunk: {chunk[:50]}...")
                            data = json.loads(chunk)
                            
                            # Check for done flag
                            if data.get("done", False):
                                print("Received 'done' flag from LLM")
                                break
                                
                            if "response" in data:
                                text_chunk = data["response"]
                                if text_chunk:  # Only yield non-empty chunks
                                    # Update buffer with new chunk to check for end token
                                    # that might be split across chunks
                                    temp_buffer = buffer + text_chunk
                                    
                                    # Check if buffer now contains our special completion token
                                    end_token_pos = temp_buffer.find(end_token)
                                    
                                    if end_token_pos != -1:
                                        # If we found the end token, only yield the text up to that point
                                        print(f"Found {end_token} token, truncating response")
                                        if end_token_pos > 0:
                                            final_chunk = temp_buffer[:end_token_pos].strip()
                                            # Only yield if there's something new (not already in buffer)
                                            if len(final_chunk) > len(buffer):
                                                yield final_chunk[len(buffer):]
                                        natural_completion_detected = True
                                        break
                                    
                                    print(f"Yielding chunk: {text_chunk[:50]}...")
                                    buffer = temp_buffer
                                    has_yielded = True
                                    yield text_chunk
                                    
                                    # Check for natural completion indicators
                                    for indicator in completion_indicators:
                                        if indicator.lower() in buffer.lower():
                                            print(f"Natural completion indicator detected: {indicator}")
                                            natural_completion_detected = True
                                    
                                    # Increment iteration counter and check max
                                    iterations += 1
                                    if iterations >= max_iterations:
                                        print(f"Reached maximum iterations ({max_iterations}), stopping generation")
                                        
                                        # If we've reached max iterations but haven't detected a natural completion,
                                        # add a closing sentence to make the response feel complete
                                        if not natural_completion_detected:
                                            closing = "\n\nI hope this information addresses your question. Let me know if you need further clarification."
                                            yield closing
                                            
                                        break
                        except json.JSONDecodeError as e:
                            print(f"Error decoding JSON chunk: {e} - Raw chunk: {chunk[:50]}...")
                            # Skip malformed chunks
                            continue
                
                # Check if the response feels incomplete
                if has_yielded and not natural_completion_detected and iterations < max_iterations:
                    print("Response may be incomplete, adding closing sentence")
                    closing = "\n\nI hope this information addresses your question. Let me know if you need further clarification."
                    yield closing
                    
            except httpx.HTTPStatusError as e:
                print(f"HTTP error during streaming: {e.response.status_code} - {str(e)}")
                print(f"Response content: {e.response.text}")
                # Don't raise, we'll handle with fallback
            except httpx.RequestError as e:
                print(f"Request error during streaming: {str(e)}")
                # Don't raise, we'll handle with fallback
            
            # If we didn't get any valid response, yield a fallback
            if not has_yielded or not buffer.strip():
                print("No valid response received from LLM, using fallback")
                fallback = fallback_answer(query)
                yield fallback
                
    except Exception as e:
        print(f"Error in streaming generation: {str(e)}")
        fallback = fallback_answer(query)
        print(f"Using fallback response: {fallback}")
        yield fallback
    
    # Always ensure we yield something, even if everything else fails
    if not has_yielded:
        emergency_fallback = "I apologize, but I couldn't process your request at this time. Please try again later."
        print(f"Using emergency fallback: {emergency_fallback}")
        yield emergency_fallback

def fallback_answer(query: str) -> str:
    """
    Provide a fallback answer when LLM generation fails.
    
    Args:
        query: The original query
        
    Returns:
        A generic fallback answer
    """
    return f"I'm sorry, I couldn't generate a complete response for '{query}'. Please try a more specific question or check back later."

def format_optimized_prompt(query: str, search_results: Dict[Any, Any]) -> str:
    """
    Format an optimized prompt for the LLM using the search results.
    Enhanced to encourage complete, thorough responses.
    
    Args:
        query: The original search query
        search_results: The search results from Serper.dev
        
    Returns:
        Formatted prompt string
    """
    # Build the prompt with clear instructions
    prompt = f"""You are an AI assistant that provides helpful, accurate, thorough, and complete answers based on search results.

USER QUERY: {query}

Your task is to analyze and synthesize the following search results to provide a comprehensive answer to the user's question. 
Focus on being accurate, detailed, dont explain it overexaggerated and complete in your response.

"""
    
    # Extract organic search results and limit to top 5
    organic_results = search_results.get("organic", [])[:5]  # Limit to top 5 results
    
    # Extract answer box if available
    answer_box = search_results.get("answerBox", {})
    if not answer_box and "answerBox" not in search_results:
        # Try alternate key format
        answer_box = search_results.get("answer_box", {})
    
    # Add answer box information if available
    if answer_box:
        prompt += "FEATURED ANSWER:\n"
        if "answer" in answer_box:
            # Truncate to ~500 characters (increased from 300)
            answer = answer_box["answer"]
            if len(answer) > 500:
                answer = answer[:497] + "..."
            prompt += f"{answer}\n\n"
        elif "snippet" in answer_box:
            # Truncate to ~500 characters (increased from 300)
            snippet = answer_box["snippet"]
            if len(snippet) > 500:
                snippet = snippet[:497] + "..."
            prompt += f"{snippet}\n\n"
    
    # Add organic search results
    prompt += "SEARCH RESULTS:\n"
    
    for i, result in enumerate(organic_results, 1):
        title = result.get("title", "No Title")
        
        # Truncate snippet to ~400 characters (increased from 300)
        snippet = result.get("snippet", "No Snippet")
        if len(snippet) > 400:
            snippet = snippet[:397] + "..."
            
        link = result.get("link", "No Link")
        
        prompt += f"{i}. {title}\n"
        prompt += f"   {snippet}\n"
        prompt += f"   Source: {link}\n\n"
    
    # Add final instruction with emphasis on completeness
    prompt += """INSTRUCTIONS:
1. Provide a thorough and complete answer to the user's query.
2. Structure your response with a clear beginning, middle, and conclusion.
3. Include relevant facts, explanations, and context from the search results.
4. If the information is not sufficient, acknowledge this limitation.
5. Do not include phrases like "Based on the search results" or "According to the information provided" in your answer.
6. Write in a helpful, informative tone.
7. Always finish your response with a proper conclusion or summary.
8. Make sure your answer is complete and doesn't cut off mid-explanation.
9. End your response with the phrase "END OF RESPONSE" to indicate you have finished.

Remember: Your goal is to provide a complete, well-structured answer that fully addresses the user's question.

Begin your response now:
"""
    
    return prompt 

def format_prompt(query: str, search_results: Dict[Any, Any]) -> str:
    """
    Legacy format prompt function.
    Use format_optimized_prompt instead.
    
    Args:
        query: The original search query
        search_results: The search results from Serper.dev
        
    Returns:
        Formatted prompt string
    """
    return format_optimized_prompt(query, search_results) 