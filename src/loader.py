import json
import logging
import sqlite3
from langchain_community.utilities import SQLDatabase


from snapshot import IAMDataSnapshot

logger = logging.getLogger(__name__)

class JsonFileLoader():
    """Loader implementation for JSON data that loads from a JSON file."""
    
    def __init__(self, file_path: str):
        """Initialize the JSON loader with a path to the JSON file.
        
        Args:
            file_path: Path to the JSON file containing IAM data
        """
        self.file_path = file_path

    def load_data(self) -> IAMDataSnapshot:
        """Load data from JSON file and return an IAMDataSnapshot.

        Returns:
            IAMDataSnapshot: A snapshot of the data loaded from the JSON file
        """
        logger.info(f"Loading data from JSON file: {self.file_path}")

        try:
            with open(self.file_path, 'r') as file:
                data = json.load(file)
        except Exception as e:
            logger.error(f"Error loading JSON data: {str(e)}")
            raise e
        
        # Extract the data sections
        users = data.get("Users", [])
        roles = data.get("Roles", [])
        applications = data.get("Applications", [])
        groups = data.get("Groups", [])
        resources = data.get("Resources", [])
        
        # Create and return a snapshot
        return IAMDataSnapshot(
            users=users,
            roles=roles,
            applications=applications,
            groups=groups,
            resources=resources
        )
    
