from db.risk_view import create_risk_view
from db.loader import JsonFileLoader
import argparse

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Create risk view database from mock data')
    parser.add_argument('--force', action='store_true', help='Force recreation of database even if it exists')
    args = parser.parse_args()

    # Define paths
    mock_data_path = "/Users/matangez/Documents/iam_agent/data/mock_data.json"
    risk_db_path = "risk_views.db"

    # Load data from JSON file
    loader = JsonFileLoader(mock_data_path)
    snapshot = loader.load_data()

    # Create risk view database
    create_risk_view(snapshot, risk_db_path, force_recreate=args.force)

    print(f"Risk view database created at {risk_db_path}")

if __name__ == "__main__":
    main() 