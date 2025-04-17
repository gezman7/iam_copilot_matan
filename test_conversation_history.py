#!/usr/bin/env python3

import asyncio
import logging
from src.Iam_copilot import IAMCopilot
from langchain_core.messages import HumanMessage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_conversation_basics():
    """Test the IAM Copilot's basic query capabilities."""
    print("\n=== Testing IAM Copilot Basic Query Capabilities ===\n")
    
    # Initialize copilot with debug mode
    copilot = IAMCopilot(db_path="/Users/matangez/Documents/iam_agent/data/risk_views.db", debug=True)
    
    # First query: How many users have weak MFA?
    print("\n=== Query 1: How many users have weak MFA? ===")
    response = await process_query(copilot, "How many users have weak MFA?", "query1")
    print(f"Response: {response}")
    
    # Second query: Which department has the most users with this issue?
    print("\n=== Query 2: Which department has the most users with this issue? ===")
    response = await process_query(copilot, "Which department has the most users with this issue?", "query2")
    print(f"Response: {response}")
    
    # Third query: How many privileged access users are there?
    print("\n=== Query 3: How many users have privileged access? ===")
    response = await process_query(copilot, "How many users have privileged access?", "query3")
    print(f"Response: {response}")
    
    # Fourth query: Tell me about weak MFA users
    print("\n=== Query 4: Tell me about the weak MFA users ===")
    response = await process_query(copilot, "Tell me about the weak MFA users", "query4")
    print(f"Response: {response}")
    
    print("\n=== Basic Query Testing Complete ===")

async def process_query(copilot, query, thread_id):
    """Process a query and extract the result."""
    result = None
    async for event in copilot.stream_query(query, thread_id):
        if "query_result" in event:
            result = event["query_result"]
    return result

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_conversation_basics()) 