#!/usr/bin/env python3

import getpass
import os
import requests
from typing import Annotated, Literal, Any, Dict, List, Optional
from typing_extensions import TypedDict
import tiktoken

from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_ollama import ChatOllama
from langchain_core.messages import ToolMessage, AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda, RunnableWithFallbacks
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import AnyMessage, add_messages
from pydantic import BaseModel, Field

# --- Prompts ---
query_check_system = """You are a SQL expert with a strong attention to detail.
Double check the SQLite query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins
If there are any of the above mistakes, rewrite the query. If there are no mistakes, just reproduce the original query.

You will call the appropriate tool to execute the query after running this check."""

query_gen_system = """You are a SQL expert with a strong attention to detail.
Given an input question, output a syntactically correct SQLite query to run, then look at the results of the query and return the answer.

DO NOT call any tool besides SubmitFinalAnswer to submit the final answer.

IMPORTANT: For risk-related queries, ALWAYS use the risk_topic column in the Users table. The risk_topic column already 
classifies users into appropriate risk categories. DO NOT try to create complex filters based on other columns.

Risk Topics (these are used in the risk_topic column):
- NO_MFA_USERS: Users with no multi-factor authentication
- WEAK_MFA_USERS: Users with less secure MFA methods like SMS or email
- INACTIVE_USERS: Users who haven't logged in for a long period
- NEVER_LOGGED_IN_USERS: Users who never logged in
- PARTIALLY_OFFBOARDED_USERS: Offboarded users who still have access
- SERVICE_ACCOUNTS: Non-human service accounts
- LOCAL_ACCOUNTS: Accounts local to a specific system
- RECENTLY_JOINED_USERS: Recently created user accounts

enforce risk by using WHERE risk_topic = <'RiskTopic'>

When generating the query:
Output the SQL query that answers the input question without a tool call.
Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results.
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for the relevant columns given the question.

If you get an error while executing a query, rewrite the query and try again.
If you get an empty result set, you should try to rewrite the query to get a non-empty result set.
NEVER make stuff up if you don't have enough information to answer the query... just say you don't have enough information.

If you have enough information to answer the input question, simply invoke the appropriate tool to submit the final answer to the user.
DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.

Enumerated Filters:
Status: active, inactive, offboarded
MFAStatus: none, sms, authenticator_app, hardware_security_key, biometric, push_notification, email
AccountType: regular, service, local
Department: Engineering, IT, Finance, Marketing, Sales, HR
Position: (e.g.) Software Engineer, IT Manager, Accountant, DevOps Engineer, etc.
"""

schema_system_prompt = """You are a database assistant. 
Your task is to identify which tables might be relevant to the user's query and retrieve their schema.


After seeing the list of tables, you need to:
1. Identify which tables are likely relevant to the user's question
2. For EACH relevant table, use the sql_db_schema tool to fetch its schema information
3. Make a separate tool call for EACH table you need information about

DO NOT try to answer the query directly - just get the schema information needed.
"""

# --- Define the State TypedDict ---
class IAMAgentState(TypedDict):
    """State for the IAM Agent workflow."""
    # Core state
    messages: Annotated[List[AnyMessage], add_messages]  # Conversation history
    
    # Error handling
    error: Optional[str]  # Error message if any operation fails
    
    # Database metadata
    table_list: Optional[str]  # List of tables in the database
    schema_info: Optional[Dict[str, str]]  # Schema information for relevant tables
    
    # Query processing
    current_query: Optional[str]  # Current SQL query being processed
    query_result: Optional[str]  # Result of the executed query
    
    # Workflow tracking
    last_tool_call_id: Optional[str]  # ID of the last tool call
    has_final_answer: bool  # Whether a final answer has been submitted

def debug_state(state_dict: IAMAgentState, node_name=None) -> IAMAgentState:
    """Debug function to print state information"""
    print(f"\n==== DEBUG STATE {'for ' + node_name if node_name else ''} ====")
    
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

