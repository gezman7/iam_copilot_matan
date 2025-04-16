import os
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).resolve().parent.parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from iam_copilot.iam_graph.llm.risk_data_pipeline import RiskDataPipeline
from iam_copilot.iam_graph.llm.search_detection_snapshot import SearchDetectionSnapshot
from langchain_openai import ChatOpenAI

def initialize_database():
    """Initialize test database"""
    print("=== Initializing test database ===")
    
    # Set up the database path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "test_risks.db")
    
    # Set mock data path
    mock_data_path = "/Users/matangez/Documents/iam_graph/data/mock_data.json"
    if not os.path.exists(mock_data_path):
        print(f"Error: Mock data file not found at {mock_data_path}")
        return None
    
    # Run the pipeline
    pipeline = RiskDataPipeline(mock_data_path=mock_data_path, db_path=db_path)
    result = pipeline.run_pipeline()
    
    if result["success"]:
        print("Database initialized successfully!")
        print(f"Database path: {result['db_path']}")
        return result["db_path"]
    else:
        print(f"Database initialization failed: {result.get('error', 'Unknown error')}")
        return None

def test_search_queries(db_path):
    """Test search queries on the risk database"""
    print("\n=== Testing search queries ===")
    
    # Initialize language model
    try:
        llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo")
        print("Language model initialized successfully")
    except Exception as e:
        print(f"Error initializing language model: {e}")
        print("Skipping search tests")
        return
    
    # Initialize search detection snapshot
    search = SearchDetectionSnapshot(llm, db_path=db_path)
    
    # Test queries
    test_queries = [
        "Show me all users with weak MFA",
        "How many service accounts do we have?",
        "List the names of inactive users",
        "Which department has the most users with weak MFA?",
        "Show me users who have never logged in",
        "Invalid query without risk type",
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        result = search.process_query(query)
        print(f"Result: {result}")
        print("-" * 50)
    
    # Test follow-up query
    print("\nTesting follow-up query:")
    initial_query = "Show me all users with weak MFA"
    followup_query = "Which ones are in the IT department?"
    
    print(f"Initial query: {initial_query}")
    initial_result = search.process_query(initial_query)
    print(f"Initial result: {initial_result}")
    
    print(f"\nFollow-up query: {followup_query}")
    chat_history = f"User: {initial_query}\nAssistant: {initial_result}"
    followup_result = search.process_query(followup_query, chat_history)
    print(f"Follow-up result: {followup_result}")

if __name__ == "__main__":
    # Initialize database
    db_path = initialize_database()
    
    if db_path:
        # Test search queries
        test_search_queries(db_path)
        print("\n=== Test completed ===")
    else:
        print("Test skipped due to database initialization failure.")
        sys.exit(1)
    
    sys.exit(0) 