def create_test_db(db_path=":memory:"):
    """Create a test SQLite database for testing the query writer.
    
    This function creates an in-memory SQLite database with tables and sample data
    that match the schema expected by the test cases.
    
    Args:
        db_path: Path to the database file or ":memory:" for in-memory database
        
    Returns:
        SQLDatabase: A SQLDatabase instance connected to the test database
    """
    # Create a connection to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.executescript('''
    -- Users table
    CREATE TABLE IF NOT EXISTS Users (
        UserID INTEGER PRIMARY KEY,
        Name TEXT,
        Email TEXT,
        Department TEXT,
        LastLogin DATETIME,
        risk_topic TEXT
    );
    
    -- Groups table
    CREATE TABLE IF NOT EXISTS Groups (
        GroupID INTEGER PRIMARY KEY,
        GroupName TEXT
    );
    
    -- UserGroups table
    CREATE TABLE IF NOT EXISTS UserGroups (
        UserID INTEGER,
        GroupID INTEGER,
        PRIMARY KEY (UserID, GroupID),
        FOREIGN KEY (UserID) REFERENCES Users(UserID),
        FOREIGN KEY (GroupID) REFERENCES Groups(GroupID)
    );
    
    -- Roles table
    CREATE TABLE IF NOT EXISTS Roles (
        RoleID INTEGER PRIMARY KEY,
        RoleName TEXT
    );
    
    -- UserRoles table
    CREATE TABLE IF NOT EXISTS UserRoles (
        UserID INTEGER,
        RoleID INTEGER,
        PRIMARY KEY (UserID, RoleID),
        FOREIGN KEY (UserID) REFERENCES Users(UserID),
        FOREIGN KEY (RoleID) REFERENCES Roles(RoleID)
    );
    
    -- Applications table
    CREATE TABLE IF NOT EXISTS Applications (
        ApplicationID INTEGER PRIMARY KEY,
        ApplicationName TEXT
    );
    
    -- UserApplications table
    CREATE TABLE IF NOT EXISTS UserApplications (
        UserID INTEGER,
        ApplicationID INTEGER,
        PRIMARY KEY (UserID, ApplicationID),
        FOREIGN KEY (UserID) REFERENCES Users(UserID),
        FOREIGN KEY (ApplicationID) REFERENCES Applications(ApplicationID)
    );
    ''')
    
    # Insert sample data - Users
    users_data = [
        (1, 'John Doe', 'john.doe@example.com', 'IT', '2023-04-10', 'NO_MFA_USERS'),
        (2, 'Jane Smith', 'jane.smith@example.com', 'Finance', '2023-05-15', 'WEAK_MFA_USERS'),
        (3, 'Bob Jackson', 'bob.jackson@example.com', 'Engineering', '2022-11-30', 'INACTIVE_USERS'),
        (4, 'Carol Williams', 'carol.williams@example.com', 'Finance', '2023-05-01', 'WEAK_MFA_USERS'),
        (5, 'Alice Smith', 'alice.smith@example.com', 'HR', '2023-04-20', 'NO_MFA_USERS'),
        (8, 'CI/CD Service', 'cicd@example.com', 'IT', None, 'SERVICE_ACCOUNTS'),
        (10, 'Backup Service', 'backup@example.com', 'IT', None, 'SERVICE_ACCOUNTS'),
        (12, 'DB Admin', 'dbadmin@example.com', 'IT', '2023-01-15', 'LOCAL_ACCOUNTS'),
        (15, 'David Chen', 'david.chen@example.com', 'Marketing', '2023-02-28', 'PARTIALLY_OFFBOARDED_USERS'),
        (16, 'Emily Brown', 'emily.brown@example.com', 'HR', '2023-03-15', 'PARTIALLY_OFFBOARDED_USERS'),
        (22, 'Frank Thomas', 'frank.thomas@example.com', 'Sales', None, 'RECENTLY_JOINED_USERS')
    ]
    cursor.executemany('INSERT INTO Users VALUES (?, ?, ?, ?, ?, ?)', users_data)
    
    # Insert sample data - Groups
    groups_data = [
        (1, 'Engineering'),
        (2, 'Finance'),
        (3, 'HR'),
        (4, 'IT'),
        (5, 'Marketing'),
        (6, 'Sales')
    ]
    cursor.executemany('INSERT INTO Groups VALUES (?, ?)', groups_data)
    
    # Insert sample data - UserGroups
    user_groups_data = [
        (1, 4),  # John Doe is in IT
        (2, 2),  # Jane Smith is in Finance
        (3, 1),  # Bob Jackson is in Engineering
        (4, 2),  # Carol Williams is in Finance
        (5, 3),  # Alice Smith is in HR
        (8, 4),  # CI/CD Service is in IT
        (10, 4), # Backup Service is in IT
        (12, 4), # DB Admin is in IT
        (15, 5), # David Chen is in Marketing
        (16, 3), # Emily Brown is in HR
        (22, 6)  # Frank Thomas is in Sales
    ]
    cursor.executemany('INSERT INTO UserGroups VALUES (?, ?)', user_groups_data)
    
    # Insert sample data - Roles
    roles_data = [
        (1, 'User'),
        (2, 'Admin'),
        (3, 'Manager'),
        (4, 'Developer'),
        (5, 'Analyst')
    ]
    cursor.executemany('INSERT INTO Roles VALUES (?, ?)', roles_data)
    
    # Insert sample data - UserRoles
    user_roles_data = [
        (1, 3),  # John Doe is a Manager
        (2, 5),  # Jane Smith is an Analyst
        (3, 4),  # Bob Jackson is a Developer
        (4, 5),  # Carol Williams is an Analyst
        (5, 1),  # Alice Smith is a User
        (8, 2),  # CI/CD Service is an Admin
        (10, 2), # Backup Service is an Admin
        (12, 2), # DB Admin is an Admin
        (15, 1), # David Chen is a User
        (16, 3), # Emily Brown is a Manager
        (22, 1)  # Frank Thomas is a User
    ]
    cursor.executemany('INSERT INTO UserRoles VALUES (?, ?)', user_roles_data)
    
    # Insert sample data - Applications
    applications_data = [
        (1, 'Email System'),
        (2, 'Financial System'),
        (3, 'HR System'),
        (4, 'Customer Database'),
        (5, 'Development Tools')
    ]
    cursor.executemany('INSERT INTO Applications VALUES (?, ?)', applications_data)
    
    # Insert sample data - UserApplications
    user_applications_data = [
        (1, 1),  # John Doe has access to Email System
        (1, 5),  # John Doe has access to Development Tools
        (2, 1),  # Jane Smith has access to Email System
        (2, 2),  # Jane Smith has access to Financial System
        (3, 1),  # Bob Jackson has access to Email System
        (3, 5),  # Bob Jackson has access to Development Tools
        (4, 1),  # Carol Williams has access to Email System
        (4, 2),  # Carol Williams has access to Financial System
        (5, 1),  # Alice Smith has access to Email System
        (5, 3),  # Alice Smith has access to HR System
        (8, 5),  # CI/CD Service has access to Development Tools
        (10, 1), # Backup Service has access to Email System
        (12, 4), # DB Admin has access to Customer Database
        (15, 4), # David Chen has access to Customer Database
        (16, 3), # Emily Brown has access to HR System
        (22, 1)  # Frank Thomas has access to Email System
    ]
    cursor.executemany('INSERT INTO UserApplications VALUES (?, ?)', user_applications_data)
    
    # Commit changes and create the SQLDatabase instance
    conn.commit()
    db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
    
    return db
    