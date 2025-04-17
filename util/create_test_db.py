#!/usr/bin/env python3

import os
import sqlite3
from langchain_community.utilities import SQLDatabase

def create_test_db(db_path="test_iam_risk.db"):
    """Create a test SQLite database with the IAM risk schema and sample data.
    
    Args:
        db_path: Path to the database file to create
    """
    print(f"Creating test database at: {db_path}")
    
    # Delete the file if it already exists
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Create a connection to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create the schema based on the tables found in risk_view.db
    cursor.executescript('''
    -- Users table
    CREATE TABLE "Users" (
        "UserID" TEXT,
        "Name" TEXT NOT NULL,
        "Email" TEXT NOT NULL,
        "Department" TEXT NOT NULL,
        "Position" TEXT NOT NULL,
        "EmploymentStartDate" TEXT NOT NULL,
        "LastLogin" TEXT NOT NULL,
        "MFAStatus" TEXT NOT NULL,
        "AccountType" TEXT DEFAULT 'regular' NOT NULL,
        "Status" TEXT DEFAULT 'active' NOT NULL,
        risk_topic TEXT,
        PRIMARY KEY ("UserID")
    );
    
    -- Roles table
    CREATE TABLE "Roles" (
        "RoleID" TEXT,
        "RoleName" TEXT NOT NULL,
        "Description" TEXT NOT NULL,
        "Permissions" TEXT NOT NULL,
        PRIMARY KEY ("RoleID")
    );
    
    -- Applications table
    CREATE TABLE "Applications" (
        "ApplicationID" TEXT,
        "ApplicationName" TEXT NOT NULL,
        "Description" TEXT NOT NULL,
        PRIMARY KEY ("ApplicationID")
    );
    
    -- Groups table
    CREATE TABLE "Groups" (
        "GroupID" TEXT,
        "GroupName" TEXT NOT NULL,
        "Description" TEXT NOT NULL,
        PRIMARY KEY ("GroupID")
    );
    
    -- Resources table
    CREATE TABLE "Resources" (
        "ResourceID" TEXT,
        "ResourceName" TEXT NOT NULL,
        "Description" TEXT NOT NULL,
        "AccessPolicies" TEXT NOT NULL,
        PRIMARY KEY ("ResourceID")
    );
    
    -- UserRoles table
    CREATE TABLE "UserRoles" (
        "UserID" TEXT,
        "RoleID" TEXT,
        PRIMARY KEY ("UserID", "RoleID"),
        FOREIGN KEY("UserID") REFERENCES "Users" ("UserID"),
        FOREIGN KEY("RoleID") REFERENCES "Roles" ("RoleID")
    );
    
    -- UserGroups table
    CREATE TABLE "UserGroups" (
        "UserID" TEXT,
        "GroupID" TEXT,
        PRIMARY KEY ("UserID", "GroupID"),
        FOREIGN KEY("UserID") REFERENCES "Users" ("UserID"),
        FOREIGN KEY("GroupID") REFERENCES "Groups" ("GroupID")
    );
    
    -- UserApplications table
    CREATE TABLE "UserApplications" (
        "UserID" TEXT,
        "ApplicationID" TEXT,
        PRIMARY KEY ("UserID", "ApplicationID"),
        FOREIGN KEY("UserID") REFERENCES "Users" ("UserID"),
        FOREIGN KEY("ApplicationID") REFERENCES "Applications" ("ApplicationID")
    );
    
    -- ResourceRoles table
    CREATE TABLE "ResourceRoles" (
        "ResourceID" TEXT,
        "RoleID" TEXT,
        PRIMARY KEY ("ResourceID", "RoleID"),
        FOREIGN KEY("ResourceID") REFERENCES "Resources" ("ResourceID"),
        FOREIGN KEY("RoleID") REFERENCES "Roles" ("RoleID")
    );
    ''')
    
    # Insert sample data - Users
    user_data = [
        ('U001', 'Alice Johnson', 'alice@example.com', 'Engineering', 'Software Engineer', '2023-01-01', '2023-04-01', 'none', 'regular', 'active', 'NO_MFA_USERS'),
        ('U002', 'Bob Smith', 'bob@example.com', 'IT', 'IT Manager', '2022-01-01', '2023-05-01', 'sms', 'regular', 'active', 'WEAK_MFA_USERS'),
        ('U003', 'Charlie Davis', 'charlie@example.com', 'Finance', 'Accountant', '2021-06-15', '2022-10-01', 'authenticator_app', 'regular', 'active', 'INACTIVE_USERS'),
        ('U004', 'David Brown', 'david.brown@example.com', 'Engineering', 'DevOps Engineer', '2021-11-20', '2023-04-06', 'hardware_security_key', 'service', 'active', 'SERVICE_ACCOUNTS'),
        ('U005', 'Eva Martinez', 'eva.martinez@example.com', 'Marketing', 'Marketing Director', '2019-08-15', '2023-04-05', 'biometric', 'regular', 'active', None),
        ('U006', 'Frank Wilson', 'frank@example.com', 'Sales', 'Sales Representative', '2020-03-10', '2022-08-15', 'authenticator_app', 'regular', 'active', 'INACTIVE_USERS'),
        ('U007', 'Grace Lee', 'grace@example.com', 'Engineering', 'QA Engineer', '2022-05-20', '2023-03-30', 'none', 'regular', 'active', 'NO_MFA_USERS'),
        ('U008', 'Henry Taylor', 'henry@example.com', 'HR', 'HR Specialist', '2021-09-01', '2023-04-02', 'sms', 'regular', 'active', 'WEAK_MFA_USERS'),
        ('U009', 'Isabel Garcia', 'isabel@example.com', 'Finance', 'Financial Analyst', '2020-11-15', '2023-04-03', 'hardware_security_key', 'regular', 'active', None),
        ('U010', 'James Miller', 'james@example.com', 'Engineering', 'Software Architect', '2019-07-01', '2022-12-20', 'authenticator_app', 'regular', 'active', 'INACTIVE_USERS')
    ]
    cursor.executemany('INSERT INTO Users VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', user_data)
    
    # Insert sample data - Roles
    role_data = [
        ('R001', 'Admin', 'Full administrative access', '["Create", "Read", "Update", "Delete"]'),
        ('R002', 'Viewer', 'Read-only access', '["Read"]'),
        ('R003', 'Editor', 'Can create and edit content', '["Create", "Read", "Update"]'),
        ('R004', 'Manager', 'Team management access', '["Read", "Update", "Approve"]'),
        ('R005', 'Finance', 'Financial system access', '["Read", "Update", "Approve"]')
    ]
    cursor.executemany('INSERT INTO Roles VALUES (?, ?, ?, ?)', role_data)
    
    # Insert sample data - Applications
    app_data = [
        ('A001', 'Payroll System', 'Handles employee payroll'),
        ('A002', 'CRM System', 'Customer relationship management'),
        ('A003', 'Project Management', 'Team project tracking'),
        ('A004', 'Marketing Platform', 'Marketing campaign management'),
        ('A005', 'Financial System', 'Financial management and reporting')
    ]
    cursor.executemany('INSERT INTO Applications VALUES (?, ?, ?)', app_data)
    
    # Insert sample data - Groups
    group_data = [
        ('G001', 'Engineering Team', 'Group for all engineering staff'),
        ('G002', 'Sales Team', 'Group for sales department'),
        ('G003', 'Marketing Team', 'Group for marketing department'),
        ('G004', 'IT Team', 'Group for IT department'),
        ('G005', 'HR Team', 'Group for HR department')
    ]
    cursor.executemany('INSERT INTO Groups VALUES (?, ?, ?)', group_data)
    
    # Insert sample data - Resources
    resource_data = [
        ('RES001', 'Internal Database', 'Contains sensitive company data', '["Admin-only"]'),
        ('RES002', 'Marketing Drive', 'Shared drive for marketing materials', '["Read-only", "Editor-access"]'),
        ('RES003', 'Development Server', 'Development environment server', '["Developer-access"]'),
        ('RES004', 'HR Documents', 'Confidential HR documentation', '["Restricted-access"]'),
        ('RES005', 'Financial Reports', 'Company financial reports and statements', '["Finance-only"]')
    ]
    cursor.executemany('INSERT INTO Resources VALUES (?, ?, ?, ?)', resource_data)
    
    # Insert sample data - UserRoles
    user_roles_data = [
        ('U001', 'R001'),  # Alice is an Admin
        ('U002', 'R004'),  # Bob is a Manager
        ('U003', 'R005'),  # Charlie has Finance access
        ('U004', 'R003'),  # David is an Editor
        ('U005', 'R003'),  # Eva is an Editor
        ('U006', 'R002'),  # Frank is a Viewer
        ('U007', 'R003'),  # Grace is an Editor
        ('U008', 'R004'),  # Henry is a Manager
        ('U009', 'R005'),  # Isabel has Finance access
        ('U010', 'R001')   # James is an Admin
    ]
    cursor.executemany('INSERT INTO UserRoles VALUES (?, ?)', user_roles_data)
    
    # Insert sample data - UserGroups
    user_groups_data = [
        ('U001', 'G001'),  # Alice is in Engineering
        ('U002', 'G004'),  # Bob is in IT
        ('U003', 'G001'),  # Charlie is in Engineering (for example purposes)
        ('U004', 'G001'),  # David is in Engineering
        ('U005', 'G003'),  # Eva is in Marketing
        ('U006', 'G002'),  # Frank is in Sales
        ('U007', 'G001'),  # Grace is in Engineering
        ('U008', 'G005'),  # Henry is in HR
        ('U009', 'G001'),  # Isabel is in Engineering (example purpose)
        ('U010', 'G001')   # James is in Engineering
    ]
    cursor.executemany('INSERT INTO UserGroups VALUES (?, ?)', user_groups_data)
    
    # Insert sample data - UserApplications
    user_apps_data = [
        ('U001', 'A003'),  # Alice uses Project Management
        ('U002', 'A002'),  # Bob uses CRM
        ('U003', 'A001'),  # Charlie uses Payroll
        ('U003', 'A005'),  # Charlie also uses Financial System
        ('U004', 'A003'),  # David uses Project Management
        ('U005', 'A004'),  # Eva uses Marketing Platform
        ('U006', 'A002'),  # Frank uses CRM
        ('U007', 'A003'),  # Grace uses Project Management
        ('U008', 'A003'),  # Henry uses Project Management
        ('U009', 'A001'),  # Isabel uses Payroll
        ('U009', 'A005'),  # Isabel also uses Financial System
        ('U010', 'A003')   # James uses Project Management
    ]
    cursor.executemany('INSERT INTO UserApplications VALUES (?, ?)', user_apps_data)
    
    # Insert sample data - ResourceRoles
    resource_roles_data = [
        ('RES001', 'R001'),  # Internal Database - Admin access
        ('RES002', 'R002'),  # Marketing Drive - Viewer access
        ('RES002', 'R003'),  # Marketing Drive - Editor access
        ('RES003', 'R003'),  # Development Server - Editor access
        ('RES004', 'R001'),  # HR Documents - Admin access 
        ('RES004', 'R004'),  # HR Documents - Manager access
        ('RES005', 'R005')   # Financial Reports - Finance access
    ]
    cursor.executemany('INSERT INTO ResourceRoles VALUES (?, ?)', resource_roles_data)
    
    # Commit changes and close connection
    conn.commit()
    conn.close()
    
    print(f"Test database created at: {db_path}")
    print(f"Database size: {os.path.getsize(db_path)} bytes")
    return db_path

def main():
    """Create the test database and validate it was created correctly."""
    db_path = create_test_db()
    
    # Validate the database was created correctly
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        print("\nValidating database...")
        
        # Connect to the database using langchain
        db = SQLDatabase.from_uri(f"sqlite:///{db_path}")
        
        # Get all tables
        tables = db.get_usable_table_names()
        print(f"Found {len(tables)} tables: {', '.join(tables)}")
        
        # Get schema for each table
        for table in tables:
            schema = db.get_table_info([table])
            print(f"\nSchema for {table}:\n{schema}")
            
        print("\nDatabase created and validated successfully!")
    else:
        print("Error: Database creation failed or database is empty.")

if __name__ == "__main__":
    main() 