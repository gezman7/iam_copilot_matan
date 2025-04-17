#!/usr/bin/env python3

from typing import Annotated, Literal, Any, Dict, List, Optional, Tuple, Union
from typing_extensions import TypedDict
import tiktoken
import re
from enum import Enum
import traceback

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

# Import prompts from prompt.py
from prompt import query_check_system, query_gen_system, schema_system_prompt

# --- Constants ---
class ToolIds(str, Enum):
    DB_METADATA = "db_metadata_id"
    EXECUTE_QUERY = "execute_query_id"
    CHECK_QUERY = "checked_query_id"
    FINAL_ANSWER = "final_answer_id"

class NodeNames(str, Enum):
    GET_DB_METADATA = "get_db_metadata"
    DB_METADATA_TOOL = "db_metadata_tool"
    QUERY_GEN = "query_gen"
    CHECK_QUERY = "check_query"
    EXECUTE_QUERY = "execute_query"

# --- State Definition ---
class IAMAgentState(TypedDict):
    """State for the IAM Agent workflow."""
    # Core state
    messages: Annotated[List[AnyMessage], add_messages]  # Conversation history
    
    # Error handling
    error: Optional[str]  # Error message if any operation fails
    
    # Database metadata
    db_metadata: Optional[str]  # Database metadata (tables and user schema)
    
    # Query processing
    current_query: Optional[str]  # Current SQL query being processed
    query_result: Optional[str]  # Result of the executed query
    
    # Workflow tracking
    last_tool_call_id: Optional[str]  # ID of the last tool call
    has_final_answer: bool  # Whether a final answer has been submitted

# --- Debug utilities ---
DEBUG_ENABLED = True  # Set to False in production

def debug_state(state_dict: IAMAgentState, node_name=None) -> IAMAgentState:
    """Debug function to print state information. No-op if debugging disabled."""
    if not DEBUG_ENABLED:
        return state_dict
        
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

# --- Database Setup ---
db = SQLDatabase.from_uri("sqlite:///risk_views.db")

# --- State Helper Functions ---
def extract_user_question(state: IAMAgentState) -> str:
    """Extract the user's question from messages."""
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""

def extract_query_from_state(state: IAMAgentState) -> Tuple[str, str]:
    """Extract query and tool_call_id from state or messages."""
    # Check if query is already in state
    query = state.get("current_query", "")
    tool_call_id = ""
    
    # If no query in state, find it in the messages
    if not query:
        for msg in reversed(state["messages"]):
            if hasattr(msg, "tool_calls"):
                for tc in msg.tool_calls:
                    if tc.get("name") == "sql_db_query":
                        query = tc.get("args", {}).get("query", "")
                        tool_call_id = tc.get("id", "")
                        break
                if query:
                    break
    
    return query, tool_call_id

def extract_query_results(state: IAMAgentState) -> Tuple[bool, str]:
    """Extract query results from state messages."""
    has_results = False
    query_result = state.get("query_result", "")
    
    for msg in reversed(state["messages"]):
        if (isinstance(msg, ToolMessage) and 
            msg.tool_call_id == ToolIds.EXECUTE_QUERY and 
            not msg.content.startswith("Error:")):
            has_results = True
            query_result = msg.content
            break
    
    return has_results, query_result

def has_db_metadata(state: IAMAgentState) -> bool:
    """Check if state has database metadata information."""
    return state.get("db_metadata") is not None

def is_final_answer(state: IAMAgentState) -> bool:
    """Check if state has a final answer."""
    # Check the has_final_answer flag
    if state.get("has_final_answer", False):
        return True
        
    # Check the last message for SubmitFinalAnswer tool calls
    messages = state["messages"]
    if not messages:
        return False
        
    last = messages[-1]
    if hasattr(last, "tool_calls") and any(tc.get("name") == "SubmitFinalAnswer" for tc in last.tool_calls):
        return True
        
    return False

