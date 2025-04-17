#!/usr/bin/env python3

import asyncio
import logging
import uuid
from src.Iam_copilot import IAMCopilot
from langchain_core.messages import HumanMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_conversation_history():
    """Test the IAM Copilot's conversation history support using MemorySaver."""
    print("\n=== Testing IAM Copilot Conversation History with MemorySaver ===\n")
    
    # Initialize copilot with debug mode
    copilot = IAMCopilot(db_path="risk_views.db", debug=True)
    
    # Use a unique thread ID for this conversation
    thread_id = f"conversation-test-{uuid.uuid4().hex[:8]}"
    print(f"Using thread ID: {thread_id}\n")
    
    # Initial query about weak MFA users
    initial_query = "How many users have weak MFA?"
    print(f"\nUser: {initial_query}")
    
    # Process initial query with streaming
    print("\nProcessing initial query...\n")
    response_content = ""
    async for event in copilot.stream_query(initial_query, thread_id):
        if "messages" in event and event["messages"]:
            last_message = event["messages"][-1]
            if hasattr(last_message, "content") and last_message.content:
                response_content = last_message.content
    print(f"Assistant: {response_content}")
    
    # Follow-up query about departments (should use context from previous query)
    follow_up = "Which department has the most users with this issue?"
    print(f"\nUser: {follow_up}")
    
    # Process follow-up query using the same thread_id
    print("\nProcessing follow-up query using same thread ID...\n")
    response_content = ""
    async for event in copilot.stream_query(follow_up, thread_id):
        if "messages" in event and event["messages"]:
            last_message = event["messages"][-1]
            if hasattr(last_message, "content") and last_message.content:
                response_content = last_message.content
    print(f"Assistant: {response_content}")
    
    # Print all saved messages to verify persistence
    print("\n=== Current Thread State ===")
    try:
        previous_state = copilot.memory.get(thread_id)
        if previous_state and "messages" in previous_state:
            for i, msg in enumerate(previous_state["messages"]):
                if hasattr(msg, "content"):
                    role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                    print(f"{role}: {msg.content}")
    except Exception as e:
        print(f"Error accessing thread state: {str(e)}")
    
    # Start a new conversation with a different thread ID
    new_thread_id = f"conversation-test-{uuid.uuid4().hex[:8]}"
    print(f"\n\nStarting a new conversation with thread ID: {new_thread_id}")
    
    # First query in new thread
    new_query = "How many users have privileged access?"
    print(f"\nUser: {new_query}")
    
    # Process query in new thread
    print("\nProcessing query in new thread...\n")
    response_content = ""
    async for event in copilot.stream_query(new_query, new_thread_id):
        if "messages" in event and event["messages"]:
            last_message = event["messages"][-1]
            if hasattr(last_message, "content") and last_message.content:
                response_content = last_message.content
    print(f"Assistant: {response_content}")
    
    # Now ask about the previous context in the new thread - should not have access
    follow_up = "Tell me about the weak MFA users we discussed earlier."
    print(f"\nUser: {follow_up}")
    print("\nProcessing follow-up in new thread (should not have history from first thread)...\n")
    
    response_content = ""
    async for event in copilot.stream_query(follow_up, new_thread_id):
        if "messages" in event and event["messages"]:
            last_message = event["messages"][-1]
            if hasattr(last_message, "content") and last_message.content:
                response_content = last_message.content
    print(f"Assistant: {response_content}")
    
    print("\n=== Conversation History Test Complete ===")
    print(f"First conversation thread ID: {thread_id}")
    print(f"Second conversation thread ID: {new_thread_id}")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_conversation_history()) 