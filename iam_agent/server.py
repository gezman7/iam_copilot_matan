"""IAM Agent FastAPI Server.

This module provides a FastAPI server for interacting with the IAMCopilot agent.
It supports both streaming and non-streaming responses.
"""

import sys
import os
import logging
import argparse
from typing import Dict, Any, Optional, List, AsyncIterator
import json
import uuid

import uvicorn
from fastapi import FastAPI, Body, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import IAMCopilot
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from iam_agent.Iam_copilot import IAMCopilot
from iam_agent.config import ServerConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("iam-server")

# Create FastAPI app
app = FastAPI(title="IAM Agent Server", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request and response models
class ChatRequest(BaseModel):
    """Chat request model."""
    query: str
    thread_id: Optional[str] = None
    stream: bool = True

class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    thread_id: str

# Global IAMCopilot instance
copilot: Optional[IAMCopilot] = None
config: ServerConfig = ServerConfig()

@app.on_event("startup")
async def startup_event():
    """Initialize the IAMCopilot agent on server startup."""
    global copilot, config
    
    try:
        logger.info(f"Initializing IAMCopilot with model {config.model}")
        copilot = IAMCopilot(
            debug=True
        )
        logger.info("IAMCopilot initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize IAMCopilot: {str(e)}")
        # We'll keep the server running, but requests will fail until
        # the copilot is properly initialized

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on server shutdown."""
    global copilot
    if copilot:
        logger.info("Closing IAMCopilot")
        copilot.close()

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "IAM Agent Server is running. Use /chat or /stream endpoints."}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a chat message with IAMCopilot.
    
    This endpoint handles non-streaming responses.
    """
    global copilot
    
    logger.info(f"Received /chat request with query: '{request.query}'")
    
    if not copilot:
        logger.error("IAMCopilot not initialized")
        raise HTTPException(status_code=503, detail="IAMCopilot not initialized")
    
    thread_id = request.thread_id or str(uuid.uuid4())
    logger.info(f"Using thread ID: {thread_id}")
    
    try:
        # Process the query
        logger.info("Processing query with IAMCopilot")
        result = copilot.process_query(query=request.query, thread_id=thread_id)
        logger.info(f"Received result from IAMCopilot: {type(result)}")
        
        # Extract response from the latest AI message
        messages = result.get("messages", [])
        logger.info(f"Found {len(messages)} messages in result")
        
        response = "No response generated."
        for msg in reversed(messages):
            logger.info(f"Processing message: {type(msg)}")
            if hasattr(msg, "type") and msg.type == "ai":
                response = msg.content
                logger.info(f"Found AI message with type attribute, content length: {len(response)}")
                break
            elif hasattr(msg, "content") and isinstance(msg, dict) and msg.get("type") == "ai":
                response = msg.get("content", "")
                logger.info(f"Found AI message as dict, content length: {len(response)}")
                break
            elif hasattr(msg, "content"):
                response = msg.content
                logger.info(f"Found message with content attribute, content length: {len(response)}")
                break
        
        logger.info(f"Returning response with length {len(response)}")
        return ChatResponse(response=response, thread_id=thread_id)
    
    except Exception as e:
        logger.error(f"Error processing chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")

async def stream_generator(query: str, thread_id: str) -> AsyncIterator[str]:
    """Generate streaming responses from IAMCopilot."""
    global copilot
    
    logger.info(f"Starting stream for query: '{query}' with thread ID: {thread_id}")
    
    if not copilot:
        logger.error("IAMCopilot not initialized for streaming")
        yield json.dumps({"error": "IAMCopilot not initialized"})
        return
    
    try:
        logger.info("Calling copilot.stream_query")
        count = 0
        async for event in copilot.stream_query(query=query, thread_id=thread_id):
            count += 1
            logger.info(f"Received event {count}: {type(event)}")
            
            # Process event based on its structure
            if "values" in event:
                logger.info("Found 'values' in event")
                values = event["values"]
                if "messages" in values:
                    logger.info(f"Found 'messages' in values with {len(values['messages'])} items")
                    messages = values["messages"]
                    for msg in messages:
                        if hasattr(msg, "type") and msg.type == "ai":
                            chunk = msg.content
                            logger.info(f"Yielding AI message with type attribute, content length: {len(chunk)}")
                            yield json.dumps({"chunk": chunk, "thread_id": thread_id})
                        elif hasattr(msg, "content") and isinstance(msg, dict) and msg.get("type") == "ai":
                            chunk = msg.get("content", "")
                            logger.info(f"Yielding AI message as dict, content length: {len(chunk)}")
                            yield json.dumps({"chunk": chunk, "thread_id": thread_id})
                        elif hasattr(msg, "content") and msg.content:
                            chunk = msg.content
                            logger.info(f"Yielding message with content attribute, content length: {len(chunk)}")
                            yield json.dumps({"chunk": chunk, "thread_id": thread_id})
            elif "error" in event:
                logger.error(f"Error in event: {event['error']}")
                yield json.dumps({"error": event["error"], "thread_id": thread_id})
            # Check if chunk is already formatted
            elif "chunk" in event:
                logger.info(f"Found direct 'chunk' in event, length: {len(event['chunk'])}")
                # Already formatted for streaming, just add thread_id if needed
                if "thread_id" not in event:
                    event["thread_id"] = thread_id
                yield json.dumps(event)
            else:
                logger.warning(f"Unhandled event structure: {event}")
    
    except Exception as e:
        logger.error(f"Error in stream generator: {str(e)}", exc_info=True)
        yield json.dumps({"error": f"Error in stream generator: {str(e)}", "thread_id": thread_id})

@app.post("/stream")
async def stream(request: ChatRequest):
    """Process a chat message with streaming response.
    
    This endpoint returns a streaming response from IAMCopilot.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    
    return StreamingResponse(
        stream_generator(query=request.query, thread_id=thread_id),
        media_type="application/json"
    )

def main():
    """Run the FastAPI server with command-line arguments."""
    global config
    
    parser = argparse.ArgumentParser(description="IAM Agent Server")
    parser.add_argument("--host", type=str, default=config.host, help="Host to bind the server to")
    parser.add_argument("--port", type=int, default=config.port, help="Port to bind the server to")
    parser.add_argument("--db-path", type=str, default=config.db_path, help="Path to the SQLite database")
    parser.add_argument("--model", type=str, default=config.model, help="Name of the LLM model to use")
    parser.add_argument("--num-ctx", type=int, default=config.num_ctx, help="Context window size for the LLM")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Update config with command-line arguments
    config = ServerConfig(
        host=args.host,
        port=args.port,
        db_path=args.db_path,
        model=args.model,
        num_ctx=args.num_ctx,
        debug=args.debug
    )
    
    # Run the server
    uvicorn.run(
        "iam_agent.server:app",
        host=config.host,
        port=config.port,
        reload=False,
        log_level="info"
    )

if __name__ == "__main__":
    main() 