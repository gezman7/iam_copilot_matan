import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent directory to path
parent_dir = str(Path(__file__).resolve().parent.parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from iam_copilot.iam_graph.llm.risk_data_pipeline import RiskDataPipeline
from iam_copilot.iam_graph.llm.search_detection_snapshot import SearchDetectionSnapshot

class IAMRiskQueryE2E:
    """End-to-end test class for IAM risk queries"""
    
    def __init__(self, llm_model="llama3.2-ctx4000", mock_data_path=None, db_path=None):
        """Initialize with optional custom paths"""
        # Setup paths
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.mock_data_path = mock_data_path or "/Users/matangez/Documents/iam_graph/data/mock_data.json"
        self.db_path = db_path or os.path.join(self.script_dir, "iam_risks.db")
        
        # Verify mock data exists
        if not os.path.exists(self.mock_data_path):
            raise FileNotFoundError(f"Mock data file not found at {self.mock_data_path}")
            
        # Initialize database
        self._initialize_database()
        
        # Initialize language model
        self._initialize_llm(llm_model)
        
        # Initialize search detection snapshot
        self.search = SearchDetectionSnapshot(self.llm, db_path=self.db_path)
        
        print(f"IAM Risk Query system initialized and ready")
    
    def _initialize_database(self):
        """Initialize the risk database"""
        print(f"Initializing risk database at {self.db_path}...")
        pipeline = RiskDataPipeline(mock_data_path=self.mock_data_path, db_path=self.db_path)
        result = pipeline.run_pipeline()
        
        if not result["success"]:
            raise RuntimeError("Failed to initialize risk database")
        
        risk_count = sum(result["statistics"].values())
        print(f"Database initialized with {risk_count} risk detections")
        self.risk_statistics = result["statistics"]
    
    def _initialize_llm(self, model_name):
        """Initialize language model"""
        try:
            # Try to initialize ChatOllama
            from langchain_ollama import ChatOllama
            self.llm = ChatOllama(model=model_name, num_ctx=4000)
            print(f"Initialized Ollama model: {model_name}")
        except Exception as e:
            print(f"Error initializing Ollama model: {e}")
            print("Attempting to use OpenAI model...")
            
            try:
                # Fallback to OpenAI
                from langchain_openai import ChatOpenAI
                self.llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
                print(f"Initialized OpenAI model: gpt-3.5-turbo")
            except Exception as e2:
                print(f"Error initializing OpenAI model: {e2}")
                print("Attempting to use fake LLM for testing...")
                
                try:
                    # Fallback to Fake LLM
                    from langchain_community.llms.fake import FakeListLLM
                    responses = [
                        "SELECT * FROM UserRiskView WHERE risk_type = 'WEAK_MFA_USERS'",
                        "SELECT COUNT(*) FROM UserRiskView WHERE risk_type = 'SERVICE_ACCOUNTS'",
                        "SELECT Name FROM UserRiskView WHERE risk_type = 'INACTIVE_USERS'",
                        "SELECT Department, COUNT(*) FROM UserRiskView WHERE risk_type = 'WEAK_MFA_USERS' GROUP BY Department ORDER BY COUNT(*) DESC LIMIT 1",
                        "SELECT * FROM UserRiskView WHERE risk_type = 'NEVER_LOGGED_IN_USERS'"
                    ]
                    self.llm = FakeListLLM(responses=responses)
                    print("Initialized fake LLM for testing")
                except Exception as e3:
                    raise RuntimeError(f"Failed to initialize any LLM: {e3}")
    
    def query(self, question: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """
        Process a natural language query about IAM risks
        
        Args:
            question: The natural language query
            conversation_history: Optional list of previous messages in the format 
                                 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        
        Returns:
            str: The response to the query
        """
        # Format conversation history if provided
        chat_history = ""
        if conversation_history:
            chat_history = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
        
        # Process query
        try:
            print(f"Processing query: {question}")
            response = self.search.process_query(question, chat_history)
            return response
        except Exception as e:
            error_msg = f"Error processing query: {str(e)}"
            print(error_msg)
            return error_msg
    
    def run_sample_queries(self):
        """Run a set of sample queries to demonstrate functionality"""
        sample_queries = [
            "Show me all users with weak MFA",
            "How many service accounts do we have?",
            "List the names of inactive users",
            "Which department has the most users with weak MFA?",
            "Show me users who have never logged in",
            "Invalid query without risk type"
        ]
        
        results = {}
        for query in sample_queries:
            print(f"\n--- Query: {query} ---")
            response = self.query(query)
            print(f"Response: {response[:200]}...")  # Show first 200 chars
            results[query] = response
        
        # Test a follow-up query
        print("\n--- Follow-up query test ---")
        initial_query = "Show me all users with weak MFA"
        followup_query = "Which ones are in the IT department?"
        
        # First query
        initial_response = self.query(initial_query)
        print(f"Initial response: {initial_response[:200]}...")
        
        # Follow-up with history
        history = [
            {"role": "user", "content": initial_query},
            {"role": "assistant", "content": initial_response}
        ]
        followup_response = self.query(followup_query, history)
        print(f"Follow-up response: {followup_response[:200]}...")
        
        return results

if __name__ == "__main__":
    # Initialize the E2E test class
    try:
        tester = IAMRiskQueryE2E()
        
        # Run sample queries
        tester.run_sample_queries()
        
        # Interactive mode
        print("\n=== Interactive Query Mode (type 'exit' to quit) ===")
        conversation = []
        
        while True:
            user_query = input("\nEnter your query: ")
            if user_query.lower() in ('exit', 'quit'):
                break
                
            response = tester.query(user_query, conversation)
            print(f"\nResponse: {response}")
            
            # Add to conversation history
            conversation.append({"role": "user", "content": user_query})
            conversation.append({"role": "assistant", "content": response})
            
            # Keep conversation context to a reasonable size
            if len(conversation) > 6:  # Keep last 3 exchanges
                conversation = conversation[-6:]
        
        print("Exiting interactive mode")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    sys.exit(0) 