db = SQLDatabase.from_uri("sqlite:///risk_views.db")

# --- Utility Functions ---
def handle_tool_error(state: IAMAgentState) -> Dict[str, List[ToolMessage]]:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\nPlease fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }

def create_tool_node_with_fallback(tools: List[Any]) -> RunnableWithFallbacks[Any, dict]:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)],
        exception_key="error"
    )

# --- Define Tools ---
toolkit = SQLDatabaseToolkit(db=db, llm= ChatOllama(model="llama3.2-ctx4000", num_ctx=4000))
tools = toolkit.get_tools()
list_tables_tool = next(t for t in tools if t.name == "sql_db_list_tables")
get_schema_tool = next(t for t in tools if t.name == "sql_db_schema")

@tool
def db_query_tool(query: str) -> Any:
    """Execute a SQL query against the IAM risk database and return the results.
    
    Args:
        query: The SQL query string to execute
        
    Returns:
        The query results or an error message if the query failed
    """
    result = db.run_no_throw(query)
    if not result:
        return "Error: Query failed. Please rewrite your query and try again."
    return result

# --- Step 1: List Tables ---
def list_tables_node(state: IAMAgentState) -> Dict[str, Any]:
    """First node that initiates the listing of database tables."""
    # Create a tool call to list the tables
    tool_call_id = "list_tables_call_id"
    
    result = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[{"name": "sql_db_list_tables", "args": {}, "id": tool_call_id}],
            )
        ],
        "last_tool_call_id": tool_call_id
    }
    return debug_state(result, "list_tables_node")

# --- Step 2: Schema Retrieval ---
schema_prompt = ChatPromptTemplate.from_messages([
    ("system", schema_system_prompt),
    ("human", "I need to find information about {question}. Here are the available tables: {tables}"),
])

def get_schema_node(state: IAMAgentState) -> Dict[str, Any]:
    """Identify relevant tables and get their schema."""
    # Extract the question from the first message
    question = ""
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            question = msg.content
            break
    
    # Get the table list from the last tool message
    tables = ""
    last_tool_call_id = state.get("last_tool_call_id", "list_tables_call_id")
    for msg in reversed(state["messages"]):
        if isinstance(msg, ToolMessage) and msg.tool_call_id == last_tool_call_id:
            tables = msg.content
            break
    
    # Update the state with the table list
    result = {"table_list": tables}
    
    # Use the model to identify relevant tables
    llm = ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
    llm_with_tools = llm.bind_tools([get_schema_tool], tool_choice="required")
    
    # Invoke the model to identify tables and make tool calls
    response = llm_with_tools.invoke(
        schema_prompt.format(question=question, tables=tables)
    )
    
    # Add the response to the result
    result["messages"] = [response]
    
    # Update the last tool call ID if available
    if hasattr(response, "tool_calls") and response.tool_calls:
        result["last_tool_call_id"] = response.tool_calls[0].get("id", "")
    
    return debug_state(result, "get_schema_node")

# --- Step 3: Query Generation ---
query_gen_prompt = ChatPromptTemplate.from_messages([
    ("system", query_gen_system),
    ("placeholder", "{messages}"),
])

query_gen = (
    query_gen_prompt
    | ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
)

