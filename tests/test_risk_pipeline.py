import os
import sys
import sqlite3
import json
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).resolve().parent.parent.parent.parent)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from iam_copilot.iam_graph.llm.risk_data_pipeline import RiskDataPipeline
from iam_copilot.iam_graph.risk_topics import RiskTopic

def print_db_contents(db_path):
    """Print database contents for debugging"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n=== DATABASE CONTENTS ===")
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row['name'] for row in cursor.fetchall()]
    
    for table in tables:
        print(f"\nTable: {table}")
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [row['name'] for row in cursor.fetchall()]
        print(f"Columns: {', '.join(columns)}")
        
        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
        count = cursor.fetchone()['count']
        print(f"Row count: {count}")
        
        # Print sample data if table has rows
        if count > 0:
            cursor.execute(f"SELECT * FROM {table} LIMIT 3")
            rows = cursor.fetchall()
            for row in rows:
                print(dict(row))
    
    # Count risk types
    print("\n=== RISK TYPE DISTRIBUTION ===")
    cursor.execute("SELECT risk_type, COUNT(*) as count FROM UserRiskTypes GROUP BY risk_type")
    for row in cursor.fetchall():
        print(f"{row['risk_type']}: {row['count']} users")
    
    # Check for users with multiple risk types
    print("\n=== USERS WITH MULTIPLE RISK TYPES ===")
    cursor.execute("""
        SELECT u.UserID, u.Name, COUNT(urt.risk_type) as risk_count, GROUP_CONCAT(urt.risk_type) as risks
        FROM Users u
        JOIN UserRiskTypes urt ON u.UserID = urt.UserID
        GROUP BY u.UserID
        HAVING COUNT(urt.risk_type) > 1
        LIMIT 5
    """)
    multi_risk_users = cursor.fetchall()
    if multi_risk_users:
        for user in multi_risk_users:
            print(f"User {user['Name']} ({user['UserID']}) has {user['risk_count']} risks: {user['risks']}")
    else:
        print("No users with multiple risk types found")
    
    conn.close()

def check_mock_data(mock_data_path):
    """Display the structure of the mock data file"""
    try:
        with open(mock_data_path, 'r') as f:
            data = json.load(f)
            print(f"\n=== MOCK DATA STRUCTURE ===")
            
            if isinstance(data, dict):
                print(f"Top-level keys: {list(data.keys())}")
                
                # Check for users
                if "users" in data:
                    users = data["users"]
                    print(f"Found {len(users)} users at data['users']")
                    if users:
                        print(f"Sample user keys: {list(users[0].keys())}")
                elif "Users" in data:
                    users = data["Users"]
                    print(f"Found {len(users)} users at data['Users']")
                    if users:
                        print(f"Sample user keys: {list(users[0].keys())}")
                else:
                    print("No users found at top level")
                    
                    # Check if nested in 'data'
                    if "data" in data and isinstance(data["data"], dict):
                        data_obj = data["data"]
                        print(f"Found nested data object with keys: {list(data_obj.keys())}")
                        
                        if "users" in data_obj:
                            users = data_obj["users"]
                            print(f"Found {len(users)} users at data['data']['users']")
                            if users:
                                print(f"Sample user keys: {list(users[0].keys())}")
                        elif "Users" in data_obj:
                            users = data_obj["Users"]
                            print(f"Found {len(users)} users at data['data']['Users']")
                            if users:
                                print(f"Sample user keys: {list(users[0].keys())}")
                
                # Check for roles
                if "roles" in data:
                    roles = data["roles"]
                    print(f"Found {len(roles)} roles at data['roles']")
                    if roles and roles[0]:
                        print(f"Sample role keys: {list(roles[0].keys())}")
                        if "AssociatedUsers" in roles[0]:
                            print(f"First role has {len(roles[0]['AssociatedUsers'])} associated users")
                
                # Check for applications
                if "applications" in data:
                    apps = data["applications"]
                    print(f"Found {len(apps)} applications at data['applications']")
                    if apps and apps[0]:
                        print(f"Sample application keys: {list(apps[0].keys())}")
            else:
                print(f"Data is not a dictionary: {type(data)}")
                
            return data
            
    except Exception as e:
        print(f"Error analyzing mock data: {e}")
        raise

def test_risk_pipeline():
    """Test the risk data pipeline with actual data"""
    print("=== TESTING RISK DATA PIPELINE ===")
    
    # Set up the database path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "test_risks.db")
    
    # Verify that the mock data file exists
    mock_data_path = "/Users/matangez/Documents/iam_graph/data/mock_data.json"
    if not os.path.exists(mock_data_path):
        print(f"Error: Mock data file not found at {mock_data_path}")
        return False
    
    print(f"Using mock data from: {mock_data_path}")
    
    # Analyze mock data structure
    data = check_mock_data(mock_data_path)
    
    # Run the pipeline
    print("\nRunning risk data pipeline...")
    pipeline = RiskDataPipeline(mock_data_path=mock_data_path, db_path=db_path)
    result = pipeline.run_pipeline()
    
    if result["success"]:
        print("Pipeline completed successfully!")
        print("Risk statistics:")
        for risk_type, count in result["statistics"].items():
            print(f"  {risk_type}: {count} users")
        
        # Validate database contents
        print_db_contents(db_path)
        
        # Verify all risk types have been checked
        risk_types_found = set(result["statistics"].keys())
        all_risk_types = {t.value for t in RiskTopic}
        missing_risk_types = all_risk_types - risk_types_found
        
        if missing_risk_types:
            print(f"\nWarning: Some risk types were not detected: {missing_risk_types}")
        else:
            print("\nAll risk types were correctly processed.")
        
        return True
    else:
        print(f"Pipeline failed: {result.get('error', 'Unknown error')}")
        return False

if __name__ == "__main__":
    success = test_risk_pipeline()
    print("\n=== TEST SUMMARY ===")
    if success:
        print("Risk data pipeline test completed successfully!")
    else:
        print("Risk data pipeline test failed.")
    
    sys.exit(0 if success else 1) 