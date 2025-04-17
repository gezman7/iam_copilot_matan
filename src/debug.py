#!/usr/bin/env python3

import tiktoken
from typing import Optional, Dict, List, Any, TypedDict

# Define IAMAgentState type locally using TypedDict to avoid circular imports
# This should match the definition in agent_eval.py
class IAMAgentState(TypedDict, total=False):
    """State for the IAM Agent workflow."""
    messages: List[Any]  # Conversation history
    error: Optional[str]  # Error message if any operation fails
    db_metadata: Optional[str]  # Database metadata (tables and user schema)
    current_query: Optional[str]  # Current SQL query being processed
    query_result: Optional[str]  # Result of the executed query
    last_tool_call_id: Optional[str]  # ID of the last tool call
    has_final_answer: bool  # Whether a final answer has been submitted

# Debug settings
DEBUG_ENABLED = True  # Set to False in production

def debug_state(state_dict: IAMAgentState, node_name=None) -> IAMAgentState:
    """Debug function to print state information. No-op if debugging disabled."""
    if not DEBUG_ENABLED:
        return state_dict
        
    print(f"\n==== DEBUG STATE {'for ' + node_name if node_name else ''} ====")
    
    # Log all state keys and values for complete node output
    print("State keys:")
    for key, value in state_dict.items():
        if key != "messages":
            print(f"  {key}: {value}")
    
    # Count tokens for all messages
    total_tokens = 0
    if "messages" in state_dict:
        encoder = tiktoken.get_encoding("cl100k_base")  # Using OpenAI's encoding
        
        print(f"Number of messages: {len(state_dict['messages'])}")
        for i, msg in enumerate(state_dict["messages"]):
            msg_type = type(msg).__name__
            content = getattr(msg, "content", "No content")
            tool_calls = getattr(msg, "tool_calls", None)
            tool_call_id = getattr(msg, "tool_call_id", None)
            
            # Count tokens in this message
            message_tokens = len(encoder.encode(str(content)))
            total_tokens += message_tokens
            
            print(f"  Message {i} ({msg_type}): {message_tokens} tokens")
            if content and content.strip():
                print(f"    Content: {content}")
            if tool_calls:
                print(f"    Tool calls: {tool_calls}")
                # Add tokens for tool calls
                tool_calls_text = str(tool_calls)
                tool_tokens = len(encoder.encode(tool_calls_text))
                total_tokens += tool_tokens
            if tool_call_id:
                print(f"    Tool call ID: {tool_call_id}")
    
    print(f"Total tokens in state: {total_tokens}")
    
    if "error" in state_dict:
        print(f"Error: {state_dict.get('error')}")
    
    print("================================")
    return state_dict 