def query_gen_node(state: IAMAgentState) -> Dict[str, Any]:
    """Generate a SQL query based on the collected schema information."""
    print("\nRunning query_gen_node...")
    try:
        # Check if we have schema information
        has_schema = False
        schema_info = state.get("schema_info", {})
        
        for msg in state["messages"]:
            if isinstance(msg, ToolMessage) and "CREATE TABLE" in msg.content:
                has_schema = True
                
                # Store schema information if not already stored
                if not schema_info:
                    tool_call_id = msg.tool_call_id
                    table_name = None
                    
                    # Try to extract table name from the schema
                    content = msg.content
                    if "CREATE TABLE" in content:
                        import re
                        match = re.search(r'CREATE TABLE (\w+)', content)
                        if match:
                            table_name = match.group(1)
                    
                    if table_name and tool_call_id:
                        if "schema_info" not in state:
                            schema_info = {}
                        schema_info[table_name] = content
        
        result = {"schema_info": schema_info}
        
        # If we have schema info and no previous queries, generate a SQL query
        if has_schema:
            # Use the model to generate the query
            response = query_gen.invoke(state)
            
            # Check if response contains a SQL query (it should be in the content)
            query = response.content.strip()
            if "SELECT" in query:
                # Found a SQL query, create a tool call to execute it
                tool_call_id = "execute_query_id"
                result["messages"] = [
                    AIMessage(
                        content="",
                        tool_calls=[{
                            "name": "db_query_tool", 
                            "args": {"query": query},
                            "id": tool_call_id
                        }]
                    )
                ]
                result["current_query"] = query
                result["last_tool_call_id"] = tool_call_id
                # Explicitly set has_final_answer to False when generating a query
                result["has_final_answer"] = False
                return debug_state(result, "query_gen_node - SQL generated")
        
        # If we have query results, generate a final answer
        has_results = False
        query_result = state.get("query_result", "")
        
        for msg in reversed(state["messages"]):
            if isinstance(msg, ToolMessage) and msg.tool_call_id == "execute_query_id" and not msg.content.startswith("Error:"):
                has_results = True
                query_result = msg.content
                break
        
        if has_results:
            # We have results, so generate a final answer
            llm = ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
            llm_with_tools = llm.bind_tools([SubmitFinalAnswer], tool_choice="required")
            
            response = llm_with_tools.invoke(
                query_gen_prompt.format(messages=state["messages"])
            )
            
            result["messages"] = [response]
            result["query_result"] = query_result
            
            # Check if it's a final answer tool call or just text response
            if hasattr(response, "tool_calls") and response.tool_calls:
                result["has_final_answer"] = any(tc.get("name") == "SubmitFinalAnswer" for tc in response.tool_calls)
            else:
                # If we got a plain text response, convert it to a SubmitFinalAnswer tool call
                tool_call_id = "final_answer_id"
                result["messages"] = [
                    AIMessage(
                        content="",
                        tool_calls=[{
                            "name": "SubmitFinalAnswer", 
                            "args": {"final_answer": response.content},
                            "id": tool_call_id
                        }]
                    )
                ]
                result["has_final_answer"] = True
            
            return debug_state(result, "query_gen_node - final answer")
        
        # Default case - process the model's output
        response = query_gen.invoke(state)
        
        # Check if the response contains a SQL query in plain text
        content = response.content.strip()
        if "SELECT" in content and not (hasattr(response, "tool_calls") and response.tool_calls):
            # Convert SQL in plain text to a proper db_query_tool call
            tool_call_id = "execute_query_id"
            result["messages"] = [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "db_query_tool", 
                        "args": {"query": content},
                        "id": tool_call_id
                    }]
                )
            ]
            result["current_query"] = content
            result["last_tool_call_id"] = tool_call_id
            result["has_final_answer"] = False
            return debug_state(result, "query_gen_node - SQL converted to tool call")
        
        # Handle normal response with or without tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            result["messages"] = [response]
            result["has_final_answer"] = any(
                tc.get("name") == "SubmitFinalAnswer" 
                for tc in response.tool_calls
            )
            
            # Check if it contains a new query
            for tc in response.tool_calls:
                if tc.get("name") == "db_query_tool":
                    result["current_query"] = tc.get("args", {}).get("query", "")
                    result["last_tool_call_id"] = tc.get("id", "")
                    result["has_final_answer"] = False  # Explicitly not final if generating a query
                    break
        else:
            # If we got a plain text response, convert it to a SubmitFinalAnswer tool call
            tool_call_id = "final_answer_id"
            result["messages"] = [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "SubmitFinalAnswer", 
                        "args": {"final_answer": response.content},
                        "id": tool_call_id
                    }]
                )
            ]
            result["has_final_answer"] = True
                    
        return debug_state(result, "query_gen_node - default")
        
    except Exception as e:
        print(f"Error in query_gen_node: {e}")
        import traceback
        traceback.print_exc()
        result = {"error": str(e)}
        return debug_state(result, "query_gen_node - error")

