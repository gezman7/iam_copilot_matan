# IAM Copilot with Conversation Support

This project implements an IAM (Identity and Access Management) security copilot that analyzes risk data using natural language queries with conversation support.

## Features

- **Conversational Interface**: The copilot maintains conversation history using LangGraph's MemorySaver, allowing for contextual follow-up questions.
- **Message Trimming**: Implements LangChain's trim_messages functionality to manage context window size.
- **Security Recommendations**: Provides specific security recommendations for different IAM risk types.
- **Robust Streaming Capabilities**: Supports multiple streaming modes with fallback mechanisms to ensure compatibility with different LLMs.
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

## Enhanced Streaming Capabilities

The IAM copilot supports different streaming modes with robust fallback mechanisms:

### Basic Streaming

```python
# Stream in values mode (default)
async for event in copilot.stream_query("How many users have weak MFA?", thread_id):
    if "messages" in event and event["messages"]:
        last_message = event["messages"][-1]
        if hasattr(last_message, "content"):
            print(f"AI: {last_message.content}")
```

### Detailed Streaming

For a comprehensive view of the agent's thought process with automatic fallback to simpler modes if needed:

```python
# Stream with detailed information about agent steps
async for event in copilot.stream_with_details("What are the security recommendations?", thread_id):
    event_type = event.get("type", "unknown")
    
    if event_type == "start_steps":
        print("Agent started")
    elif event_type == "step":
        print(f"Running tool: {event.get('name')}")
    elif event_type == "observation":
        print(f"Tool result: {event.get('content')}")
    elif event_type == "response":
        print(f"Final response: {event.get('content')}")
    elif event_type == "fallback":
        print("Switching to simplified streaming mode")
```

### Simplified Streaming

A simplified streaming approach that works with any LLM:

```python
# Stream with simplified approach that works with any LLM
async for event in copilot.stream_simplified("How many users have weak MFA?", thread_id):
    event_type = event.get("type", "unknown")
    content = event.get("content", "")
    
    if event_type == "start":
        print("Starting processing")
    elif event_type == "ai":
        print(f"AI: {content}")
    elif event_type == "tool":
        print(f"Tool: {content}")
    elif event_type == "end":
        print("Processing completed")
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

## Running Tests

To verify the IAM copilot's capabilities, run the test scripts:

```bash
# Test conversational capabilities
python3 test_conversation.py

# Test basic streaming capabilities
python3 test_streaming.py

# Run comprehensive streaming test with fallbacks
python3 test_comprehensive.py
```

# IAM Query Writer Testing System

This system provides a robust way to test the IAM Query Writer's ability to translate natural language queries into SQL statements for Identity and Access Management (IAM) risk analysis.

## Overview

The QueryWriter system has been enhanced with multi-step verification techniques from LangGraph SQL agent architecture:

1. Initial SQL generation from natural language query
2. SQL validation for potential errors
3. Test execution to catch runtime issues
4. Error handling and correction

## Test Framework

The testing framework provides:

- Unit tests for specific components
- Integration tests for end-to-end functionality
- A test data file with various IAM risk scenarios
- Result comparison between expected and actual outputs
- Detailed reporting in multiple formats

## Running Tests

### Unit Tests

To run the unit tests for the QueryWriter:

```bash
python -m unittest src/test_query_writer.py
```

### Integration Tests

To run the integration tests with the test cases:

```bash
python src/test_runner.py
```

#### Command Line Options

- `--test-data PATH`: Path to the test data JSON file (default: test_data/test_cases.json)
- `--verbose`: Enable verbose output
- `--format {text,csv,json,html}`: Output format for the test report (default: text)
- `--output PATH`: Output file path (without extension) for reports

Example:

```bash
python src/test_runner.py --verbose --format html --output reports/test_results
```

## Adding New Test Cases

You can add new test cases to the `test_data/test_cases.json` file. Each test case should include:

- `id`: Unique identifier for the test
- `description`: Brief description of what the test is checking
- `user_query`: The natural language query
- `expected_sql`: The expected SQL output
- `expected_result`: Expected database query results

## Test Case Example

```json
{
  "id": "test_no_mfa",
  "description": "Basic query for users without MFA",
  "user_query": "Show me all users without MFA",
  "expected_sql": "SELECT UserID, Name, Email, Department FROM Users WHERE risk_topic = 'NO_MFA_USERS'",
  "expected_result": [...]
}
```

## Enhanced QueryWriter Features

The updated QueryWriter includes several features inspired by the LangGraph SQL agent:

1. **Multi-step verification process**:
   - Initial SQL generation
   - SQL validation to check for errors
   - Execution testing to catch runtime issues

2. **SQL query validation**:
   - Checks for syntax errors
   - Ensures required risk_topic filters are present
   - Verifies table and column names
   - Reviews join logic
   - Checks GROUP BY clauses for aggregate functions
   - Evaluates query efficiency

3. **Error handling**:
   - Catches runtime errors when executing queries
   - Uses error messages to guide query correction
   - Provides specific error context to the LLM

4. **Query testing**:
   - Tests queries with LIMIT 1 to validate syntax without retrieving large results
   - Preserves existing LIMIT clauses when present

## Requirements

- Python 3.8+
- Required packages:
  - langchain_ollama
  - langchain_core
  - langchain_community
  - pandas
  - tabulate
  - sqlite3 