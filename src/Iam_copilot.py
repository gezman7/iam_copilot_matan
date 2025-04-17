import logging
from typing import Dict, Any

# LangChain imports
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import ToolMessage
from langchain_core.tools import tool
from langchain_core.messages.utils import trim_messages
from langchain_ollama import ChatOllama

# LangGraph imports
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import MemorySaver

# Database utils
from langchain_community.utilities import SQLDatabase
from src.guidelines import GUIDELINES

from .models import RiskTopic

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IAMCopilot:
    """Class for querying risk data using natural language using a LangGraph agent"""
    
    def __init__(self, llm=None, db_path="iam_risks.db"):
        self.db_path = db_path
        
        # Set up default llm if not provided
        if llm is None:
            
            self.llm = ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
        else:
            self.llm = llm
        
        # Connect to database
        self.db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
        
        # Get valid risk topics from enum
        self.valid_risk_types = [topic.value for topic in RiskTopic]
        
       
        
        # Initialize memory saver for conversation persistence
        self.memory = MemorySaver()
        
        # Create the agent workflow
        self.agent = self._create_agent()
    
    def _create_agent(self):
        
        # Define tools
        @tool
        def list_tables_tool() -> str:
            """Lists all tables in the database."""
            return ", ".join(self.db.get_usable_table_names())
        
        @tool
        def get_schema_tool(table_names: str) -> str:
            """
            Get the schema of the specified tables.
            
            Args:
                table_names: Comma-separated list of table names
            """
            tables = [name.strip() for name in table_names.split(",")]
            return self.db.get_table_info(tables)
        
        @tool
        def analyze_query(query: str) -> str:
            """
            Analyze a SQL query for common issues before execution.
            
            Args:
                query: SQL query to analyze
            """
            # Check for basic SQL injection patterns
            if ";" in query and not query.strip().endswith(";"):
                return "SECURITY WARNING: Multiple SQL statements detected. Only single statements are allowed."
            
            # Check for risk table filtering
            tables = self.db.get_usable_table_names()
            if ("risks" in tables or any("risk" in table.lower() for table in tables)) and any(risk_table in query.lower() for risk_table in ["risk", "risks"]):
                # Verify risk_type filter
                if not any(risk_type in query for risk_type in self.valid_risk_types):
                    return "ERROR: Query must filter by a valid risk_type value. Please add a WHERE clause with risk_type."
            
            # Basic syntax checks
            basic_syntax_issues = []
            if "WHERE" not in query.upper() and "SELECT *" in query.upper():
                basic_syntax_issues.append("- Query uses SELECT * without a WHERE clause, which might return too many rows")
            
            if "JOIN" in query.upper() and "ON" not in query.upper():
                basic_syntax_issues.append("- JOIN without ON clause detected")
            
            if "ORDER BY" in query.upper() and "LIMIT" not in query.upper():
                basic_syntax_issues.append("- Consider adding a LIMIT clause to your ORDER BY")
            
            if "GROUP BY" in query.upper() and "HAVING" not in query.upper():
                basic_syntax_issues.append("- Consider adding a HAVING clause to filter your GROUP BY results")
            
            if basic_syntax_issues:
                return "QUERY ANALYSIS WARNINGS:\n" + "\n".join(basic_syntax_issues)
            
            return "Query analysis complete. No obvious issues detected."
        
        @tool
        def db_query_tool(query: str) -> str:
            """
            Execute the given SQL query and return the results.
            
            Args:
                query: SQL query to execute
            """
            try:
                result = self.db.run(query)
                return result
            except Exception as e:
                # Return error message but formatted to be helpful
                return f"SQL Error: {str(e)}"
        
        @tool
        def generate_final_answer(query_results: str, risk_type: str = None) -> str:
            """
            Generate a final answer based on query results and risk type.
            
            Args:
                query_results: The results of SQL queries
                risk_type: The risk type being analyzed (optional)
            """
            # If risk_type is provided, add the corresponding guideline
            if risk_type and risk_type in GUIDELINES:
                guideline = GUIDELINES[risk_type]
                if "Guideline:" not in query_results:
                    return f"{query_results}\n\nGuideline: {guideline}"
            
            return query_results
        
        # Create tools list
        tools = [list_tables_tool, get_schema_tool, analyze_query, db_query_tool, generate_final_answer]
        
        # System prompt focused on SQL analysis for IAM risks
        system_prompt = """You are an IAM security analyst specializing in SQL analysis of identity risks.

User will ask questions about IAM security risks in the database. Your job is to:

1. First list the tables in the database using list_tables_tool
2. Get the schema for relevant tables using get_schema_tool
3. Craft an appropriate SQL query to answer the question
4. Analyze your SQL query using analyze_query to check for common issues:
   - Ensure queries filtering risk data include WHERE clause with risk_type
   Execute the query with db_query_tool
6. Generate a final answer with generate_final_answer including:
   - A clear explanation of the results
   - Any security implications
   - The specific risk type if identified from: INACTIVE_USERS, WEAK_MFA_USERS, 
     SERVICE_ACCOUNTS, LOCAL_ACCOUNTS, NEVER_LOGGED_IN_USERS, RECENTLY_JOINED_USERS, 
     PARTIALLY_OFFBOARDED_USERS

Provide your answer in a clear, structured format with analysis of the security implications.
"""
        
        # Create a fully linear workflow
        workflow = StateGraph(MessagesState)
        
        # Create tool node
        tool_node = ToolNode(tools)
        
        # Define message trimming function to limit context window
        def trim_message_history(messages):
            """Trim message history to manage context window"""
            # Use trim_messages to keep only the most relevant messages
            # The function balances keeping system prompt, recent messages,
            # and ensuring the conversation starts with the right message type
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
        
        # Agent node that processes messages and calls LLM
        def agent_node(state):
            """Generate responses using the LLM"""
            messages = state.get("messages", [])
            
            # Add system message if it's not already there
            if not any(isinstance(msg, SystemMessage) for msg in messages):
                messages = [SystemMessage(content=system_prompt)] + messages
            
            # Trim messages to manage context window
            trimmed_messages = trim_message_history(messages)
            
            # Call the LLM with trimmed message history
            response = self.llm.invoke(trimmed_messages)
            
            # Add the response to messages
            return {"messages": messages + [response]}
        
        # Add nodes to workflow
        workflow.add_node("agent", RunnableLambda(agent_node))
        workflow.add_node("tools", tool_node)
        
        # Define how to check for completion
        def should_end(state):
            """Check if workflow should end"""
            messages = state.get("messages", [])
            
            # Check if generate_final_answer has been called
            for i, msg in enumerate(messages):
                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
                    for tool_call in msg.tool_calls:
                        if tool_call.get("name") == "generate_final_answer":
                            # Look for tool response
                            if i+1 < len(messages) and isinstance(messages[i+1], ToolMessage):
                                return True
            
            return False
        
        # Add edges - simple linear path between agent and tools
        workflow.add_edge("agent", "tools")
        workflow.add_edge("tools", "agent")
        
        # Add conditional edge to end when final answer is generated
        workflow.add_conditional_edges(
            "agent",
            should_end,
            {
                True: END,
                False: "tools"
            }
        )
        
        # Set entry point
        workflow.set_entry_point("agent")
        
        # Compile graph with memory checkpointer for conversation persistence
        return workflow.compile(checkpointer=self.memory)
    
    def process_query(self, question: str, thread_id: str = "default") -> Dict[str, Any]:
        """
        Process a natural language query about IAM risks and return the answer.
        
        Unlike stream methods, this returns the complete response at once.
        
        Args:
            question: The natural language query to process
            thread_id: Unique ID for the conversation thread (for persistence)
            
        Returns:
            Dict containing the response and metadata
        """
        try:
            # Format the user query
            input_message = HumanMessage(content=question)
            
            # Set up configuration with thread_id for conversation persistence
            config = {"configurable": {"thread_id": thread_id}}
            
            # Invoke the agent with thread_id config for conversation persistence
            result = self.agent.invoke({"messages": [input_message]}, config)
            
            # Extract messages
            messages = result.get("messages", [])
            
            if not messages:
                return {
                    "success": False,
                    "response": "No response was generated."
                }
            
            # Find the final answer from the last AI message
            final_answer = None
            tool_calls = []
            tool_results = []
            
            for msg in messages:
                if isinstance(msg, AIMessage):
                    final_answer = msg.content
                    # Collect tool calls if available
                    if hasattr(msg, "tool_calls"):
                        tool_calls.extend([{
                            "name": tc.get("name"),
                            "args": tc.get("args")
                        } for tc in msg.tool_calls])
                elif isinstance(msg, ToolMessage):
                    tool_results.append(msg.content)
            
            # If no final answer was found, use the last message content
            if not final_answer and messages:
                last_message = messages[-1]
                final_answer = last_message.content if hasattr(last_message, "content") else str(last_message)
            
            return {
                "success": True,
                "response": final_answer,
                "thread_id": thread_id,
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "message_count": len(messages)
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "success": False,
                "response": f"I encountered an error processing your query: {str(e)}",
                "error_type": "processing_error",
                "error": str(e)
            }
    
    def process_speech_query(self, question: str, thread_id: str = "default") -> Dict[str, Any]:
        """Process a natural language query about IAM risks"""
        try:
            # Format the user query
            input_message = HumanMessage(content=question)
            
            # Set up configuration with thread_id for conversation persistence
            config = {"configurable": {"thread_id": thread_id}}
            
            # Invoke the agent with thread_id config for conversation persistence
            result = self.agent.invoke({"messages": [input_message]}, config)
            
            # Extract messages
            messages = result.get("messages", [])
            
            if not messages:
                return {
                    "success": False,
                    "response": "No response was generated."
                }
            
            # Find the final answer
            final_answer = None
            
            # Look for generate_final_answer tool calls and responses
            for i, msg in enumerate(messages):
                if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
                    for tool_call in msg.tool_calls:
                        if tool_call.get("name") == "generate_final_answer":
                            # Look for the tool response
                            if i+1 < len(messages) and isinstance(messages[i+1], ToolMessage):
                                final_answer = messages[i+1].content
                                break
                
                if final_answer:
                    break
            
            # If no specific final answer found, use the last message
            if not final_answer and messages:
                last_message = messages[-1]
                final_answer = last_message.content if hasattr(last_message, "content") else str(last_message)
            
            # Construct the response
            return {
                "success": True,
                "response": final_answer,
                "trajectory": [m.content if hasattr(m, "content") else str(m) for m in messages],
                "thread_id": thread_id
            }
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return {
                "success": False,
                "response": f"I encountered an error processing your query: {str(e)}",
                "error_type": "processing_error",
                "error": e
            }

    async def stream_query(self, question: str, thread_id: str = "default", stream_mode: str = "values"):
        """
        Stream a natural language query about IAM risks with incremental responses
        
        Args:
            question: The natural language query to process
            thread_id: Unique ID for the conversation thread (for persistence)
            stream_mode: The streaming mode to use - 'values', 'steps', or 'intermediate_steps'
        """
        try:
            # Format the user query
            input_message = HumanMessage(content=question)
            
            # Set up configuration with thread_id for conversation persistence
            config = {"configurable": {"thread_id": thread_id}}
            
            # Stream the agent with thread_id config for conversation persistence
            for chunk in self.agent.stream({"messages": [input_message]}, config, stream_mode=stream_mode):
                yield chunk
            
        except Exception as e:
            logger.error(f"Error streaming query: {e}")
            yield {
                "success": False,
                "response": f"I encountered an error processing your query: {str(e)}",
                "error_type": "processing_error",
                "error": e
            }
    
    async def stream_with_details(self, question: str, thread_id: str = "default"):
        """
        Stream a query with detailed information about agent steps and thought process
        
        Args:
            question: The natural language query to process
            thread_id: Unique ID for the conversation thread (for persistence)
        """
        try:
            # Format the user query
            input_message = HumanMessage(content=question)
            
            # Set up configuration with thread_id for conversation persistence
            config = {"configurable": {"thread_id": thread_id}}
            
            # Track the state of output for better formatting
            steps_started = False
            current_step = None
            seen_messages = set()  # To track unique messages
            
            # First try with intermediate_steps mode
            try:
                # Stream in intermediate_steps mode to get details on agent's thought process
                async for chunk in self.stream_query(question, thread_id, stream_mode="intermediate_steps"):
                    if "intermediate_steps" in chunk:
                        # Extract steps information
                        if not steps_started:
                            yield {"type": "start_steps", "content": "Starting agent execution..."}
                            steps_started = True
                        
                        step = chunk["intermediate_steps"][-1] if chunk["intermediate_steps"] else None
                        if step and step != current_step:
                            current_step = step
                            action = step.get("action", {})
                            action_name = action.get("name", "Unknown action")
                            action_input = action.get("args", {})
                            
                            # Yield information about the current step
                            yield {
                                "type": "step", 
                                "name": action_name, 
                                "input": action_input,
                                "content": f"Executing {action_name} with input: {action_input}"
                            }
                            
                            # If there's an observation, yield that too
                            if "observation" in step:
                                yield {
                                    "type": "observation",
                                    "content": f"Observation: {step['observation']}"
                                }
                    
                    if "messages" in chunk and chunk["messages"]:
                        last_message = chunk["messages"][-1]
                        if hasattr(last_message, "content"):
                            # Only yield new messages
                            msg_id = id(last_message)
                            if msg_id not in seen_messages and last_message.content:
                                seen_messages.add(msg_id)
                                yield {
                                    "type": "response",
                                    "content": last_message.content
                                }
            except Exception as e:
                logger.warning(f"Intermediate steps streaming not fully supported: {e}")
                # Fall back to simpler streaming if intermediate_steps mode fails
                yield {"type": "fallback", "content": "Falling back to simpler streaming mode"}
                
                # Use values mode instead
                async for chunk in self.stream_query(question, thread_id, stream_mode="values"):
                    if "messages" in chunk and chunk["messages"]:
                        last_message = chunk["messages"][-1]
                        if hasattr(last_message, "content"):
                            msg_id = id(last_message)
                            if msg_id not in seen_messages and last_message.content:
                                seen_messages.add(msg_id)
                                # Look for tool usage in the content
                                if "tool" in last_message.content.lower() or "executing" in last_message.content.lower():
                                    yield {
                                        "type": "step",
                                        "name": "inferred_tool",
                                        "content": last_message.content
                                    }
                                else:
                                    yield {
                                        "type": "response",
                                        "content": last_message.content
                                    }
            
            yield {"type": "end", "content": "Agent execution completed."}
            
        except Exception as e:
            logger.error(f"Error streaming query with details: {e}")
            yield {
                "type": "error",
                "content": f"I encountered an error processing your query: {str(e)}",
                "error_type": "processing_error",
                "error": e
            }
            
    async def stream_simplified(self, question: str, thread_id: str = "default"):
        """
        Stream a query with a simplified output format that works with any LLM
        
        Args:
            question: The natural language query to process
            thread_id: Unique ID for the conversation thread (for persistence)
        """
        try:
            # Format the user query
            input_message = HumanMessage(content=question)
            
            # Set up configuration with thread_id for conversation persistence
            config = {"configurable": {"thread_id": thread_id}}
            
            # Track seen message content to avoid duplicates
            seen_content = set()
            
            # Yield start event
            yield {"type": "start", "content": "Starting query processing..."}
            
            # Stream using values mode (most widely supported)
            async for chunk in self.stream_query(question, thread_id, stream_mode="values"):
                if "messages" in chunk and chunk["messages"]:
                    for msg in chunk["messages"]:
                        if hasattr(msg, "content") and msg.content:
                            # Only yield new content
                            if msg.content not in seen_content:
                                seen_content.add(msg.content)
                                
                                # Determine message type
                                if isinstance(msg, AIMessage):
                                    yield {"type": "ai", "content": msg.content}
                                elif isinstance(msg, ToolMessage):
                                    yield {"type": "tool", "content": msg.content}
                                elif isinstance(msg, HumanMessage):
                                    yield {"type": "human", "content": msg.content}
                                else:
                                    yield {"type": "other", "content": msg.content}
            
            # Yield end event
            yield {"type": "end", "content": "Query processing completed."}
            
        except Exception as e:
            logger.error(f"Error streaming simplified query: {e}")
            yield {
                "type": "error",
                "content": f"Error: {str(e)}"
            }