def is_plaintext_response(state: IAMAgentState) -> bool:
    """Check if the last message is a plain text response."""
    messages = state["messages"]
    if not messages:
        return False
        
    last = messages[-1]
    return (isinstance(last, AIMessage) and 
            hasattr(last, "content") and 
            last.content.strip() and 
            not (hasattr(last, "tool_calls") and last.tool_calls))

def has_db_error(state: IAMAgentState) -> bool:
    """Check if the last message indicates a database error."""
    messages = state["messages"]
    if not messages:
        return False
        
    last = messages[-1]
    return isinstance(last, ToolMessage) and last.content.startswith("Error:")

def has_sql_query(state: IAMAgentState) -> bool:
    """Check if state contains an SQL query."""
    # Check if current_query exists in state
    if state.get("current_query", ""):
        return True
        
    # Check if the last message has a sql_db_query call
    messages = state["messages"]
    if not messages:
        return False
        
    last = messages[-1]
    return (hasattr(last, "tool_calls") and 
            any(tc.get("name") == "sql_db_query" for tc in last.tool_calls))

# --- Utility Functions ---
def handle_tool_error(state: IAMAgentState) -> Dict[str, List[ToolMessage]]:
    """Handle errors from tool calls."""
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
    """Create a tool node with error handling fallback."""
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)],
        exception_key="error"
    )

def create_tool_call_message(tool_name: str, args: Dict[str, Any], tool_id: str) -> AIMessage:
    """Create a standardized tool call message."""
    return AIMessage(
        content="",
        tool_calls=[{
            "name": tool_name, 
            "args": args,
            "id": tool_id
        }]
    )

def extract_sql_from_llm_response(response_text: str, original_query: str) -> str:
    """Extract SQL query from LLM response or fallback to original query."""
    sql_pattern = re.compile(r'SELECT\s+.*?(?=;|\Z)', re.IGNORECASE | re.DOTALL)
    sql_matches = sql_pattern.findall(response_text)
    
    if sql_matches:
        # Use the last (most likely corrected) SQL query found
        return sql_matches[-1].strip()
    else:
        # Fallback: Use the original query
        print("Warning: Could not extract SQL query from LLM response. Using original query.")
        return original_query

# --- Custom Tool for DB Metadata ---
@tool
def get_db_metadata_tool() -> str:
    """Get the database metadata including table list and the user table schema."""
    # Get the list of all tables
    tables = db.get_usable_table_names()
    table_list = ", ".join(tables)
    
    # Get the schema for the users table (for IAM focus)
    user_schema = db.get_table_info(["users"]) if "users" in tables else "User table not found."
    
    return f"Available tables: {table_list}\n\nUser Table Schema:\n{user_schema}"

# --- Define Standard Tools ---
toolkit = SQLDatabaseToolkit(db=db, llm=ChatOllama(model="llama3.2-ctx4000", num_ctx=4000))
tools = toolkit.get_tools()
db_query_tool = next((t for t in tools if t.name == "sql_db_query"), None)
if not db_query_tool:
    @tool(name="sql_db_query")
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

# --- Node Implementations ---
def get_db_metadata_node(state: IAMAgentState) -> Dict[str, Any]:
    """Get database metadata focusing on the users table for identity management."""
    result = {
        "messages": [create_tool_call_message("get_db_metadata_tool", {}, ToolIds.DB_METADATA)],
        "last_tool_call_id": ToolIds.DB_METADATA
    }
    return debug_state(result, NodeNames.GET_DB_METADATA)

# --- Query Generation ---
query_gen_prompt = ChatPromptTemplate.from_messages([
    ("system", query_gen_system),
    ("placeholder", "{messages}"),
])

query_gen = (
    query_gen_prompt
    | ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
)

def generate_sql_query(state: IAMAgentState) -> Dict[str, Any]:
    """Generate a SQL query based on database metadata."""
    try:
        # Use the model to generate the query
        response = query_gen.invoke(state)
        
        # Extract and process query from response
        query = response.content.strip()
        if "SELECT" in query:
            # Found a SQL query, create a tool call
            result = {
                "messages": [create_tool_call_message(
                    "sql_db_query", 
                    {"query": query}, 
                    ToolIds.EXECUTE_QUERY
                )],
                "current_query": query,
                "last_tool_call_id": ToolIds.EXECUTE_QUERY,
                "has_final_answer": False
            }
            return result
        
        return {"messages": [response]}
        
    except Exception as e:
        print(f"Error generating SQL query: {e}")
        return {"error": str(e)}

