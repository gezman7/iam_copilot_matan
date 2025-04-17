import os
import sqlite3
import json
import logging
from typing import Dict, Any, List
from .snapshot import IAMDataSnapshot
from src.models import RiskTopic

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_risk_view(snapshot: IAMDataSnapshot, db_path: str) -> None:
    """Create a SQLite database with risk information from an IAM data snapshot.
    
    This function analyzes an IAM data snapshot for various risk indicators,
    such as weak MFA, inactive users, etc., and creates a dedicated SQLite
    database with a risk-focused view. The database preserves all entity
    relationships from the original IAM data.
    
    Risk prioritization is implemented to handle cases where a user has
    multiple risk factors. For example, if a user has both weak MFA and
    is inactive, they will be tagged with the highest priority risk (weak MFA).
    
    Args:
        snapshot: The IAM data snapshot to analyze for risks
        db_path: Path to the SQLite database file to create
    """
    # Remove existing database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"Removed existing database at {db_path}")
    
    # Create a new SQLite database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    logger.info(f"Created new database at {db_path}")
    
    try:
        # Create all the necessary tables with the risk_topic column
        create_tables(cursor)
        
        # Process users and detect risks
        process_users_with_risks(cursor, snapshot)
        
        # Store roles, applications, groups, and resources
        store_roles(cursor, snapshot.roles)
        store_applications(cursor, snapshot.applications)
        store_groups(cursor, snapshot.groups)
        store_resources(cursor, snapshot.resources)
        
        # Create relationships
        create_relationships(cursor, snapshot)
        
        # Commit changes
        conn.commit()
        logger.info("Database populated with risk information successfully")
    
    except Exception as e:
        logger.error(f"Error creating risk view: {str(e)}")
        conn.rollback()
        raise
    finally:
        conn.close()

def delete_risk_db(db_path: str) -> None:
    """Delete the risk database file if it exists.
    
    Args:
        db_path: Path to the SQLite database file to delete
    """
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"Deleted database at {db_path}")
    else:
        logger.info(f"No database found at {db_path}")

