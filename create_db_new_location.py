#!/usr/bin/env python3
import os
import argparse
from src.db.risk_view import create_risk_view
from src.db.loader import JsonFileLoader

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Create risk view database in data directory')
    parser.add_argument('--force', action='store_true', help='Force recreation of database even if it exists')
    args = parser.parse_args()

    # Define paths - use absolute path for the db file
    mock_data_path = "/Users/matangez/Documents/iam_agent/data/mock_data.json"
    data_dir = "/Users/matangez/Documents/iam_agent/data"
    
    # Make sure the directory exists
    os.makedirs(data_dir, exist_ok=True)
    
    # Full path to the database file
    risk_db_path = os.path.join(data_dir, "risk_views.db")

    # Load data from JSON file
    loader = JsonFileLoader(mock_data_path)
    snapshot = loader.load_data()

    # Create risk view database
    create_risk_view(snapshot, risk_db_path, force_recreate=args.force)

    print(f"Risk view database created at {risk_db_path}")
    print(f"Relative path for use in code: data/risk_views.db")

if __name__ == "__main__":
    main() 