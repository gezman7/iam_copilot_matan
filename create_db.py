#!/usr/bin/env python3

import os
import logging
from src.loader import JsonFileLoader
from src.snapshot import IAMDataSnapshot
from src.risk_view import create_risk_view

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('recreate_db')

def main():
    """Create the IAM risk database from mock data."""
    # Define file paths
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    mock_data_path = os.path.join(data_dir, 'mock_data.json')
    db_path = os.path.join(data_dir, 'iam_risks.db')
    
    # Load data from JSON
    logger.info(f"Loading mock data from {mock_data_path}")
    loader = JsonFileLoader(mock_data_path)
    snapshot = loader.load_data()
    
    # Create the risk database
    logger.info(f"Creating risk database at {db_path}")
    create_risk_view(snapshot, db_path)
    
    # Verify database was created
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        logger.info(f"Successfully created database: {db_path}")
    else:
        logger.error(f"Failed to create database or database is empty: {db_path}")

if __name__ == "__main__":
    main() 