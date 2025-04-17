#!/usr/bin/env python3

from langchain_community.utilities import SQLDatabase
from src.query_writer import QueryWriter
from pprint import pprint

def test_query():
    # Connect to the database
    db = SQLDatabase.from_uri("sqlite:///data/iam_risks.db")
    
    # Print database info
    print("Table names:")
    print(db.get_usable_table_names())
    
    print("\nTable info:")
    for info in db.get_table_info():
        print(info)
    
    # Test direct SQL query
    print("\nTesting direct SQL query:")
    result = db.run("SELECT * FROM Users LIMIT 5")
    print(result)
    
    # Test query writer
    print("\nTesting query writer:")
    q = QueryWriter(db)
    
    # Process a query
    query = "which users are inactive?"
    print(f"\nProcessing query: {query}")
    res = q.process_query(query)
    
    # Print the generated SQL
    print("\nGenerated SQL:")
    print(res.content)
    
    # Execute the generated SQL
    print("\nSQL result:")
    result = db.run(res.content)
    print(result)

if __name__ == "__main__":
    test_query() 