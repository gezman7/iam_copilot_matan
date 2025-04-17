#!/usr/bin/env python3

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
from enum import Enum
import traceback
import sys
import os

# Add the root directory to the path to make imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Import QueryGraph
from src.query_graph import QueryGraph

# Import prompts from prompt.py

# Import debug utilities
from debug import debug_state

# --- Constants ---
class ToolIds(str, Enum):
    DB_METADATA = "db_metadata_id"
    FINAL_ANSWER = "final_answer_id"

class NodeNames(str, Enum):
    GET_DB_METADATA = "get_db_metadata"
    DB_METADATA_TOOL = "db_metadata_tool"
    QUERY_PROCESSOR = "query_processor"

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

# --- Database Setup ---
db = SQLDatabase.from_uri("sqlite:///risk_views.db")

# --- State Helper Functions ---
def extract_user_question(state: IAMAgentState) -> str:
    """Extract the user's question from messages."""
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""

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

# --- Final Answer ---
class SubmitFinalAnswer(BaseModel):
    final_answer: str = Field(..., description="The final answer to the user")

# --- Query Processor Node ---
def query_processor_node(state: IAMAgentState) -> Dict[str, Any]:
    """Process user query using the QueryGraph."""
    print("\nRunning query_processor_node...")
    
    try:
        # Extract user question
        user_question = extract_user_question(state)
        if not user_question:
            return debug_state({"error": "No user question found"}, NodeNames.QUERY_PROCESSOR)
        
        # Extract DB metadata
        db_metadata = state.get("db_metadata", "")
        if not db_metadata:
            # Try to extract from messages
            for msg in state["messages"]:
                if isinstance(msg, ToolMessage) and msg.tool_call_id == ToolIds.DB_METADATA:
                    db_metadata = msg.content
                    state["db_metadata"] = db_metadata
                    break
        
        if not db_metadata:
            return debug_state({"error": "No database metadata found"}, NodeNames.QUERY_PROCESSOR)
        
        # Create and execute QueryGraph
        query_graph = QueryGraph(db=db, debug=DEBUG_ENABLED)
        result = query_graph.execute(user_question, db_metadata, state["messages"])
        
        # Process result
        if result.get("is_complete") and result.get("query_result"):
            # Query was successful, generate final answer
            llm = ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
            llm_with_tools = llm.bind_tools([SubmitFinalAnswer], tool_choice="required")
            
            # Create prompt for final answer
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful SQL assistant. Given the query results, 
                provide a clear final answer to the user's question."""),
                ("human", f"""
User question: {{user_question}}
Query result: {{query_result}}

Generate a clear and concise final answer.
""")
            ])
            
            # Generate final answer - properly format the prompt first
            response = llm_with_tools.invoke(
                prompt.format(
                    user_question=user_question,
                    query_result=result['query_result']
                )
            )
            
            return debug_state({
                "messages": [response],
                "current_query": result.get("current_query"),
                "query_result": result.get("query_result"),
                "has_final_answer": True
            }, f"{NodeNames.QUERY_PROCESSOR} - final answer")
        elif result.get("error"):
            # Query execution had an error
            return debug_state({
                "error": result.get("error"),
                "messages": [AIMessage(content=f"Error: {result.get('error')}")]
            }, f"{NodeNames.QUERY_PROCESSOR} - error")
        else:
            # Unexpected state
            return debug_state({
                "error": "Unknown error in query processing",
                "messages": [AIMessage(content="Sorry, I encountered an error processing your query.")]
            }, f"{NodeNames.QUERY_PROCESSOR} - unknown")
            
    except Exception as e:
        print(f"Error in query_processor_node: {e}")
        traceback.print_exc()
        return debug_state({
            "error": str(e),
            "messages": [AIMessage(content=f"An error occurred: {str(e)}")]
        }, f"{NodeNames.QUERY_PROCESSOR} - exception")

# --- Routing Logic ---
def determine_next_step(state: IAMAgentState) -> str:
    """Unified routing logic for the workflow."""
    # Check for termination conditions
    if is_final_answer(state) or is_plaintext_response(state):
        print("\nFinal answer or text response detected - ending conversation")
        return "end"
    
    # Check for errors (return END to prevent loops)
    if state.get("error"):
        print("\nError detected - ending conversation")
        return "end"
    
    # Default case - we're done
    print("\nNo special conditions - ending conversation")
    return "end"

# --- Workflow Definition ---
workflow = StateGraph(IAMAgentState)

# Add all nodes
workflow.add_node(NodeNames.GET_DB_METADATA, get_db_metadata_node)
workflow.add_node(NodeNames.DB_METADATA_TOOL, create_tool_node_with_fallback([get_db_metadata_tool]))
workflow.add_node(NodeNames.QUERY_PROCESSOR, query_processor_node)

# Define the workflow edges - simplified
workflow.add_edge(START, NodeNames.GET_DB_METADATA)
workflow.add_edge(NodeNames.GET_DB_METADATA, NodeNames.DB_METADATA_TOOL)
workflow.add_edge(NodeNames.DB_METADATA_TOOL, NodeNames.QUERY_PROCESSOR)
workflow.add_conditional_edges(
    NodeNames.QUERY_PROCESSOR,
    determine_next_step,
    {
        "end": END
    }
)

# Compile the graph
app = workflow.compile()

# --- Run Example ---
if __name__ == "__main__":
    
   
    question = "Do we have any users that are partially offboarded?"
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