def generate_final_answer(state: IAMAgentState, query_result: str) -> Dict[str, Any]:
    """Generate a final answer based on query results."""
    try:
        # Generate a final answer using the model
        llm = ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
        llm_with_tools = llm.bind_tools([SubmitFinalAnswer], tool_choice="required")
        
        response = llm_with_tools.invoke(
            query_gen_prompt.format(messages=state["messages"])
        )
        
        result = {
            "messages": [response],
            "query_result": query_result
        }
        
        # Check if it's a tool call or text response
        if hasattr(response, "tool_calls") and response.tool_calls:
            result["has_final_answer"] = any(
                tc.get("name") == "SubmitFinalAnswer" for tc in response.tool_calls
            )
        else:
            # Convert text response to a tool call
            result["messages"] = [create_tool_call_message(
                "SubmitFinalAnswer", 
                {"final_answer": response.content}, 
                ToolIds.FINAL_ANSWER
            )]
            result["has_final_answer"] = True
        
        return result
    
    except Exception as e:
        print(f"Error generating final answer: {e}")
        return {"error": str(e)}

def handle_llm_response(state: IAMAgentState, response: AIMessage) -> Dict[str, Any]:
    """Process and handle general LLM responses."""
    result = {}
    
    # Handle plain text with SQL pattern (convert to tool call)
    content = response.content.strip()
    if "SELECT" in content and not (hasattr(response, "tool_calls") and response.tool_calls):
        result["messages"] = [create_tool_call_message(
            "sql_db_query", 
            {"query": content}, 
            ToolIds.EXECUTE_QUERY
        )]
        result["current_query"] = content
        result["last_tool_call_id"] = ToolIds.EXECUTE_QUERY
        result["has_final_answer"] = False
        return result
    
    # Handle normal response with tool calls
    if hasattr(response, "tool_calls") and response.tool_calls:
        result["messages"] = [response]
        
        # Check for final answer or db query tools
        result["has_final_answer"] = any(
            tc.get("name") == "SubmitFinalAnswer" for tc in response.tool_calls
        )
        
        for tc in response.tool_calls:
            if tc.get("name") == "sql_db_query":
                result["current_query"] = tc.get("args", {}).get("query", "")
                result["last_tool_call_id"] = tc.get("id", "")
                result["has_final_answer"] = False
                break
    else:
        # Convert text to final answer
        result["messages"] = [create_tool_call_message(
            "SubmitFinalAnswer", 
            {"final_answer": response.content}, 
            ToolIds.FINAL_ANSWER
        )]
        result["has_final_answer"] = True
    
    return result

def query_gen_node(state: IAMAgentState) -> Dict[str, Any]:
    """Generate SQL query, final answer, or handle model response."""
    print("\nRunning query_gen_node...")
    try:
        # Store DB metadata if it exists in messages but not state
        for msg in state["messages"]:
            if isinstance(msg, ToolMessage) and msg.tool_call_id == ToolIds.DB_METADATA:
                state["db_metadata"] = msg.content
                break
        
        # Check if we have DB metadata and query results
        has_metadata = has_db_metadata(state)
        has_results, query_result = extract_query_results(state)
        
        result = {}
        
        # Decision logic
        if has_metadata and not has_results:
            # Generate a SQL query
            query_result = generate_sql_query(state)
            result.update(query_result)
            return debug_state(result, f"{NodeNames.QUERY_GEN} - SQL generated")
        
        elif has_results:
            # Generate a final answer
            answer_result = generate_final_answer(state, query_result)
            result.update(answer_result)
            return debug_state(result, f"{NodeNames.QUERY_GEN} - final answer")
        
        else:
            # Default case - process model output
            response = query_gen.invoke(state)
            response_result = handle_llm_response(state, response)
            result.update(response_result)
            return debug_state(result, f"{NodeNames.QUERY_GEN} - default")
            
    except Exception as e:
        print(f"Error in query_gen_node: {e}")
        traceback.print_exc()
        return debug_state({"error": str(e)}, f"{NodeNames.QUERY_GEN} - error")