def create_tables(cursor: sqlite3.Cursor) -> None:
    """Create all necessary tables for the risk database.
    
    The schema is similar to the original IAM database schema,
    with the addition of a risk_topic column in the Users table
    to track identified risks.
    
    Args:
        cursor: SQLite cursor for executing commands
    """
    # Users table with risk_topic column
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Users (
            UserID TEXT PRIMARY KEY,
            Name TEXT NOT NULL,
            Email TEXT NOT NULL,
            Department TEXT NOT NULL,
            Position TEXT NOT NULL,
            EmploymentStartDate TEXT NOT NULL,
            LastLogin TEXT NOT NULL,
            MFAStatus TEXT NOT NULL,
            AccountType TEXT NOT NULL DEFAULT 'regular',
            Status TEXT NOT NULL DEFAULT 'active',
            risk_topic TEXT
        )
    ''')

    # Roles table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Roles (
            RoleID TEXT PRIMARY KEY,
            RoleName TEXT NOT NULL,
            Description TEXT NOT NULL,
            Permissions TEXT NOT NULL
        )
    ''')

    # UserRoles relationship table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS UserRoles (
            UserID TEXT,
            RoleID TEXT,
            PRIMARY KEY (UserID, RoleID),
            FOREIGN KEY (UserID) REFERENCES Users(UserID),
            FOREIGN KEY (RoleID) REFERENCES Roles(RoleID)
        )
    ''')

    # Applications table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Applications (
            ApplicationID TEXT PRIMARY KEY,
            ApplicationName TEXT NOT NULL,
            Description TEXT NOT NULL
        )
    ''')

    # UserApplications relationship table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS UserApplications (
            UserID TEXT,
            ApplicationID TEXT,
            PRIMARY KEY (UserID, ApplicationID),
            FOREIGN KEY (UserID) REFERENCES Users(UserID),
            FOREIGN KEY (ApplicationID) REFERENCES Applications(ApplicationID)
        )
    ''')

    # Groups table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Groups (
            GroupID TEXT PRIMARY KEY,
            GroupName TEXT NOT NULL,
            Description TEXT NOT NULL
        )
    ''')

    # UserGroups relationship table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS UserGroups (
            UserID TEXT,
            GroupID TEXT,
            PRIMARY KEY (UserID, GroupID),
            FOREIGN KEY (UserID) REFERENCES Users(UserID),
            FOREIGN KEY (GroupID) REFERENCES Groups(GroupID)
        )
    ''')

    # Resources table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Resources (
            ResourceID TEXT PRIMARY KEY,
            ResourceName TEXT NOT NULL,
            Description TEXT NOT NULL,
            AccessPolicies TEXT NOT NULL
        )
    ''')

    # ResourceRoles relationship table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ResourceRoles (
            ResourceID TEXT,
            RoleID TEXT,
            PRIMARY KEY (ResourceID, RoleID),
            FOREIGN KEY (ResourceID) REFERENCES Resources(ResourceID),
            FOREIGN KEY (RoleID) REFERENCES Roles(RoleID)
        )
    ''')
    
    # Create a view for users with risks
    cursor.execute('''
        CREATE VIEW IF NOT EXISTS UserRiskView AS
        SELECT 
            UserID, Name, Email, Department, Position, EmploymentStartDate, 
            LastLogin, MFAStatus, AccountType, Status, risk_topic
        FROM Users 
        WHERE risk_topic IS NOT NULL
    ''')
    
    logger.info("Created database tables and views")

def process_users_with_risks(cursor: sqlite3.Cursor, snapshot: IAMDataSnapshot) -> None:
    """Process users and detect risks, storing them in the database.
    
    This function implements the core risk detection and prioritization logic:
    1. Identify all risks for each user
    2. Apply a priority order to handle conflicts
    3. Assign each user their highest priority risk
    4. Store users with their assigned risk in the database
    
    Args:
        cursor: SQLite cursor for executing commands
        snapshot: IAM data snapshot to analyze
    """
    # Track which users have which risks - map of UserID to list of risk topics
    user_risks = {}
    
    # Collect all risks for each user
    for risk_topic in RiskTopic:
        risky_users = snapshot.detect_risk(risk_topic)
        logger.info(f"Found {len(risky_users)} users with risk topic {risk_topic.name}")
        
        for user in risky_users:
            user_id = user['UserID']
            if user_id not in user_risks:
                user_risks[user_id] = []
            user_risks[user_id].append(risk_topic)
    
    # Risk priority order (highest to lowest)
    # This determines which risk is assigned when a user has multiple risks
    risk_priority = [
        RiskTopic.WEAK_MFA_USERS,           # Security risk: Weak authentication
        RiskTopic.NO_MFA_USERS,             # Security risk: No authentication
        RiskTopic.INACTIVE_USERS,           # Access risk: Inactive user still has access
        RiskTopic.PARTIALLY_OFFBOARDED_USERS, # Access risk: Offboarded user still in system
        RiskTopic.NEVER_LOGGED_IN_USERS,    # Access risk: User hasn't logged in recently
        RiskTopic.SERVICE_ACCOUNTS,         # Management risk: Service account needs review
        RiskTopic.LOCAL_ACCOUNTS,           # Management risk: Local account needs review
        RiskTopic.RECENTLY_JOINED_USERS     # Monitoring: New account to monitor
    ]
    
    # Now assign the highest priority risk to each user and insert
    for user in snapshot.users:
        user_id = user['UserID']
        if user_id in user_risks and user_risks[user_id]:
            # Sort by priority
            user_risks[user_id].sort(key=lambda x: risk_priority.index(x))
            # Get highest priority risk
            highest_risk = user_risks[user_id][0]
            logger.debug(f"Assigning risk {highest_risk.value} to user {user_id}")
            insert_user_with_risk(cursor, user, highest_risk.value)
        else:
            # No risks for this user
            insert_user_without_risk(cursor, user)
    
    # Verify we have users with each risk topic
    for risk_topic in RiskTopic:
        cursor.execute("SELECT COUNT(*) FROM Users WHERE risk_topic = ?", (risk_topic.value,))
        count = cursor.fetchone()[0]
        logger.info(f"Verified {count} users with {risk_topic.value} risk in database")
    
    # Total users with risks
    cursor.execute("SELECT COUNT(*) FROM Users WHERE risk_topic IS NOT NULL")
    total_risky_users = cursor.fetchone()[0]
    logger.info(f"Total {total_risky_users} users with risks in database")
    
    logger.info(f"Processed and stored {len(snapshot.users)} users with risk detection")

def insert_user_with_risk(cursor: sqlite3.Cursor, user: Dict[str, Any], risk_topic: str) -> None:
    """Insert a user with a specific risk topic.
    
    Args:
        cursor: SQLite cursor for executing commands
        user: User dictionary
        risk_topic: Risk topic string
    """
    cursor.execute('''
        INSERT OR REPLACE INTO Users 
        (UserID, Name, Email, Department, Position, EmploymentStartDate, 
        LastLogin, MFAStatus, AccountType, Status, risk_topic)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user['UserID'],
        user['Name'],
        user['Email'],
        user['Department'],
        user['Position'],
        user['EmploymentStartDate'],
        user.get('LastLogin', ''),
        user['MFAStatus'],
        user.get('AccountType', 'regular'),
        user.get('Status', 'active'),
        risk_topic
    ))

