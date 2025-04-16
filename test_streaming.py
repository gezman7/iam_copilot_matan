import os
import logging
import asyncio
from datetime import datetime
from src.Iam_copilot import IAMCopilot

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StreamingTester:
    """Class for testing the streaming capabilities of IAMCopilot"""
    
    def __init__(self):
        self.copilot = IAMCopilot(db_path="iam_risks.db")
        # Use timestamp in thread_id to ensure uniqueness
        self.thread_id = f"stream-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
    async def test_basic_streaming(self):
        """Test basic streaming functionality with 'values' mode"""
        print("\n===== Testing Basic Streaming =====\n")
        
        # Initial query
        query = "How many users have weak MFA?"
        print(f"User: {query}")
        
        print("\n--- Response ---")
        async for event in self.copilot.stream_query(query, self.thread_id, stream_mode="values"):
            if "messages" in event and event["messages"]:
                last_message = event["messages"][-1]
                if hasattr(last_message, "content") and last_message.content:
                    # Print a dot for each chunk to show streaming progress
                    print(".", end="", flush=True)
        print("\n--- End of response ---\n")
        
        # Follow-up query
        follow_up = "Which department has the most users with this issue?"
        print(f"User: {follow_up}")
        
        print("\n--- Response ---")
        async for event in self.copilot.stream_query(follow_up, self.thread_id, stream_mode="values"):
            if "messages" in event and event["messages"]:
                last_message = event["messages"][-1]
                if hasattr(last_message, "content") and last_message.content:
                    # Print a dot for each chunk to show streaming progress
                    print(".", end="", flush=True)
        print("\n--- End of response ---\n")
        
        print("✅ Basic streaming test completed")
        
    async def test_steps_streaming(self):
        """Test streaming with 'steps' mode to see each step"""
        print("\n===== Testing Steps Streaming =====\n")
        
        query = "List all weak MFA users and analyze the results."
        print(f"User: {query}")
        
        print("\n--- Steps ---")
        step_count = 0
        async for event in self.copilot.stream_query(query, self.thread_id, stream_mode="steps"):
            if "steps" in event:
                step_count += 1
                print(f"\nStep {step_count}: Received step event")
            elif "messages" in event and event["messages"]:
                print(".", end="", flush=True)
        print("\n--- End of steps ---\n")
        
        print(f"✅ Steps streaming test completed ({step_count} steps observed)")
        
    async def test_detailed_streaming(self):
        """Test the stream_with_details method for comprehensive information"""
        print("\n===== Testing Detailed Streaming =====\n")
        
        query = "What security recommendations do you have for weak MFA users?"
        print(f"User: {query}")
        
        print("\n--- Detailed Stream ---")
        async for event in self.copilot.stream_with_details(query, self.thread_id):
            event_type = event.get("type", "unknown")
            content = event.get("content", "")
            
            if event_type == "start_steps":
                print("\n🚀 Agent started")
            elif event_type == "step":
                print(f"\n⚙️ Tool: {event.get('name', 'Unknown')}")
            elif event_type == "observation":
                print("👁️", end="", flush=True)
            elif event_type == "response":
                print("🤖", end="", flush=True)
            elif event_type == "end":
                print(f"\n✅ Agent completed")
            elif event_type == "error":
                print(f"\n❌ Error: {content}")
        print("\n--- End of detailed stream ---\n")
        
        print("✅ Detailed streaming test completed")
        
    async def run_all_tests(self):
        """Run all streaming tests in sequence"""
        print("\n============================================")
        print("  TESTING IAM COPILOT STREAMING CAPABILITIES  ")
        print("============================================\n")
        
        await self.test_basic_streaming()
        await self.test_steps_streaming()  
        await self.test_detailed_streaming()
        
        print("\n============================================")
        print("          ALL STREAMING TESTS PASSED         ")
        print("============================================\n")

async def main():
    tester = StreamingTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main()) 