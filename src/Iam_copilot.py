#!/usr/bin/env python3

import logging
import datetime
from typing import Dict, Any, List, AsyncIterator
import uuid

from langchain_core.messages import AIMessage, HumanMessage, AnyMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_community.utilities import SQLDatabase
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langchain.globals import set_debug

from src.iam_query import IAMQueryAgent
from src.state import IAMAgentState
from src.llm_context.prompt import iam_copilot_system, response_system_prompt, error_response_prompt, congrats_message
from src.llm_context.guidelines import GUIDELINES, MINIMAL_GUIDELINES, GENERAL_GUIDELINE, MINIMAL_GENERAL_GUIDELINE
from util.debug import setup_logger, debug_log, debug_state, count_tokens
from util.risk_utils import find_risk_type, has_user_data

class IAMCopilot:
    """IAM Copilot with conversation support using LangGraph."""
    
    def __init__(self, db_path: str = "data/risk_views.db", model: str = "llama3.2-ctx4000", num_ctx:int = 4000, debug: bool = True):
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
        
        # Set up session ID and logger
        self.session_id = f"copilot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Set up logger if in debug mode
        if debug:
            self.logger = setup_logger(self.session_id)
        else:
            self.logger = logging.getLogger(__name__)
        
        # Create LLM
        self.llm = ChatOllama(model=model, num_ctx=num_ctx)
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
        
        # Risk categories for similarity matching
        self.risk_categories = [
            "NO_MFA_USERS", 
            "WEAK_MFA_USERS", 
            "INACTIVE_USERS", 
            "NEVER_LOGGED_IN_USERS",
            "PARTIALLY_OFFBOARDED_USERS", 
            "SERVICE_ACCOUNTS", 
            "LOCAL_ACCOUNTS", 
            "RECENTLY_JOINED_USERS"
        ]
        
        if debug:
            set_debug(True)
            debug_log(self.logger, f"IAMCopilot initialized with session ID: {self.session_id}", "init")
    
    def _extract_messages_from_memory(self, thread_id: str) -> List[AnyMessage]:
        """Extract message history from memory saver for a specific thread."""
        try:
            # Create proper config object with thread_id
            config = {"configurable": {"thread_id": thread_id}}
            
            # Get the previous state for this thread_id if it exists
            previous_state = self.memory.get_tuple(config)
            
            # Check if we got a valid state back
            if previous_state is not None:
                # Check if there's a valid state value
                if previous_state.values and "messages" in previous_state.values:
                    return previous_state.values["messages"]
            
            return []
        except Exception as e:
            self.logger.error(f"Error extracting messages from memory: {str(e)}", exc_info=True)
            return []
    
    def _build_workflow(self) -> StateGraph:
        """Build the workflow graph with memory support."""
        # Create graph with state
        workflow = StateGraph(IAMAgentState)
        
        # Add nodes
        workflow.add_node("query_processor", self._query_processor_node)
        workflow.add_node("response_generator", self._response_generator_node)
        
        # Add edges
        workflow.add_edge(START, "query_processor")
        workflow.add_edge("query_processor", "response_generator")
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "response_generator",
            self._determine_next_step,
            {
                "end": END
            }
        )
        
        # Compile with memory checkpointer
        return workflow.compile(checkpointer=self.memory)
    
    def _query_processor_node(self, state: IAMAgentState) -> Dict[str, Any]:
        """Process query with conversation history."""
        if self.debug:
            debug_log(self.logger, "Processing query", "query_processor")
            debug_state(self.logger, state, "query_processor_input")
        
        try:
            # Get thread ID
            thread_id = state.get("thread_id", "default")
            
            # Set up messages list
            messages = []
            
            # Add current message to history for context
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
                error_state = {
                    "error": "No user question found",
                    "messages": state.get("messages", []),
                    "thread_id": thread_id
                }
                if self.debug:
                    debug_state(self.logger, error_state, "query_processor_error")
                return error_state
            
            # Create QueryGraph with conversation history
            query_graph = IAMQueryAgent(
                db=self.db,
                model=self.model,
                debug=self.debug,
                session_id=self.session_id
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
            
            result_state = {
                "messages": all_messages,
                "current_query": result.get("current_query"),
                "query_result": result.get("query_result"),
                "has_final_answer": False,  # Will be set by response generator
                "thread_id": thread_id,  # Preserve thread_id
                "error": result.get("error"),
                "user_query": user_question  # Store original query for response generator
            }
            
            if self.debug:
                debug_state(self.logger, result_state, "query_processor_output")
            
            return result_state
            
        except Exception as e:
            self.logger.error(f"Error in query processor: {str(e)}", exc_info=True)
            error_state = {
                "error": str(e),
                "messages": state.get("messages", []),
                "thread_id": state.get("thread_id", "default")  # Preserve thread_id
            }
            
            if self.debug:
                debug_state(self.logger, error_state, "query_processor_exception")
            
            return error_state
    
    def _get_guideline_for_risk_type(self, risk_type: str, query: str, use_minimal: bool = False) -> str:
        """Get appropriate guideline based on risk type and token count."""
        if risk_type == "GENERAL":
            return MINIMAL_GENERAL_GUIDELINE if use_minimal else GENERAL_GUIDELINE
            
        # Get guideline
        if use_minimal:
            # Use minimal guideline
            if risk_type in MINIMAL_GUIDELINES:
                return MINIMAL_GUIDELINES[risk_type]
            # Handle different naming in guidelines
            elif "Partially Offboarded Users" in GUIDELINES and risk_type == "PARTIALLY_OFFBOARDED_USERS":
                return MINIMAL_GUIDELINES.get("PARTIALLY_OFFBOARDED_USERS", "")
            return MINIMAL_GENERAL_GUIDELINE
        else:
            # Use full guideline
            if risk_type in GUIDELINES:
                return GUIDELINES[risk_type]
            # Handle different naming in guidelines
            elif risk_type == "PARTIALLY_OFFBOARDED_USERS" and "Partially Offboarded Users" in GUIDELINES:
                return GUIDELINES["Partially Offboarded Users"]
            elif risk_type == "NEVER_LOGGED_IN_USERS" and "NEVER_LOGGED_IN_USERS " in GUIDELINES:
                return GUIDELINES["NEVER_LOGGED_IN_USERS "]
            return GENERAL_GUIDELINE
    
    def _format_conversation_history(self, messages: List[AnyMessage]) -> str:
        """Format conversation history for the prompt."""
        formatted_history = ""
        
        if not messages:
            return formatted_history
            
        formatted_history = "Previous conversation:\n"
        for i, msg in enumerate(messages):
            if isinstance(msg, HumanMessage):
                formatted_history += f"User: {msg.content}\n"
            elif isinstance(msg, AIMessage):
                formatted_history += f"Assistant: {msg.content}\n"
                
        return formatted_history
    
    def _response_generator_node(self, state: IAMAgentState) -> Dict[str, Any]:
        """Generate response based on query results or error."""
        if self.debug:
            debug_log(self.logger, "Generating response", "response_generator")
            debug_state(self.logger, state, "response_generator_input")
        
        try:
            error = state.get("error")
            query_result = state.get("query_result")
            user_query = state.get("user_query", "")
            messages = state.get("messages", [])
            
            # Format conversation history
            conversation_history = self._format_conversation_history(messages[:-1] if messages else [])
            
            # Handle error case
            if error:
                if self.debug:
                    debug_log(self.logger, f"Processing error: {error}", "response_generator")
                
                # Create error response prompt
                prompt = ChatPromptTemplate.from_messages([
                    ("system", iam_copilot_system),
                    ("human", f"""
                    {conversation_history}
                    
                    User query: {user_query}
                    
                    {error_response_prompt}
                    """)
                ])
                
                # Generate error response
                response = self.llm.invoke(prompt.format_prompt())
                
                # Update state with error response
                result_state = {
                    "messages": messages + [AIMessage(content=response.content)],
                    "has_final_answer": True,
                    "thread_id": state.get("thread_id", "default")
                }
                
                if self.debug:
                    debug_state(self.logger, result_state, "response_generator_error_output")
                
                return result_state
            
            # Handle successful query
            if query_result is not None:  # Check if there was a query (even if result is empty)
                if self.debug:
                    debug_log(self.logger, "Processing query result", "response_generator")
                
                # Check if there is user data in the result
                has_data_result = has_user_data(query_result)
                
                if not has_data_result:
                    if self.debug:
                        debug_log(self.logger, "No user data found - sending congratulations", "response_generator")
                    
                    # Find the risk type from the query and conversation
                    risk_type, is_general = find_risk_type(
                        user_query=user_query,
                        messages=messages,
                        risk_categories=self.risk_categories,
                        logger=self.logger,
                        debug=self.debug
                    )
                    
                    if risk_type == "GENERAL":
                        # Create response with general congrats
                        result_state = {
                            "messages": messages + [AIMessage(content=congrats_message)],
                            "has_final_answer": True,
                            "thread_id": state.get("thread_id", "default")
                        }
                    else:
                        # Create response with specific risk type congrats
                        specific_congrats = f"Great news! I couldn't find any users with the '{risk_type}' risk category. This indicates your organization is maintaining good security practices in this area.\n\nRemember that IAM security is an ongoing process, so continue regular audits and monitoring to maintain this strong posture. Would you like information about other potential IAM risk areas to review?"
                        
                        result_state = {
                            "messages": messages + [AIMessage(content=specific_congrats)],
                            "has_final_answer": True,
                            "risk_type": risk_type,
                            "thread_id": state.get("thread_id", "default")
                        }
                    
                    if self.debug:
                        debug_state(self.logger, result_state, "response_generator_congrats_output")
                    
                    return result_state
                
                # Identify risk type in query result and conversation context
                risk_type, is_general = find_risk_type(
                    user_query=user_query,
                    messages=messages,
                    risk_categories=self.risk_categories,
                    logger=self.logger,
                    debug=self.debug
                )
                
                # Get appropriate guideline
                guideline = ""
                if risk_type:
                    # Check token count
                    combined_text = f"{user_query} {query_result}"
                    token_count = count_tokens(combined_text)
                    
                    # Use minimal guideline if more than 900 tokens
                    use_minimal = token_count > 900
                    guideline = self._get_guideline_for_risk_type(risk_type, user_query, use_minimal)
                    
                    if self.debug:
                        debug_log(self.logger, f"Risk type: {risk_type}, token count: {token_count}, using minimal: {use_minimal}, is general: {is_general}", "response_generator")
                
                # Create response prompt with guidelines if available
                guideline_text = f"\n\nGuideline for {risk_type}:\n{guideline}" if guideline else ""
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", response_system_prompt),
                    ("human", f"""
                    {conversation_history}
                    
                    User query: {user_query}
                    
                    Query result: {query_result}
                    {guideline_text}
                    
                    Generate a helpful response addressing the query and providing insights based on the results.
                    """)
                ])
                
                # Generate response
                response = self.llm.invoke(prompt.format_prompt())
                
                # Update state with response
                result_state = {
                    "messages": messages + [AIMessage(content=response.content)],
                    "has_final_answer": True,
                    "risk_type": risk_type,
                    "thread_id": state.get("thread_id", "default")
                }
                
                if self.debug:
                    debug_state(self.logger, result_state, "response_generator_success_output")
                
                return result_state
            
            # No result and no error - unusual case
            if self.debug:
                debug_log(self.logger, "No result and no error - fallback response", "response_generator")
            
            # Create fallback response
            result_state = {
                "messages": messages + [AIMessage(content="I couldn't find relevant information for your query. Could you please rephrase or provide more details?")],
                "has_final_answer": True,
                "thread_id": state.get("thread_id", "default")
            }
            
            if self.debug:
                debug_state(self.logger, result_state, "response_generator_fallback_output")
            
            return result_state
            
        except Exception as e:
            self.logger.error(f"Error in response generator: {str(e)}", exc_info=True)
            
            # Return error state
            error_state = {
                "error": str(e),
                "messages": state.get("messages", []) + [AIMessage(content="I encountered an error while processing your request. Please try again.")],
                "has_final_answer": True,
                "thread_id": state.get("thread_id", "default")
            }
            
            if self.debug:
                debug_state(self.logger, error_state, "response_generator_exception")
            
            return error_state
    
    def _determine_next_step(self, state: IAMAgentState) -> str:
        """Determine the next step in the workflow."""
        # Always end after response generator
        return "end"
    
    async def stream_query(
        self,
        query: str,
        thread_id: str = None,
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
        # Generate thread ID if not provided
        if not thread_id:
            thread_id = str(uuid.uuid4())
        
        if self.debug:
            debug_log(self.logger, f"Streaming query: {query} with thread ID: {thread_id}", "stream_query")
        
        # Create initial state with thread ID
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "thread_id": thread_id,
            "error": None,
            "db_metadata": None,
            "current_query": None,
            "query_result": None,
            "last_tool_call_id": None,
            "has_final_answer": False,
            "user_query": query
        }
        
        # Configurable with thread_id as per LangGraph spec
        config = {"configurable": {"thread_id": thread_id}}
        
        # Stream results with thread config
        async for event in self.workflow.astream(initial_state, config):
            yield event
    
    def process_query(self, query: str, thread_id: str = None) -> Dict[str, Any]:
        """Process a query synchronously.
        
        Args:
            query: The user's question
            thread_id: Unique identifier for the conversation thread
        
        Returns:
            Dict containing the final response
        """
        # Generate thread ID if not provided
        if not thread_id:
            thread_id = str(uuid.uuid4())
            
        if self.debug:
            debug_log(self.logger, f"Processing query: {query} with thread ID: {thread_id}", "process_query")
        
        # Create initial state with thread ID
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "thread_id": thread_id,
            "error": None,
            "db_metadata": None,
            "current_query": None,
            "query_result": None,
            "last_tool_call_id": None,
            "has_final_answer": False,
            "user_query": query
        }
        
        # Configurable with thread_id as per LangGraph spec
        config = {"configurable": {"thread_id": thread_id}}
        
        # Process query with thread config
        result = self.workflow.invoke(initial_state, config)
        
        if self.debug:
            debug_state(self.logger, result, "process_query_result")
            
        return result
    
    def close(self):
        """Close any open connections and resources."""
        # Access and close the underlying database connection
        if hasattr(self, 'db') and hasattr(self.db, '_engine'):
            if hasattr(self.db._engine, 'dispose'):
                self.db._engine.dispose()
                self.logger.info("Database connection closed")
        
        # Clear any memory
        if hasattr(self, 'memory'):
            # The MemorySaver doesn't have a close method,
            # but we could clean up references
            self.memory = None
        
        self.logger.info("IAMCopilot resources released") 