def insert_user_without_risk(cursor: sqlite3.Cursor, user: Dict[str, Any]) -> None:
    """Insert a user without any risk topic.
    
    Args:
        cursor: SQLite cursor for executing commands
        user: User dictionary
    """
    cursor.execute('''
        INSERT OR REPLACE INTO Users 
        (UserID, Name, Email, Department, Position, EmploymentStartDate, 
        LastLogin, MFAStatus, AccountType, Status, risk_topic)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
    ''', (
        user['UserID'],
        user['Name'],
        user['Email'],
        user['Department'],
        user['Position'],
        user['EmploymentStartDate'],
        user.get('LastLogin', ''),
        user['MFAStatus'],
        user.get('AccountType', 'regular'),
        user.get('Status', 'active')
    ))

def store_roles(cursor: sqlite3.Cursor, roles: List[Dict[str, Any]]) -> None:
    """Store roles in the database.
    
    Args:
        cursor: SQLite cursor for executing commands
        roles: List of role dictionaries
    """
    for role in roles:
        cursor.execute('''
            INSERT OR REPLACE INTO Roles 
            (RoleID, RoleName, Description, Permissions)
            VALUES (?, ?, ?, ?)
        ''', (
            role['RoleID'],
            role['RoleName'],
            role['Description'],
            json.dumps(role['Permissions'])
        ))
    
    logger.info(f"Stored {len(roles)} roles")

def store_applications(cursor: sqlite3.Cursor, applications: List[Dict[str, Any]]) -> None:
    """Store applications in the database.
    
    Args:
        cursor: SQLite cursor for executing commands
        applications: List of application dictionaries
    """
    for app in applications:
        cursor.execute('''
            INSERT OR REPLACE INTO Applications 
            (ApplicationID, ApplicationName, Description)
            VALUES (?, ?, ?)
        ''', (
            app['ApplicationID'],
            app['ApplicationName'],
            app['Description']
        ))
    
    logger.info(f"Stored {len(applications)} applications")

def store_groups(cursor: sqlite3.Cursor, groups: List[Dict[str, Any]]) -> None:
    """Store groups in the database.
    
    Args:
        cursor: SQLite cursor for executing commands
        groups: List of group dictionaries
    """
    for group in groups:
        cursor.execute('''
            INSERT OR REPLACE INTO Groups 
            (GroupID, GroupName, Description)
            VALUES (?, ?, ?)
        ''', (
            group['GroupID'],
            group['GroupName'],
            group['Description']
        ))
    
    logger.info(f"Stored {len(groups)} groups")

def store_resources(cursor: sqlite3.Cursor, resources: List[Dict[str, Any]]) -> None:
    """Store resources in the database.
    
    Args:
        cursor: SQLite cursor for executing commands
        resources: List of resource dictionaries
    """
    for resource in resources:
        cursor.execute('''
            INSERT OR REPLACE INTO Resources 
            (ResourceID, ResourceName, Description, AccessPolicies)
            VALUES (?, ?, ?, ?)
        ''', (
            resource['ResourceID'],
            resource['ResourceName'],
            resource['Description'],
            json.dumps(resource['AccessPolicies'])
        ))
    
    logger.info(f"Stored {len(resources)} resources")

def create_relationships(cursor: sqlite3.Cursor, snapshot: IAMDataSnapshot) -> None:
    """Create relationship records between entities.
    
    This preserves the relationships between users, roles, applications,
    groups, and resources in the risk database.
    
    Args:
        cursor: SQLite cursor for executing commands
        snapshot: IAM data snapshot with relationship information
    """
    # Create UserRoles relationships
    for role in snapshot.roles:
        for user_id in role.get('AssociatedUsers', []):
            cursor.execute('''
                INSERT OR IGNORE INTO UserRoles (UserID, RoleID)
                VALUES (?, ?)
            ''', (user_id, role['RoleID']))
    
    # Create UserApplications relationships
    for app in snapshot.applications:
        for user_id in app.get('AssociatedUsers', []):
            cursor.execute('''
                INSERT OR IGNORE INTO UserApplications (UserID, ApplicationID)
                VALUES (?, ?)
            ''', (user_id, app['ApplicationID']))
    
    # Create UserGroups relationships
    for group in snapshot.groups:
        for user_id in group.get('AssociatedUsers', []):
            cursor.execute('''
                INSERT OR IGNORE INTO UserGroups (UserID, GroupID)
                VALUES (?, ?)
            ''', (user_id, group['GroupID']))
    
    # Create ResourceRoles relationships
    for resource in snapshot.resources:
        for role_id in resource.get('AssociatedRoles', []):
            cursor.execute('''
                INSERT OR IGNORE INTO ResourceRoles (ResourceID, RoleID)
                VALUES (?, ?)
            ''', (resource['ResourceID'], role_id))
    
    logger.info("Created all entity relationships") 