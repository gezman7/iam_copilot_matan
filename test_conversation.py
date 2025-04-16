import os
import logging
import asyncio
from src.Iam_copilot import IAMCopilot

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    print("Initializing IAM Copilot with conversation support...")
    
    # Create IAMCopilot instance
    copilot = IAMCopilot(db_path="iam_risks.db")
    
    # Use a unique thread ID for this conversation
    thread_id = "conversation-test-1"
    
    # Initial query
    initial_query = "How many users have weak MFA?"
    print(f"\n>>> Initial Query: {initial_query}")
    
    # Process initial query with streaming
    async for event in copilot.stream_query(initial_query, thread_id):
        if "messages" in event and event["messages"]:
            last_message = event["messages"][-1]
            if hasattr(last_message, "content") and last_message.content:
                print("\n=== RESPONSE STREAM ===")
                print(last_message.content)
                print("=====================")
    
    # Follow-up query that relies on previous context
    follow_up_query = "Which department has the most users with this issue?"
    print(f"\n>>> Follow-up Query: {follow_up_query}")
    
    # Process follow-up query using the same thread_id with streaming
    async for event in copilot.stream_query(follow_up_query, thread_id):
        if "messages" in event and event["messages"]:
            last_message = event["messages"][-1]
            if hasattr(last_message, "content") and last_message.content:
                print("\n=== RESPONSE STREAM ===")
                print(last_message.content)
                print("=====================")
    
    # Another follow-up
    second_follow_up = "What security recommendations do you have for these weak MFA users?"
    print(f"\n>>> Second Follow-up Query: {second_follow_up}")
    
    # Process second follow-up query using the same thread_id with streaming
    async for event in copilot.stream_query(second_follow_up, thread_id):
        if "messages" in event and event["messages"]:
            last_message = event["messages"][-1]
            if hasattr(last_message, "content") and last_message.content:
                print("\n=== RESPONSE STREAM ===")
                print(last_message.content)
                print("=====================")
    
    print("\nConversation test completed.")

if __name__ == "__main__":
    asyncio.run(main()) 