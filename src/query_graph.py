#!/usr/bin/env python3

from typing import Dict, List, Optional, Any
from typing_extensions import TypedDict
from enum import Enum
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import AnyMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_community.utilities import SQLDatabase
from langgraph.graph import StateGraph, START, END

from src.prompt import query_check_system, query_gen_system

from util.sql_parser import extract_sql_from_text

# --- Constants ---
class ToolIds(Enum):
    """Tool IDs used in the workflow."""
    DB_METADATA = "db_metadata_id"
    EXECUTE_QUERY = "execute_query_id"
    CHECK_QUERY = "checked_query_id"
    FINAL_ANSWER = "final_answer_id"

class QueryState(TypedDict):
    """State for the SQL query processing subgraph."""
    # Input state
    user_query: str                          # Original user question
    db_metadata: str                         # Database metadata information
    messages: List[AnyMessage]               # Messages for context
    
    # Processing state
    current_query: Optional[str]             # Current SQL query
    error: Optional[str]                     # Error message if query failed
    retry_count: int                         # Number of retry attempts
    
    # Output state
    query_result: Optional[str]              # Result of the executed query
    is_complete: bool                        # Whether processing is complete

class QueryGraph:
    """A simplified graph for SQL query generation, validation, and execution."""
    
    def __init__(self, db: SQLDatabase, model: str = "llama3.2-ctx4000", ctx_size: int = 4000, debug: bool = False):
        """Initialize the query graph."""
    
        self.db = db
        self.llm = ChatOllama(model=model, num_ctx=ctx_size)
        self.debug = debug
        self.graph = self._build_graph()
    
    def _debug_log(self, message: str, node_name: Optional[str] = None):
        """Print debug information if debug is enabled."""
        if self.debug:
            prefix = f"[{node_name}] " if node_name else ""
            print(f"\n=== DEBUG: {prefix}{message} ===")
    
    def _debug_state(self, state: QueryState, node_name: Optional[str] = None):
        """Print complete state information if debug is enabled."""
        if self.debug:
            prefix = f"[{node_name}] " if node_name else ""
            print(f"\n=== DEBUG STATE: {prefix} ===")
            print("COMPLETE STATE:")
            print(state)
            print("=== END DEBUG STATE ===")
    
    def _create_tool_call(self, name: str, args: Dict[str, Any], tool_id: str) -> AIMessage:
        """Create a standardized tool call message."""
        return AIMessage(
            content="",
            tool_calls=[{
                "name": name,
                "args": args,
                "id": tool_id
            }]
        )
    
    def _query_generator(self, state: QueryState) -> Dict[str, Any]:
        """Generate SQL query based on user question and DB metadata."""
        self._debug_log("Generating SQL query", "generator")
        self._debug_state(state, "generator_input")
        
        try:
            # Create prompt with error context if available
            error_context = ""
            if state.get("error") and state.get("retry_count", 0) > 0:
                error_context = f"Previous query failed with error: {state['error']}\nPlease fix the issues."
            
            # Get conversation history
            messages = state.get("messages", [])
            history_context = ""
            if messages:
                history_context = "\nConversation history:\n"
                for msg in messages:
                    if isinstance(msg, (HumanMessage, AIMessage)):
                        role = "User" if isinstance(msg, HumanMessage) else "Assistant"
                        content = msg.content if hasattr(msg, "content") else ""
                        history_context += f"{role}: {content}\n"
            
            # Define prompt
            prompt = ChatPromptTemplate.from_messages([
                ("system", query_gen_system),
                ("human", f"""
                            Database information:
                            {state['db_metadata']}

                            {history_context}

                            User question: {state['user_query']}

                            {error_context}

                            Generate a SQL query to answer this question.
                            """)
            ])
            
            response = self.llm.invoke(
                prompt.format(
                    db_metadata=state['db_metadata'],
                    user_query=state['user_query'],
                    error_context=error_context,
                    history_context=history_context
                )
            )
            
            # Extract SQL
            content = response.content.strip()
            if "SELECT" in content:
                query = extract_sql_from_text(content)
                
                result = {
                    "current_query": query,
                    "messages": [self._create_tool_call(
                        "sql_db_query", 
                        {"query": query}, 
                        ToolIds.EXECUTE_QUERY
                    )],
                    "is_complete": False
                }
                self._debug_state(result, "generator_output")
                return result
            else:
                # No query found - treat as error
                result = {
                    "error": "Failed to generate SQL query",
                    "is_complete": False
                }
                self._debug_state(result, "generator_output")
                return result
        except Exception as e:
            result = {
                "error": f"Error in query generation: {str(e)}",
                "is_complete": False
            }
            self._debug_state(result, "generator_error")
            return result
    
    def _query_validator(self, state: QueryState) -> Dict[str, Any]:
        """Validate and potentially fix the SQL query."""
        self._debug_log("Validating query", "validator")
        self._debug_state(state, "validator_input")
        
        query = state.get("current_query", "")
        if not query:
            result = {
                "error": "No query to validate",
                "is_complete": False
            }
            self._debug_state(result, "validator_error")
            return result
        
        try:

            # TODO: if i get the position, add validator agent - it's too late now..

            # # Create validation prompt
            # prompt = ChatPromptTemplate.from_messages([
            #     ("system", query_check_system),
            #     ("human", f"Validate this SQL query: {query}")
            # ])
            
            # response = self.llm.invoke(
            #     prompt.format(query=query)
            # )
            
            # Extract validated query
            validated_query = extract_sql_from_text( query)
            
            # Return the validated query for execution
            result = {
                "current_query": validated_query,
                "messages": [self._create_tool_call(
                    "sql_db_query", 
                    {"query": validated_query},
                    ToolIds.EXECUTE_QUERY
                )],
                "is_complete": False
            }
            self._debug_state(result, "validator_output")
            return result
        except Exception as e:
            result = {
                "error": f"Error in query validation: {str(e)}",
                "is_complete": False
            }
            self._debug_state(result, "validator_error")
            return result
    
    def _query_executor(self, state: QueryState) -> Dict[str, Any]:
        """Execute the SQL query."""
        self._debug_log("Executing query", "executor")
        self._debug_state(state, "executor_input")
        
        query = state.get("current_query", "")
        if not query:
            result = {
                "error": "No query to execute",
                "is_complete": False
            }
            self._debug_state(result, "executor_error")
            return result
        
        try:
            # Execute query
            result = self.db.run_no_throw(query)
            
            if result and not result.startswith("Error"):
                # Success
                success_result = {
                    "query_result": result,
                    "is_complete": True
                }
                self._debug_state(success_result, "executor_success")
                return success_result
            else:
                # Query execution failed
                error_result = {
                    "error": f"Query execution failed: {result}",
                    "is_complete": False
                }
                self._debug_state(error_result, "executor_failure")
                return error_result
        except Exception as e:
            error_result = {
                "error": f"Error executing query: {str(e)}",
                "is_complete": False
            }
            self._debug_state(error_result, "executor_exception")
            return error_result
    
    def _error_handler(self, state: QueryState) -> Dict[str, Any]:
        """Handle errors and potentially retry."""
        self._debug_log(f"Handling error: {state.get('error')}", "error_handler")
        self._debug_state(state, "error_handler_input")
        
        # Increment retry count
        retry_count = state.get("retry_count", 0) + 1
        
        # Check retry limit
        if retry_count >= 3:
            result = {
                "retry_count": retry_count,
                "query_result": f"Error: {state.get('error')}. Maximum retries reached.",
                "is_complete": True
            }
            self._debug_state(result, "error_handler_max_retries")
            return result
        
        # Clear current query to force regeneration and continue
        result = {
            "retry_count": retry_count,
            "current_query": None,
            "is_complete": False
        }
        self._debug_state(result, "error_handler_retry")
        return result
    
    def _determine_next(self, state: QueryState) -> str:
        """Determine the next node to execute."""
        self._debug_state(state, "router_input")
        
        # Check if processing is complete
        if state.get("is_complete", False):
            self._debug_log("Processing complete", "router")
            return "end"
        
        # Check for errors
        if state.get("error"):
            self._debug_log("Error detected, routing to error handler", "router")
            return "error_handler"
        
        # Determine based on state
        if not state.get("current_query"):
            self._debug_log("No query, routing to generator", "router")
            return "query_generator"
        else:
            self._debug_log("Query exists, routing to validator", "router")
            return "query_validator"
    
    def _build_graph(self) -> Any:
        """Build and compile the query processing graph."""
        # Create graph
        graph = StateGraph(QueryState)
        
        # Add nodes
        graph.add_node("query_generator", self._query_generator)
        graph.add_node("query_validator", self._query_validator)
        graph.add_node("query_executor", self._query_executor)
        graph.add_node("error_handler", self._error_handler)
        
        # Add edges
        graph.add_edge(START, "query_generator")
        graph.add_edge("query_validator", "query_executor")
        
        # Add conditional edges
        graph.add_conditional_edges(
            "query_generator", 
            self._determine_next,
            {
                "end": END,
                "error_handler": "error_handler",
                "query_generator": "query_generator",
                "query_validator": "query_validator"
            }
        )
        graph.add_conditional_edges(
            "query_executor", 
            lambda state: "end",
            {
                "end": END
            }
        )
        graph.add_conditional_edges(
            "error_handler", 
            self._determine_next,
            {
                "end": END,
                "error_handler": "error_handler",
                "query_generator": "query_generator",
                "query_validator": "query_validator"
            }
        )
        
        # Compile and return
        return graph.compile()
    
    def execute(self, user_query: str, db_metadata: str, messages: List[AnyMessage] = None) -> Dict[str, Any]:
        """Execute the query graph with a user query."""
        # Initialize state
        initial_state: QueryState = {
            "user_query": user_query,
            "db_metadata": db_metadata,
            "messages": messages or [],
            "current_query": None,
            "error": None,
            "retry_count": 0,
            "query_result": None,
            "is_complete": False
        }
        
        self._debug_log("Starting query graph execution", "execute")
        self._debug_state(initial_state, "initial_state")
        
        # Execute graph
        result = self.graph.invoke(initial_state)
        
        self._debug_log("Query graph execution completed", "execute")
        self._debug_state(result, "final_state")
        
        return result 