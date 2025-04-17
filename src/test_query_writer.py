import unittest
from unittest.mock import MagicMock, patch
from src.query_writer import QueryWriter
from src.models import RiskTopic
from langchain_core.messages import AIMessage

class TestQueryWriter(unittest.TestCase):
    def setUp(self):
        # Mock the database
        self.mock_db = MagicMock()
        
        # Set up schema and tables for the mock database
        self.mock_db.get_table_info.return_value = [
            "CREATE TABLE Users (UserID INTEGER PRIMARY KEY, Name TEXT, Email TEXT, Department TEXT, LastLogin DATETIME, risk_topic TEXT)",
            "CREATE TABLE UserGroups (UserID INTEGER, GroupID INTEGER, PRIMARY KEY (UserID, GroupID))",
            "CREATE TABLE Groups (GroupID INTEGER PRIMARY KEY, GroupName TEXT)",
            "CREATE TABLE UserRoles (UserID INTEGER, RoleID INTEGER, PRIMARY KEY (UserID, RoleID))",
            "CREATE TABLE Roles (RoleID INTEGER PRIMARY KEY, RoleName TEXT)",
            "CREATE TABLE UserApplications (UserID INTEGER, ApplicationID INTEGER, PRIMARY KEY (UserID, ApplicationID))",
            "CREATE TABLE Applications (ApplicationID INTEGER PRIMARY KEY, ApplicationName TEXT)"
        ]
        
        self.mock_db.get_usable_table_names.return_value = [
            "Users", "UserGroups", "Groups", "UserRoles", "Roles", "UserApplications", "Applications"
        ]
        
        # Set up query writer with the mock db
        self.query_writer = QueryWriter(self.mock_db)
        
        # Mock the LLM responses
        self.mock_llm_patcher = patch('src.query_writer.ChatOllama')
        self.mock_llm = self.mock_llm_patcher.start()
        self.query_writer.llm = self.mock_llm.return_value

    def tearDown(self):
        self.mock_llm_patcher.stop()

    def test_basic_no_mfa_query(self):
        """Test a simple query for users with no MFA."""
        # Set up test data
        query = "Find all users without MFA"
        expected_sql = "SELECT UserID, Name, Email, Department FROM Users WHERE risk_topic = 'NO_MFA_USERS'"
        
        # Configure mock responses
        self.mock_llm.return_value.invoke.side_effect = [
            # Initial SQL generation
            AIMessage(content=expected_sql),
            # Verification step
            AIMessage(content="VALID: The query is correct.")
        ]
        
        # Execute test
        response = self.query_writer.process_query(query)
        
        # Verify the result
        self.assertEqual(response.content, expected_sql)
        self.assertEqual(len(self.query_writer.conversation_history), 1)
        self.assertEqual(self.query_writer.conversation_history[0]["query"], query)
        self.assertEqual(self.query_writer.conversation_history[0]["sql"], expected_sql)

    def test_complex_query_with_join(self):
        """Test a complex query requiring joins across tables."""
        # Set up test data
        query = "Which service accounts have admin roles?"
        initial_sql = "SELECT u.UserID, u.Name, u.Email FROM Users u JOIN UserRoles ur ON u.UserID = ur.UserID JOIN Roles r ON ur.RoleID = r.RoleID WHERE u.risk_topic = 'SERVICE_ACCOUNTS' AND r.RoleName = 'Admin'"
        
        # Configure mock responses
        self.mock_llm.return_value.invoke.side_effect = [
            # Initial SQL generation
            AIMessage(content=initial_sql),
            # Verification step
            AIMessage(content="VALID: The query is correct.")
        ]
        
        # Configure the DB.run to succeed
        self.mock_db.run.return_value = [("1", "service_account1", "service1@example.com")]
        
        # Execute test
        response = self.query_writer.process_query(query)
        
        # Verify the result
        self.assertEqual(response.content, initial_sql)
        self.assertEqual(len(self.query_writer.conversation_history), 1)

    def test_query_with_verification_correction(self):
        """Test a query that needs correction during verification."""
        # Set up test data
        query = "Find all inactive users in the Engineering department"
        initial_sql = "SELECT UserID, Name, Email FROM Users WHERE Department = 'Engineering' AND inactive = 1"
        corrected_sql = "SELECT u.UserID, u.Name, u.Email, u.Department FROM Users u JOIN UserGroups ug ON u.UserID = ug.UserID JOIN Groups g ON ug.GroupID = g.GroupID WHERE u.risk_topic = 'INACTIVE_USERS' AND g.GroupName = 'Engineering'"
        
        verification_response = """
        The initial query has several issues:
        1. Missing the required risk_topic filter
        2. Using a non-existent column 'inactive'
        3. Not using the correct way to filter by department (should use join with Groups)
        
        Corrected SQL:
        ```sql
        SELECT u.UserID, u.Name, u.Email, u.Department FROM Users u JOIN UserGroups ug ON u.UserID = ug.UserID JOIN Groups g ON ug.GroupID = g.GroupID WHERE u.risk_topic = 'INACTIVE_USERS' AND g.GroupName = 'Engineering'
        ```
        """
        
        # Configure mock responses
        self.mock_llm.return_value.invoke.side_effect = [
            # Initial SQL generation
            AIMessage(content=initial_sql),
            # Verification step with correction
            AIMessage(content=verification_response)
        ]
        
        # Configure the DB.run to succeed
        self.mock_db.run.return_value = [("1", "John Doe", "john@example.com", "Engineering")]
        
        # Execute test
        response = self.query_writer.process_query(query)
        
        # Verify the result
        self.assertEqual(response.content, corrected_sql)

    def test_query_with_runtime_error(self):
        """Test a query that causes a runtime error and needs fixing."""
        # Set up test data
        query = "Count users by risk category"
        initial_sql = "SELECT risk_topic, COUNT(*) FROM Users GROUP BY risk_topic"
        fixed_sql = "SELECT risk_topic, COUNT(*) as user_count FROM Users WHERE risk_topic IS NOT NULL GROUP BY risk_topic ORDER BY user_count DESC"
        
        # Configure mock responses
        self.mock_llm.return_value.invoke.side_effect = [
            # Initial SQL generation
            AIMessage(content=initial_sql),
            # Verification step
            AIMessage(content="VALID: The query is correct."),
            # Error handling response
            AIMessage(content=fixed_sql)
        ]
        
        # Configure the DB.run to fail on first call, succeed on second
        self.mock_db.run.side_effect = [
            Exception("Syntax error: missing column alias for aggregate function"),
            [("NO_MFA_USERS", 25), ("INACTIVE_USERS", 18)]
        ]
        
        # Execute test
        response = self.query_writer.process_query(query)
        
        # Verify the result
        self.assertEqual(response.content, fixed_sql)

    def test_extract_sql_from_verification(self):
        """Test the SQL extraction function with different formats."""
        # Test with code block format
        verification_with_code_block = """
        The query has issues:
        1. Missing order by clause for the count
        2. Should have a column alias for the count
        
        ```sql
        SELECT risk_topic, COUNT(*) as user_count FROM Users GROUP BY risk_topic ORDER BY user_count DESC
        ```
        """
        expected_sql = "SELECT risk_topic, COUNT(*) as user_count FROM Users GROUP BY risk_topic ORDER BY user_count DESC"
        result = self.query_writer._extract_sql_from_verification(verification_with_code_block)
        self.assertEqual(result, expected_sql)
        
        # Test with indicator format
        verification_with_indicator = """
        The query has issues:
        1. Missing order by clause for the count
        2. Should have a column alias for the count
        
        Corrected SQL: SELECT risk_topic, COUNT(*) as user_count FROM Users GROUP BY risk_topic ORDER BY user_count DESC
        
        This will properly count users by risk category.
        """
        result = self.query_writer._extract_sql_from_verification(verification_with_indicator)
        self.assertEqual(result, expected_sql)

    def test_create_test_query(self):
        """Test the function that creates test queries with LIMIT."""
        # Normal SELECT without LIMIT
        sql = "SELECT * FROM Users WHERE risk_topic = 'NO_MFA_USERS'"
        expected = "SELECT * FROM Users WHERE risk_topic = 'NO_MFA_USERS' LIMIT 1;"
        self.assertEqual(self.query_writer._create_test_query(sql), expected)
        
        # SELECT with existing LIMIT
        sql = "SELECT * FROM Users WHERE risk_topic = 'NO_MFA_USERS' LIMIT 5"
        self.assertEqual(self.query_writer._create_test_query(sql), sql)
        
        # SELECT with semicolon
        sql = "SELECT * FROM Users WHERE risk_topic = 'NO_MFA_USERS';"
        expected = "SELECT * FROM Users WHERE risk_topic = 'NO_MFA_USERS' LIMIT 1;"
        self.assertEqual(self.query_writer._create_test_query(sql), expected)
        
        # Non-SELECT statement
        sql = "UPDATE Users SET LastLogin = NULL WHERE risk_topic = 'INACTIVE_USERS'"
        self.assertEqual(self.query_writer._create_test_query(sql), sql)


if __name__ == "__main__":
    unittest.main() 