# --- Query Checking ---
query_check_prompt = ChatPromptTemplate.from_messages([
    ("system", query_check_system),
    ("human", "{query}"),
])

query_check = query_check_prompt | ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)

def check_query_node(state: IAMAgentState) -> Dict[str, Any]:
    """Check and validate SQL queries before execution."""
    print("\nRunning check_query_node...")
    
    # Get the current query
    query, _ = extract_query_from_state(state)
    
    if not query:
        # No query to check, pass through
        return {"messages": state["messages"][-1:]}
    
    try:
        # Use the SQL checker to validate the query
        check_result = query_check.invoke({"query": query})
        
        # Extract query from LLM response
        llm_response = check_result.content
        checked_query = extract_sql_from_llm_response(llm_response, query)
        
        print(f"Original query: {query}")
        print(f"Extracted checked query: {checked_query}")
        
        # Create a new tool call with the checked query
        result = {
            "messages": [create_tool_call_message(
                "sql_db_query", 
                {"query": checked_query}, 
                ToolIds.CHECK_QUERY
            )],
            "current_query": checked_query,
            "last_tool_call_id": ToolIds.CHECK_QUERY
        }
        return debug_state(result, NodeNames.CHECK_QUERY)
    except Exception as e:
        print(f"Error in check_query_node: {e}")
        traceback.print_exc()
        return debug_state({"error": str(e)}, f"{NodeNames.CHECK_QUERY} - error")

# --- Final Answer ---
class SubmitFinalAnswer(BaseModel):
    final_answer: str = Field(..., description="The final answer to the user")

# --- Routing Logic ---
def determine_next_step(state: IAMAgentState) -> Literal[END, str]:
    """Unified routing logic for the workflow."""
    # Check for termination conditions
    if is_final_answer(state) or is_plaintext_response(state):
        print("\nFinal answer or text response detected - ending conversation")
        return END
    
    # Check for SQL queries that need validation
    if has_sql_query(state):
        print("\nSQL query detected - routing to check_query")
        return NodeNames.CHECK_QUERY
    
    # Check for database errors
    if has_db_error(state):
        print("\nError detected - routing back to query_gen")
        return NodeNames.QUERY_GEN
    
    # Default case - we're done
    print("\nNo special conditions - ending conversation")
    return END

# --- Workflow Definition ---
workflow = StateGraph(IAMAgentState)

# Add all nodes
workflow.add_node("get_db_metadata", get_db_metadata_node)
workflow.add_node("db_metadata_tool", create_tool_node_with_fallback([get_db_metadata_tool]))
workflow.add_node("query_gen", query_gen_node)
workflow.add_node("check_query", check_query_node)
workflow.add_node("execute_query", create_tool_node_with_fallback([db_query_tool]))

# Define the workflow edges - simplified
workflow.add_edge(START, "get_db_metadata")
workflow.add_edge("get_db_metadata", "db_metadata_tool")
workflow.add_edge("db_metadata_tool", "query_gen")
workflow.add_conditional_edges(
    "query_gen", 
    lambda state: END if is_final_answer(state) or is_plaintext_response(state) 
    else "check_query" if has_sql_query(state)
    else "query_gen" if has_db_error(state)
    else END
)
workflow.add_edge("check_query", "execute_query")
workflow.add_conditional_edges(
    "execute_query", 
    lambda state: END if is_final_answer(state) or is_plaintext_response(state) else "query_gen"
)

# Compile the graph
app = workflow.compile()

# --- Run Example ---
if __name__ == "__main__":
    from IPython.display import Image, display
    from langchain_core.runnables.graph import MermaidDrawMethod
   
    question = "Do we have any users that are partialy offboared?"
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


