#!/usr/bin/env python3

import os
import sys
from langchain_community.utilities import SQLDatabase

def test_database(db_path):
    """Test a specific database file and print its contents"""
    print(f"\n\n======== Testing Database: {db_path} ========")
    if not os.path.exists(db_path):
        print(f"Database file does not exist: {db_path}")
        return False
    
    file_size = os.path.getsize(db_path)
    if file_size == 0:
        print(f"Database file exists but is empty (0 bytes): {db_path}")
        return False
        
    print(f"Database file exists with size: {file_size} bytes")
    
    try:
        # Connect to the database
        db_uri = f"sqlite:///{db_path}"
        print(f"Connecting to: {db_uri}")
        db = SQLDatabase.from_uri(db_uri)
        
        # Get all table names
        tables = db.get_usable_table_names()
        print(f"Found {len(tables)} tables: {', '.join(tables)}")
        
        if not tables:
            print("No tables found in the database.")
            return False
        
        # Query each table
        for table in tables:
            print(f"\n----- Table: {table} -----")
            # Run a simple query to get a few rows from each table
            try:
                query = f"SELECT * FROM {table} LIMIT 5"
                print(f"Query: {query}")
                result = db.run(query)
                print(f"Result:\n{result}\n")
            except Exception as e:
                print(f"Error querying {table}: {str(e)}\n")
        
        # Get and print table schema info for all tables
        print("\n----- Table Schema Information -----")
        for table in tables:
            try:
                schema_info = db.get_table_info([table])
                print(f"\nSchema for {table}:\n{schema_info}")
            except Exception as e:
                print(f"Error getting schema for {table}: {str(e)}")
                
        return True
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        return False

def main():
    # Check if a specific database path was provided
    if len(sys.argv) > 1:
        # Use the specified database path
        db_path = sys.argv[1]
        print(f"Testing specified database: {db_path}")
        test_database(db_path)
        return
    
    # Default test paths if no specific path is provided
    database_files = [
        "risk_views.db",
        "iam_risks.db", 
        "iam_risk.db",
        "data/iam_risks.db",
        "data/risk_views.db",
        "data/risk_view.db",
        "src/iam_risk.db"
    ]
    
    success = False
    for db_file in database_files:
        if test_database(db_file):
            success = True
    
    if not success:
        print("\n\nNo valid databases found with tables.")
        print("You may need to create the database first using create_db.py or another setup script.")

if __name__ == "__main__":
    main() 