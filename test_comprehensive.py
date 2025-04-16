import os
import logging
import asyncio
import json
from datetime import datetime
from src.Iam_copilot import IAMCopilot

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def comprehensive_test():
    """Run a comprehensive test of the IAM copilot's streaming capabilities"""
    print("\n============================================")
    print("     COMPREHENSIVE STREAMING TEST     ")
    print("============================================\n")
    
    # Create IAM copilot instance
    copilot = IAMCopilot(db_path="iam_risks.db")
    
    # Use a unique thread ID
    thread_id = f"comprehensive-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # The query to test
    query = "How many users have weak MFA, which department has the most, and what security recommendations do you have?"
    
    print(f"USER QUERY: {query}\n")
    
    # PART 1: Test with detailed streaming
    print("PART 1: DETAILED STREAMING OUTPUT\n")
    response_content = ""
    current_step = None
    
    async for event in copilot.stream_with_details(query, thread_id):
        event_type = event.get("type", "unknown")
        content = event.get("content", "")
        
        # Format and display based on event type
        if event_type == "start_steps":
            print("🚀 Starting agent execution...\n")
            
        elif event_type == "step":
            step_name = event.get("name", "Unknown action")
            step_input = event.get("input", {})
            
            # Format the input for better readability
            input_str = ""
            if step_input:
                try:
                    if isinstance(step_input, dict):
                        input_str = json.dumps(step_input, indent=2)
                    else:
                        input_str = str(step_input)
                except:
                    input_str = str(step_input)
            
            current_step = step_name
            print(f"⚙️ EXECUTING: {step_name}")
            if input_str:
                print(f"📥 INPUT: {input_str}\n")
            
        elif event_type == "observation":
            if current_step:
                # Truncate long observations for clarity
                obs_display = content
                if len(obs_display) > 200:
                    obs_display = obs_display[:200] + "... [truncated]"
                print(f"👁️ RESULT FROM {current_step}: {obs_display}\n")
            
        elif event_type == "response":
            # Accumulate response content
            response_content += content
            print("🤖 GENERATING RESPONSE...")
        
        elif event_type == "fallback":
            print(f"⚠️ {content}")
            
        elif event_type == "end":
            print(f"✅ {content}\n")
    
    print("\n---------------------------------------------------\n")
    
    # PART 2: Test with simplified streaming
    print("PART 2: SIMPLIFIED STREAMING OUTPUT\n")
    
    # Use a different thread ID for a fresh conversation
    thread_id2 = f"simple-test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    simple_response = ""
    
    async for event in copilot.stream_simplified(query, thread_id2):
        event_type = event.get("type", "unknown")
        content = event.get("content", "")
        
        if event_type == "start":
            print(f"🚀 {content}")
            
        elif event_type == "ai":
            simple_response += content
            print(f"🤖 AI: {content[:50]}..." if len(content) > 50 else f"🤖 AI: {content}")
            
        elif event_type == "tool":
            print(f"🔧 TOOL: {content[:50]}..." if len(content) > 50 else f"🔧 TOOL: {content}")
            
        elif event_type == "human":
            print(f"👤 HUMAN: {content}")
            
        elif event_type == "end":
            print(f"✅ {content}")
            
        elif event_type == "error":
            print(f"❌ ERROR: {content}")
    
    # Display the final response from both methods
    print("\n============================================")
    print("     FINAL RESPONSES     ")
    print("============================================\n")
    
    print("DETAILED STREAMING FINAL RESPONSE:")
    print("----------------------------------")
    print(response_content or "No response generated")
    
    print("\nSIMPLIFIED STREAMING FINAL RESPONSE:")
    print("----------------------------------")
    print(simple_response or "No response generated")
    
    print("\n============================================")
    print("     TEST COMPLETED SUCCESSFULLY     ")
    print("============================================\n")

if __name__ == "__main__":
    asyncio.run(comprehensive_test()) 