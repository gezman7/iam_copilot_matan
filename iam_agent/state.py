#!/usr/bin/env python3

from typing import Optional, List, Any, TypedDict

# Define IAMAgentState type locally using TypedDict to avoid circular imports
class IAMAgentState(TypedDict, total=False):
    """State for the IAM Agent workflow."""
    messages: List[Any]  # Conversation history
    error: Optional[str]  # Error message if any operation fails
    db_metadata: Optional[str]  # Database metadata (tables and user schema)
    current_query: Optional[str]  # Current SQL query being processed
    query_result: Optional[str]  # Result of the executed query
    last_tool_call_id: Optional[str]  # ID of the last tool call
    has_final_answer: bool  # Whether a final answer has been submitted
    user_query: Optional[str]  # Original user query
    risk_type: Optional[str]  # Identified risk type if applicable
    thread_id: Optional[str]  # Thread ID for conversation tracking 