# --- Step 4: Query Checking ---
query_check_prompt = ChatPromptTemplate.from_messages([
    ("system", query_check_system),
    ("placeholder", "{messages}"), 
])

query_check = (
    ChatPromptTemplate.from_messages([
        ("system", query_check_system),
        ("human", "{query}"),
    ])
    | ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
)

def check_query_node(state: IAMAgentState) -> Dict[str, Any]:
    """Check and validate SQL queries before execution."""
    print("\nRunning check_query_node...")
    
    # Get the current query from the state
    query = state.get("current_query", "")
    tool_call_id = ""
    
    # If no query in state, find it in the messages
    if not query:
        for msg in reversed(state["messages"]):
            if hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    if tc.get("name") == "db_query_tool":
                        query = tc.get("args", {}).get("query", "")
                        tool_call_id = tc.get("id", "")
                        break
                if query:
                    break
    
    if not query:
        # No query to check, pass through
        return {"messages": state["messages"][-1:]}
    
    try:
        # Use the SQL checker to validate the query
        llm = ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
        
        # Extract the query and check it
        check_result = query_check.invoke({"query": query})
        
        # Get the checked query from the content
        llm_response = check_result.content
        
        # Extract just the SQL query from the potentially verbose response
        # First try to find a query block with SELECT statement
        import re
        sql_pattern = re.compile(r'SELECT\s+.*?(?=;|\Z)', re.IGNORECASE | re.DOTALL)
        sql_matches = sql_pattern.findall(llm_response)
        
        if sql_matches:
            # Use the last (most likely corrected) SQL query found
            checked_query = sql_matches[-1].strip()
        else:
            # Fallback: If no clear SQL pattern, use the original query
            # This is safer than using potentially non-SQL text
            print("Warning: Could not extract SQL query from LLM response. Using original query.")
            checked_query = query
            
        print(f"Original query: {query}")
        print(f"Extracted checked query: {checked_query}")
        
        # Create a new tool call with the checked query
        new_tool_call_id = "checked_query_id"
        result = {
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "db_query_tool",
                        "args": {"query": checked_query},
                        "id": new_tool_call_id
                    }]
                )
            ],
            "current_query": checked_query,
            "last_tool_call_id": new_tool_call_id
        }
        return debug_state(result, "check_query_node")
    except Exception as e:
        print(f"Error in check_query_node: {e}")
        import traceback
        traceback.print_exc()
        result = {"error": str(e)}
        return debug_state(result, "check_query_node - error")

# --- Final Answer ---
class SubmitFinalAnswer(BaseModel):
    final_answer: str = Field(..., description="The final answer to the user")

# --- Workflow Definition ---
# Create the state graph
workflow = StateGraph(IAMAgentState)

# Add all nodes
workflow.add_node("list_tables", list_tables_node)
workflow.add_node("list_tables_tool", create_tool_node_with_fallback([list_tables_tool]))
workflow.add_node("get_schema", get_schema_node)
workflow.add_node("get_schema_tool", create_tool_node_with_fallback([get_schema_tool]))
workflow.add_node("query_gen", query_gen_node)
workflow.add_node("check_query", check_query_node)
workflow.add_node("execute_query", create_tool_node_with_fallback([db_query_tool]))

