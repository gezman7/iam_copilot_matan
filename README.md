# IAM Copilot with Conversation Support

This project implements an IAM (Identity and Access Management) security copilot that analyzes risk data using natural language queries with conversation support.

## Features

- **Conversational Interface**: The copilot maintains conversation history using LangGraph's MemorySaver, allowing for contextual follow-up questions.
- **Message Trimming**: Implements LangChain's trim_messages functionality to manage context window size.
- **Security Recommendations**: Provides specific security recommendations for different IAM risk types.
- **Streaming Responses**: Supports streaming responses for a more interactive experience.
- **SQL Query Analysis**: Analyzes and executes SQL queries with built-in security checks.

## Conversation Support Implementation

### Memory Persistence

The copilot uses LangGraph's `MemorySaver` for conversation persistence across queries:

```python
from langgraph.checkpoint.memory import MemorySaver

# Initialize memory saver for conversation persistence
self.memory = MemorySaver()

# Compile graph with memory checkpointer
return workflow.compile(checkpointer=self.memory)
```

### Message Trimming

To manage the context window size as conversations grow longer, we implemented `trim_messages` functionality:

```python
def trim_message_history(messages):
    """Trim message history to manage context window"""
    return trim_messages(
        messages,
        # Max number of messages to keep
        max_tokens=10,
        # Simply count the number of messages rather than tokens
        token_counter=len,
        # Keep most recent messages
        strategy="last",
        # Ensure the conversation flow makes sense
        start_on="human",
        # Always keep the system message for instructions
        include_system=True,
        # Don't split messages in the middle
        allow_partial=False
    )
```

### Thread-based Conversations

Each conversation is assigned a thread ID, allowing multiple independent conversations:

```python
# Set up configuration with thread_id for conversation persistence
config = {"configurable": {"thread_id": thread_id}}
```

## Usage

```python
from src.Iam_copilot import IAMCopilot

# Create IAMCopilot instance
copilot = IAMCopilot(db_path="iam_risks.db")

# Use a unique thread ID for this conversation
thread_id = "conversation-1"

# Initial query
result1 = copilot.process_query("How many users have weak MFA?", thread_id)

# Follow-up query using the same thread_id
result2 = copilot.process_query("Which department has the most users with this issue?", thread_id)

# Ask for security recommendations based on the conversation context
result3 = copilot.process_query("What security recommendations do you have for these weak MFA users?", thread_id)
```

## Streaming Example

```python
import asyncio

async def stream_example():
    # Create IAMCopilot instance
    copilot = IAMCopilot(db_path="iam_risks.db")
    
    # Use a unique thread ID for this conversation
    thread_id = "conversation-1"
    
    # Stream initial query
    async for event in copilot.stream_query("How many users have weak MFA?", thread_id):
        if "messages" in event and event["messages"]:
            last_message = event["messages"][-1]
            if hasattr(last_message, "content"):
                print(f"AI: {last_message.content}")

# Run the async function
asyncio.run(stream_example())
``` 