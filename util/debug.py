#!/usr/bin/env python3

import os
import logging
import datetime
from typing import Dict, Any, Optional
import tiktoken

# Configure logging
def setup_logger(session_id: str = None) -> logging.Logger:
    """Configure and return a logger for debug information.
    
    Args:
        session_id: Unique identifier for this session/chat
        
    Returns:
        Configured logger instance
    """
    # Create a unique session ID if not provided
    if not session_id:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = f"session_{timestamp}"
    
    # Create logger
    logger = logging.getLogger(f"iam_agent.{session_id}")
    logger.setLevel(logging.DEBUG)
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Create file handler
    log_file = f"logs/iam_session_{session_id}.txt"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    
    # Add a console handler for immediate feedback
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    logger.info(f"Logger initialized. Writing to {log_file}")
    return logger

def debug_log(logger: logging.Logger, message: str, node_name: Optional[str] = None):
    """Log debug information.
    
    Args:
        logger: Logger instance
        message: Debug message
        node_name: Optional name of the current node
    """
    separator = "=" * 80
    prefix = f"[{node_name}] " if node_name else ""
    logger.debug(f"\n{separator}\n{prefix}{message}\n{separator}")

def debug_state(logger: logging.Logger, state: Dict[str, Any], node_name: Optional[str] = None) -> Dict[str, Any]:
    """Log state information and return the state unchanged.
    
    Args:
        logger: Logger instance
        state: State dictionary to log
        node_name: Optional name of the current node
        
    Returns:
        The original state dictionary
    """
    separator = "=" * 80
    prefix = f"[{node_name}] " if node_name else ""
    logger.debug(f"\n{separator}\n{prefix}STATE:\n{separator}")
    
    # Log all state keys and values
    for key, value in state.items():
        if key != "messages":
            logger.debug(f"{prefix}  {key}: {value}")
    
    # Count tokens for all messages
    if "messages" in state:
        try:
            encoder = tiktoken.get_encoding("cl100k_base")
            total_tokens = 0
            
            logger.debug(f"{prefix}Number of messages: {len(state['messages'])}")
            for i, msg in enumerate(state["messages"]):
                msg_type = type(msg).__name__
                content = getattr(msg, "content", "No content")
                if content and len(content) > 50:
                    content = content[:47] + "..."
                tool_calls = getattr(msg, "tool_calls", None)
                tool_call_id = getattr(msg, "tool_call_id", None)
                
                # Count tokens in this message
                message_tokens = len(encoder.encode(str(getattr(msg, "content", "No content"))))
                total_tokens += message_tokens
                
                logger.debug(f"{prefix}  Message {i} ({msg_type}): {message_tokens} tokens")
                logger.debug(f"{prefix}    Content: {content}")
                if tool_calls:
                    logger.debug(f"{prefix}    Tool calls: {tool_calls}")
                    # Add tokens for tool calls
                    tool_calls_text = str(tool_calls)
                    tool_tokens = len(encoder.encode(tool_calls_text))
                    total_tokens += tool_tokens
                if tool_call_id:
                    logger.debug(f"{prefix}    Tool call ID: {tool_call_id}")
            
            logger.debug(f"{prefix}Total tokens in state: {total_tokens}")
        except Exception as e:
            logger.error(f"{prefix}Error counting tokens: {str(e)}")
    
    if "error" in state:
        logger.debug(f"{prefix}Error: {state.get('error')}")
    
    logger.debug(separator)
    return state

def count_tokens(text: str) -> int:
    """Count the number of tokens in a text string."""
    try:
        encoder = tiktoken.get_encoding("cl100k_base")
        return len(encoder.encode(text))
    except Exception:
        # Fallback to rough approximation if tiktoken fails
        return len(text.split()) * 1.3  # Rough approximation 