#!/usr/bin/env python3

import os
import sqlite3
from langchain_community.utilities import SQLDatabase
from agent_eval import list_tables_tool, get_schema_tool, db_query_tool
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Set up database connection (same as in agent_eval.py)
DB_PATH = "iam_risk.db"
db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH}")

def get_actual_tables():
    """Get the actual table names from the database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tables
    except Exception as e:
        print(f"Error getting tables: {e}")
        return []

def test_tool(name, tool, args=None):
    """Test a tool and print its output"""
    print(f"\n=== Testing {name} ===")
    try:
        if args is None:
            result = tool.invoke({})
        else:
            result = tool.invoke(args)
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all tool tests"""
    print("Starting tool tests...")
    
    # Get actual tables first
    actual_tables = get_actual_tables()
    print(f"Actual tables in database: {actual_tables}")
    
    if not actual_tables:
        print("No tables found in database or database not accessible.")
        return
    
    # Test list_tables_tool (gets all table names)
    test_tool("list_tables_tool", list_tables_tool)
    
    # Test get_schema_tool with the actual tables
    test_tool("get_schema_tool", get_schema_tool, {"table_names": actual_tables})
    
    # Create queries based on actual tables
    sample_queries = []
    
    # For each table, create a simple SELECT query
    for table in actual_tables:
        sample_queries.append(f"SELECT * FROM {table} LIMIT 3;")
    
    # Add some specific queries if we have certain tables
    if "Users" in actual_tables:
        sample_queries.append("SELECT * FROM Users WHERE MFAStatus = 'none' LIMIT 5;")
    
    if "users" in actual_tables:
        sample_queries.append("SELECT * FROM users WHERE mfa_status = 'none' LIMIT 5;")
    
    # Test db_query_tool with the queries
    for i, query in enumerate(sample_queries):
        test_tool(f"db_query_tool (query {i+1})", db_query_tool, query)

if __name__ == "__main__":
    main() 