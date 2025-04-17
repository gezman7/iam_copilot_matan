from risk_view import create_risk_view
from loader import JsonFileLoader
# Define paths
mock_data_path = "/Users/matangez/Documents/iam_agent/data/mock_data.json"
risk_db_path = "risk_views.db"

# Load data from JSON file
loader = JsonFileLoader(mock_data_path)
snapshot = loader.load_data()

# Create risk view database
create_risk_view(snapshot, risk_db_path)

print(f"Risk view database created at {risk_db_path}") 