# Define conditional routing based on state
def should_continue(state: IAMAgentState) -> Literal[END, "check_query", "query_gen"]:
    """Determine the next step based on the current state."""
    messages = state["messages"]
    last = messages[-1]
    
    # If we have a final answer, we're done
    has_final_answer = state.get("has_final_answer", False)
    if has_final_answer or (hasattr(last, "tool_calls") and any(tc.get("name") == "SubmitFinalAnswer" for tc in last.tool_calls)):
        print("\nSubmitFinalAnswer detected - ending conversation")
        return END
    
    # If the last message is plain text with content (not a tool call), we're done
    if isinstance(last, AIMessage) and hasattr(last, "content") and last.content.strip() and not (hasattr(last, "tool_calls") and last.tool_calls):
        print("\nText response detected - ending conversation")
        return END
    
    # If we have a SQL query, we need to check it
    current_query = state.get("current_query", "")
    if current_query or (hasattr(last, "tool_calls") and any(tc.get("name") == "db_query_tool" for tc in last.tool_calls)):
        print("\nSQL query detected - routing to check_query")
        return "check_query"
    
    # If we have an error from the database, go back to query generation
    if isinstance(last, ToolMessage) and last.content.startswith("Error:"):
        print("\nError detected - routing back to query_gen")
        return "query_gen"
    
    # Default case - we're done
    print("\nNo special conditions - ending conversation")
    return END

# Function to decide where to go after query execution
def after_query_execution(state: IAMAgentState) -> Literal[END, "query_gen"]:
    """Determine whether to end or continue after executing a query."""
    messages = state["messages"]
    last = messages[-1]
    
    # Check if we should terminate based on same conditions as should_continue
    has_final_answer = state.get("has_final_answer", False)
    if has_final_answer or (hasattr(last, "tool_calls") and any(tc.get("name") == "SubmitFinalAnswer" for tc in last.tool_calls)):
        print("\nSubmitFinalAnswer detected after query execution - ending conversation")
        return END
        
    # If the last message is plain text with content (not a tool call), we're done
    if isinstance(last, AIMessage) and hasattr(last, "content") and last.content.strip() and not (hasattr(last, "tool_calls") and last.tool_calls):
        print("\nText response detected after query execution - ending conversation")
        return END
    
    # Continue to query_gen for further processing
    print("\nContinuing to query_gen after query execution")
    return "query_gen"

# Define the workflow edges
workflow.add_edge(START, "list_tables")
workflow.add_edge("list_tables", "list_tables_tool")
workflow.add_edge("list_tables_tool", "get_schema")
workflow.add_edge("get_schema", "get_schema_tool") 
workflow.add_edge("get_schema_tool", "query_gen")
workflow.add_conditional_edges("query_gen", should_continue)
workflow.add_edge("check_query", "execute_query")
# Replace the direct edge with a conditional edge
workflow.add_conditional_edges("execute_query", after_query_execution)

# Compile the graph
app = workflow.compile()

# --- Run Example ---
if __name__ == "__main__":
    from IPython.display import Image, display
    from langchain_core.runnables.graph import MermaidDrawMethod
   
    question = "how many inactive users in engneering?"
    print(f"Question: {question}")
    
    events = []
    for evt in app.stream({"messages": [HumanMessage(content=question)]}):
        print(f"\n--- Event: {evt.get('type', 'unknown')} ---")
        if "messages" in evt:
            for msg in evt["messages"]:
                if hasattr(msg, "content") and msg.content:
                    print(f"Message content: {msg.content}")
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    print(f"Tool calls: {msg.tool_calls}")
                if hasattr(msg, "tool_call_id") and msg.tool_call_id:
                    print(f"Tool call ID: {msg.tool_call_id}")
        events.append(evt)
    
    # Get final result
    result = app.invoke({"messages": [HumanMessage(content=question)]})
    print("\n=== Final Result ===")
    for msg in result["messages"]:
        print(f"Message type: {type(msg).__name__}")
        if hasattr(msg, "content") and msg.content:
            print(f"Content: {msg.content}")
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            print(f"Tool calls: {msg.tool_calls}")
    
    # Extract the final answer if available
    try:
        final = result["messages"][-1].tool_calls[0]["args"]["final_answer"]
        print(f"\nFinal Answer: {final}")
    except (IndexError, KeyError, AttributeError) as e:
        print(f"\nError extracting final answer: {e}")
        print("Last message:", result["messages"][-1] if result["messages"] else "No messages")


