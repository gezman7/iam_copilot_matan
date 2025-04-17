from langchain_community.utilities import SQLDatabase
import os

def main():
    db_path = "risk_views.db"
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    
    try:
        print(db.get_table_info())
        print(db.get_table_names())
    finally:
        # Close the database connection properly
        if hasattr(db, '_engine') and hasattr(db._engine, 'dispose'):
            db._engine.dispose()
            print("Database connection closed")


if __name__ == "__main__":
    main()