import logging
from typing import Dict, Any

# LangChain imports
from langchain_core.runnables import RunnableLambda
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.tool import ToolMessage
from langchain_core.tools import tool
from langchain_core.messages.utils import trim_messages

# LangGraph imports
from langgraph.prebuilt import ToolNode
from langgraph.graph import END, StateGraph
from langgraph.graph import MessagesState
from langgraph.checkpoint.memory import MemorySaver

# Database utils
from langchain_community.utilities import SQLDatabase

from src.risk_topics import RiskTopic

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class IAMCopilot:
    """Class for querying risk data using natural language using a LangGraph agent"""
    
    def __init__(self, llm=None, db_path="iam_risks.db"):
        self.db_path = db_path
        
        # Set up default llm if not provided
        if llm is None:
            from langchain_ollama import ChatOllama
            self.llm = ChatOllama(model="llama3.2-ctx4000", num_ctx=4000)
        else:
            self.llm = llm
        
        # Connect to database
        self.db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
        
        # Get valid risk topics from enum
        self.valid_risk_types = [topic.value for topic in RiskTopic]
        
        # Load guidelines for risk types
        self.risk_guidelines = {
            "INACTIVE_USERS": "Inactive accounts should be disabled after 90 days of inactivity and deleted after 180 days.",
            "WEAK_MFA_USERS": "All user accounts should have strong MFA enabled. Hardware tokens or authenticator apps are preferred over SMS or email.",
            "SERVICE_ACCOUNTS": "Service accounts should not have interactive login capabilities and credentials should be rotated regularly.",
            "LOCAL_ACCOUNTS": "Local accounts should be minimized and carefully monitored as they bypass centralized identity management.",
            "NEVER_LOGGED_IN_USERS": "Accounts that have never been accessed should be reviewed and potentially removed.",
            "RECENTLY_JOINED_USERS": "New user accounts should be carefully monitored for unusual activity during their first 30 days.",
            "PARTIALLY_OFFBOARDED_USERS": "Partially offboarded users still have access to some systems and should be fully offboarded."
        }
        
        # Initialize memory saver for conversation persistence
        self.memory = MemorySaver()
        
        # Create the agent workflow
        self.agent = self._create_agent()
    
    def _create_agent(self):
        """Create a LangGraph-based SQL agent with a fully linear flow"""
        
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
        def get_security_recommendations(risk_type: str) -> str:
            """
            Get security recommendations for a specific risk type.
            
            Args:
                risk_type: The type of risk to get recommendations for
            """
            if risk_type in self.risk_guidelines:
                guideline = self.risk_guidelines[risk_type]
                recommendations = {
                    "INACTIVE_USERS": """
1. Implement an automated account disablement policy
2. Set up regular account audits (at least quarterly)
3. Create alerting for accounts that approach inactivity thresholds
4. Develop a formal offboarding process
5. Maintain documentation of exceptions with business justification
                    """,
                    "WEAK_MFA_USERS": """
1. Enforce hardware-based or app-based MFA for all users
2. Gradually phase out SMS and email-based MFA
3. Implement conditional access policies that require stronger MFA for sensitive applications
4. Conduct regular user training on the importance of strong MFA
5. Set up monitoring to detect and alert on MFA method changes
                    """,
                    "SERVICE_ACCOUNTS": """
1. Implement automated credential rotation
2. Use a privileged access management solution
3. Apply the principle of least privilege
4. Set up alerting for any interactive login attempts
5. Regularly audit service account permissions
                    """,
                    "LOCAL_ACCOUNTS": """
1. Minimize local accounts where possible
2. Apply strong password policies
3. Implement regular local account audits
4. Set up monitoring for local account creation and modification
5. Document business justifications for all local accounts
                    """,
                    "NEVER_LOGGED_IN_USERS": """
1. Implement automated deprovisioning for accounts not used within 30 days of creation
2. Review provisioning workflows to avoid creating unnecessary accounts
3. Set up alerting for new accounts that remain unused
4. Include account cleanup in regular access reviews
5. Document exceptions with business justification
                    """,
                    "RECENTLY_JOINED_USERS": """
1. Implement enhanced monitoring for new user accounts
2. Provide targeted security awareness training
3. Apply more restrictive permissions initially
4. Conduct early access reviews (within first 30 days)
5. Set up buddy systems or mentoring for security practices
                    """,
                    "PARTIALLY_OFFBOARDED_USERS": """
1. Implement comprehensive offboarding checklists
2. Conduct regular audits of offboarded users
3. Use automated offboarding workflows
4. Assign accountability for completion of offboarding
5. Set up monitoring to detect access from supposedly offboarded accounts
                    """
                }
                
                if risk_type in recommendations:
                    return f"Guideline: {guideline}\n\nRecommendations:\n{recommendations[risk_type]}"
                else:
                    return f"Guideline: {guideline}"
            
            return "No specific recommendations available for this risk type."
        
        @tool
        def generate_final_answer(query_results: str, risk_type: str = None) -> str:
            """
            Generate a final answer based on query results and risk type.
            
            Args:
                query_results: The results of SQL queries
                risk_type: The risk type being analyzed (optional)
            """
            # If risk_type is provided, add the corresponding guideline
            if risk_type and risk_type in self.risk_guidelines:
                guideline = self.risk_guidelines[risk_type]
                if "Guideline:" not in query_results:
                    return f"{query_results}\n\nGuideline: {guideline}"
            
            return query_results
        
        # Create tools list
        tools = [list_tables_tool, get_schema_tool, analyze_query, db_query_tool, get_security_recommendations, generate_final_answer]
        
        # System prompt focused on SQL analysis for IAM risks
        system_prompt = """You are an IAM security analyst specializing in SQL analysis of identity risks.

User will ask questions about IAM security risks in the database. Your job is to:

1. First list the tables in the database using list_tables_tool
2. Get the schema for relevant tables using get_schema_tool
3. Craft an appropriate SQL query to answer the question
4. Analyze your SQL query using analyze_query to check for common issues:
   - Ensure queries filtering risk data include WHERE clause with risk_type
   - Check for SQL injection patterns
   - Validate proper JOIN conditions
   - Verify appropriate filtering
5. Execute the query with db_query_tool
6. Generate a final answer with generate_final_answer including:
   - A clear explanation of the results
   - Any security implications
   - The specific risk type if identified from: INACTIVE_USERS, WEAK_MFA_USERS, 
     SERVICE_ACCOUNTS, LOCAL_ACCOUNTS, NEVER_LOGGED_IN_USERS, RECENTLY_JOINED_USERS, 
     PARTIALLY_OFFBOARDED_USERS

If the user asks for security recommendations or best practices for a specific risk type, use the get_security_recommendations tool with the appropriate risk type.

If the user asks a follow-up question, take into account the previous conversation context to provide a coherent response. For example, if they previously asked about WEAK_MFA_USERS and then ask "What are the security recommendations for these users?", you should use get_security_recommendations with "WEAK_MFA_USERS" as the risk type.

IMPORTANT SQL GUIDELINES:
- Always filter risk tables by risk_type
- Always use parameterized queries when possible
- Avoid unnecessary SELECT *
- Include appropriate LIMIT clauses
- Always include proper JOIN conditions

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

    async def stream_query(self, question: str, thread_id: str = "default"):
        """Stream a natural language query about IAM risks with incremental responses"""
        try:
            # Format the user query
            input_message = HumanMessage(content=question)
            
            # Set up configuration with thread_id for conversation persistence
            config = {"configurable": {"thread_id": thread_id}}
            
            # Stream the agent with thread_id config for conversation persistence
            stream = self.agent.stream({"messages": [input_message]}, config, stream_mode="values")
            
            # Create an async generator from the stream
            for chunk in stream:
                yield chunk
            
        except Exception as e:
            logger.error(f"Error streaming query: {e}")
            yield {
                "success": False,
                "response": f"I encountered an error processing your query: {str(e)}",
                "error_type": "processing_error",
                "error": e
            }


# Example of usage
if __name__ == "__main__":
    import os
    import traceback
    import asyncio
    
    # Create IAMCopilot with default Ollama model
    copilot = IAMCopilot(db_path="iam_risks.db")
    
    # Example conversation with thread_id for persistence
    thread_id = "conversation-1"
    
    # Define an async function to handle streaming
    async def run_streaming_example():
        # Initial query
        query = "How many users have weak MFA?"
        print(f"Initial query: {query}")
        
        # Stream initial query
        async for event in copilot.stream_query(query, thread_id):
            # Get the last message which is the most recent response
            if "messages" in event and event["messages"]:
                last_message = event["messages"][-1]
                if hasattr(last_message, "content"):
                    print(f"AI: {last_message.content}")
        
        # Follow-up query
        follow_up = "Which department has the most users with this issue?"
        print(f"\nFollow-up query: {follow_up}")
        
        # Stream follow-up query
        async for event in copilot.stream_query(follow_up, thread_id):
            # Get the last message which is the most recent response
            if "messages" in event and event["messages"]:
                last_message = event["messages"][-1]
                if hasattr(last_message, "content"):
                    print(f"AI: {last_message.content}")
        
        # Second follow-up query for security recommendations
        security_query = "What security recommendations do you have for these weak MFA users?"
        print(f"\nSecurity recommendations query: {security_query}")
        
        # Stream security recommendations query
        async for event in copilot.stream_query(security_query, thread_id):
            # Get the last message which is the most recent response
            if "messages" in event and event["messages"]:
                last_message = event["messages"][-1]
                if hasattr(last_message, "content"):
                    print(f"AI: {last_message.content}")
    
    # Run the async function
    asyncio.run(run_streaming_example())

