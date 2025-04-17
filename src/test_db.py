from langchain_community.utilities import SQLDatabase

def main():
    db_path = "risk_views.db"
    db =SQLDatabase.from_uri(f"sqlite:///{db_path}")

    print(db.get_table_info())

if __name__ == "__main__":
    main()