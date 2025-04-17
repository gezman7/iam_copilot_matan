#!/usr/bin/env python3

import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from langchain_core.messages import AIMessage, HumanMessage, AnyMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_community.utilities import SQLDatabase
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langchain.globals import set_debug

from src.query_graph import QueryGraph, QueryState
from src.state import IAMAgentState, debug_state

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IAMCopilot:
    """IAM Copilot with conversation support using LangGraph."""
    
    def __init__(self, db_path: str = "risk_views.db", model: str = "llama3.2-ctx4000", debug: bool = False):
        """Initialize the IAM Copilot.
        
        Args:
            db_path: Path to the SQLite database
            model: Name of the LLM model to use
            debug: Whether to enable debug mode
        """
        self.db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
        self.model = model
        self.debug = debug
        
        # Initialize memory saver for conversation persistence
        self.memory = MemorySaver()
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        
        if debug:
            set_debug(True)
    
    def _extract_messages_from_memory(self, thread_id: str) -> List[AnyMessage]:
        """Extract message history from memory saver for a specific thread."""
        try:
            # Create proper config object with thread_id
            config = {"configurable": {"thread_id": thread_id}}
            
            # Get the previous state for this thread_id if it exists
            previous_state = self.memory.get(config)
            
            # Extract messages from the state
            if previous_state and "messages" in previous_state:
                return previous_state["messages"]
            
            return []
        except Exception as e:
            logger.error(f"Error extracting messages from memory: {str(e)}", exc_info=True)
            return []
    
    def _build_workflow(self) -> StateGraph:
        """Build the workflow graph with memory support."""
        # Create graph with state
        workflow = StateGraph(IAMAgentState)
        
        # Add nodes
        workflow.add_node("query_processor", self._query_processor_node)
        
        # Add edges
        workflow.add_edge(START, "query_processor")
        workflow.add_conditional_edges(
            "query_processor",
            self._determine_next_step,
            {
                "end": END
            }
        )
        
        # Compile with memory checkpointer
        return workflow.compile(checkpointer=self.memory)
    
    def _query_processor_node(self, state: IAMAgentState) -> Dict[str, Any]:
        """Process query with conversation history."""
        try:
            # Get thread ID
            thread_id = state.get("thread_id", "default")
            
            # Get conversation history from memory saver
            previous_messages = self._extract_messages_from_memory(thread_id)
            
            # Add current message to history for context
            messages = previous_messages.copy()
            for msg in state.get("messages", []):
                if isinstance(msg, HumanMessage):
                    messages.append(msg)
            
            # Extract user question from the last human message
            user_question = None
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_question = msg.content
                    break
            
            if not user_question:
                return debug_state({"error": "No user question found"}, "query_processor")
            
            # Create QueryGraph with conversation history
            query_graph = QueryGraph(
                db=self.db,
                model=self.model,
                debug=self.debug
            )
            
            # Execute query with history
            result = query_graph.execute(
                user_query=user_question,
                db_metadata=state.get("db_metadata", ""),
                messages=messages
            )
            
            # Prepare response for state
            response_messages = result.get("messages", [])
            all_messages = messages + response_messages
            
            return debug_state({
                "messages": all_messages,
                "current_query": result.get("current_query"),
                "query_result": result.get("query_result"),
                "has_final_answer": result.get("is_complete", False),
                "thread_id": thread_id  # Preserve thread_id
            }, "query_processor")
            
        except Exception as e:
            logger.error(f"Error in query processor: {str(e)}", exc_info=True)
            return debug_state({
                "error": str(e),
                "messages": [AIMessage(content=f"An error occurred: {str(e)}")],
                "thread_id": state.get("thread_id", "default")  # Preserve thread_id
            }, "query_processor - error")
    
    def _determine_next_step(self, state: IAMAgentState) -> str:
        """Determine the next step in the workflow."""
        if state.get("has_final_answer", False):
            return "end"
        if state.get("error"):
            return "end"
        return "end"
    
    async def stream_query(
        self,
        query: str,
        thread_id: str,
        stream_mode: str = "values"
    ) -> AsyncIterator[Dict[str, Any]]:
        """Process a query with streaming support.
        
        Args:
            query: The user's question
            thread_id: Unique identifier for the conversation thread
            stream_mode: Streaming mode ('values', 'steps', or 'detailed')
        
        Yields:
            Dict containing streamed response data
        """
        # Create initial state with thread ID
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "thread_id": thread_id,
            "error": None,
            "db_metadata": None,
            "current_query": None,
            "query_result": None,
            "last_tool_call_id": None,
            "has_final_answer": False
        }
        
        # Configure with thread_id for memory identification
        config = {"configurable": {"thread_id": thread_id}}
        
        # Stream results with thread config
        async for event in self.workflow.astream(initial_state, config=config):
            yield event
    
    def process_query(self, query: str, thread_id: str) -> Dict[str, Any]:
        """Process a query synchronously.
        
        Args:
            query: The user's question
            thread_id: Unique identifier for the conversation thread
        
        Returns:
            Dict containing the final response
        """
        # Create initial state with thread ID
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "thread_id": thread_id,
            "error": None,
            "db_metadata": None,
            "current_query": None,
            "query_result": None,
            "last_tool_call_id": None,
            "has_final_answer": False
        }
        
        # Configure with thread_id for memory identification
        config = {"configurable": {"thread_id": thread_id}}
        
        # Process query with thread config
        return self.workflow.invoke(initial_state, config=config) 