# Example of usage
if __name__ == "__main__":
    import os
    import traceback
    import asyncio
    from datetime import datetime
    
    # Create IAMCopilot with default Ollama model
    copilot = IAMCopilot(db_path="iam_risks.db")
    
    # Example conversation with thread_id for persistence
    thread_id = f"conversation-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    
    # Define an async function to handle basic streaming
    async def run_basic_streaming_example():
        print("\n=== Basic Streaming Example ===\n")
        
        # Initial query
        query = "How many users have weak MFA?"
        print(f"User: {query}")
        
        # Stream initial query in values mode
        async for event in copilot.stream_query(query, thread_id, stream_mode="values"):
            # Get the last message which is the most recent response
            if "messages" in event and event["messages"]:
                last_message = event["messages"][-1]
                if hasattr(last_message, "content") and last_message.content:
                    print(f"AI: {last_message.content}")
        
        # Follow-up query
        follow_up = "Which department has the most users with this issue?"
        print(f"\nUser: {follow_up}")
        
        # Stream follow-up query
        async for event in copilot.stream_query(follow_up, thread_id, stream_mode="values"):
            if "messages" in event and event["messages"]:
                last_message = event["messages"][-1]
                if hasattr(last_message, "content") and last_message.content:
                    print(f"AI: {last_message.content}")
    
    # Define an async function to handle detailed streaming
    async def run_detailed_streaming_example():
        print("\n=== Detailed Streaming Example ===\n")
        
        # Query with detailed streaming
        query = "What security recommendations do you have for weak MFA users?"
        print(f"User: {query}")
        
        # Stream with detailed information about agent steps
        async for event in copilot.stream_with_details(query, thread_id):
            event_type = event.get("type", "unknown")
            content = event.get("content", "")
            
            if event_type == "start_steps":
                print("\n🚀 Starting agent execution...")
            elif event_type == "step":
                print(f"\n⚙️ Step: {event.get('name', 'Unknown')}")
                print(f"   Input: {event.get('input', {})}")
            elif event_type == "observation":
                print(f"\n👁️ {content}")
            elif event_type == "response":
                print(f"\n🤖 Response: {content}")
            elif event_type == "end":
                print(f"\n✅ {content}")
            elif event_type == "error":
                print(f"\n❌ Error: {content}")
    
    # Run both streaming examples
    async def run_all_examples():
        await run_basic_streaming_example()
        await run_detailed_streaming_example()
    
    # Run the async function
    asyncio.run(run_all_examples())

