from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from models import RiskTopic
SHORT_PROMPT = """
SYSTEM
You are an AI that translates natural language queries into SQL for an Identity Management Risk database.
Always include a risk_topic filter (WHERE risk_topic = …) using one or more of:

Copy
Edit
WEAK_MFA_USERS, NO_MFA_USERS, INACTIVE_USERS,
NEVER_LOGGED_IN_USERS, PARTIALLY_OFFBOARDED_USERS,
SERVICE_ACCOUNTS, LOCAL_ACCOUNTS, RECENTLY_JOINED_USERS
Do not join to infer risk—its already tagged.

Tables & Key Columns
Users (UserID, Name, Email, Department, Position, EmploymentStartDate, LastLogin, MFAStatus, AccountType, Status, risk_topic)

UserGroups (UserID, GroupID)

Groups (GroupID, GroupName, Description)

UserApplications (UserID, ApplicationID)

Applications (ApplicationID, ApplicationName, Description)

UserRoles (UserID, RoleID)

Roles (RoleID, RoleName, Description, Permissions)

Resources (ResourceID, ResourceName, Description, AccessPolicies)

ResourceRoles (ResourceID, RoleID)

(Each table has its primary key and relevant foreign keys.)

Enumerated Filters
Status: active, inactive, offboarded

MFAStatus: none, sms, authenticator_app, hardware_security_key, biometric, push_notification, email

AccountType: regular, service, local

Department: Engineering, IT, Finance, Marketing, Sales, HR

Position: (e.g.) Software Engineer, IT Manager, Accountant, DevOps Engineer, etc.

Examples
No MFA users


SELECT UserID, Name, Email
FROM Users
WHERE risk_topic = 'NO_MFA_USERS';
MFA status of a specific user


SELECT MFAStatus
FROM Users
WHERE Name = 'Mark Levy';
No‑MFA users in Engineering


SELECT u.UserID, u.Name, u.Email
FROM Users u
JOIN UserGroups ug ON u.UserID = ug.UserID
JOIN Groups g     ON ug.GroupID = g.GroupID
WHERE u.risk_topic = 'NO_MFA_USERS'
  AND g.Department = 'Engineering';

  """
NEW_SPEECH_TO_QUERY_TEMPLATE = """
SYSTEM: You are an AI assistant that translates natural language queries into SQL for an Identity Management Risk database.
When to filter using risk_topic use **only** WHERE risk_topic = <risk_topic> and dont try to join to get the risk. its already tagged.
Requirements:

All SQL must include a risk_topic filter using one or more values from: {topics}.

Database Tables: {schema_info}

Schema Information:
{tables_info}

When querying for enum values, use ONLY the following values:
Status: ["active", "inactive", "offboarded"]
MFAStatus: ["none", "sms", "authenticator_app", "hardware_security_key", "biometric", "push_notification", "email"]
AccountType: ["regular", "service", "local"]
Department: ["Engineering", "IT", "Finance", "Marketing", "Sales", "HR"]
Position: ["Software Engineer", "IT Manager", "Accountant", "DevOps Engineer", "Marketing Director", "Financial Analyst", "Frontend Developer", "Sales Representative", "Recruitment Specialist", "Backend Developer", "Content Writer", "QA Engineer", "Sales Executive", "Training Coordinator", "System Architect", "Social Media Manager", "Financial Controller", "Mobile Developer", "Sales Director", "Security Engineer", "IT Support Specialist", "Budget Analyst", "HR Manager", "Digital Marketing Specialist", "Account Executive", "Data Engineer", "Network Administrator", "Financial Planner", "Benefits Coordinator"]

EXMAPLE: 
User Query: which users have no mfa?
Generated SQL: SELECT u.UserID, u.Name, u.Email
FROM Users u
WHERE u.risk_topic = 'NO_MFA_USERS';

User Query: whats the mfa status of mark levy?
Generated SQL: SELECT u.MFAStatus
FROM Users u
WHERE u.Name = 'Mark Levy';

Example:
-- Find all NO_MFA_USERS in the Engineering Team
SELECT u.UserID, u.Name, u.Email
FROM Users u
JOIN UserGroups ug ON u.UserID = ug.UserID
JOIN Groups g ON ug.GroupID = g.GroupID
WHERE u.risk_topic = 'NO_MFA_USERS'
AND g.Department = 'Engineering';

Previous Conversation History:
{conversation_history}

User Query: {query}
Return only the executable SQL statement, without commentary.
"""


QUERY_VERIFICATION_TEMPLATE = """
You are a SQL query validator specialized in Identity Management databases. You need to review the following SQL query to ensure it's correct, optimized, and addresses the user's original intent.

User Query: {query}
Generated SQL: {generated_sql}

Database Tables: {schema_info}

Schema Information:
{tables_info}

Risk Topics (one of these MUST be referenced): {topics}

Check for the following errors:
1. Syntax errors
2. Missing risk_topic filter (REQUIRED)
3. Incorrect table or column names
4. Inappropriate joins
5. Missing GROUP BY clauses where aggregate functions are used
6. Inefficient query structure

If there are errors, explain them briefly and provide a corrected SQL query.
If there are no errors, reply with: "VALID: The query is correct."
"""

ERROR_HANDLING_TEMPLATE = """
An error occurred while executing the SQL query:

User Query: {query}
Generated SQL: {sql}
Error Message: {error}

Database Tables: {schema_info}

Schema Information:
{tables_info}

Please fix the SQL query to correctly address the user's request while resolving the error. NEVER change the user query.
Return only the corrected SQL query without any explanation. without starting with any prefix.
When to filter using risk_topic use only WHERE risk_topic = <risk_topic> and dont try to join to get the risk. its already tagged.
"""


class QueryWriter():
    def __init__(self, db):
        self.llm = ChatOllama(model="mistral")
        self.db = db
        self.conversation_history = []
        
        # Create prompt templates
        self.prompt_template = PromptTemplate(
            template=NEW_SPEECH_TO_QUERY_TEMPLATE,
            input_variables=["conversation_history", "schema_info", "tables_info", "query", "topics"]
        )
        
        self.verification_template = PromptTemplate(
            template=QUERY_VERIFICATION_TEMPLATE,
            input_variables=["query", "generated_sql", "schema_info", "tables_info", "topics"]
        )
        
        self.error_handling_template = PromptTemplate(
            template=ERROR_HANDLING_TEMPLATE,
            input_variables=["query", "sql", "error", "schema_info", "tables_info"]
        )
        
    def process_query(self, query):
    
        
        # Get risk topics
        risk_topics = [topic.value for topic in RiskTopic]
        topics_str = ", ".join(risk_topics)
        
        # Format conversation history
        history_text = ""
        for exchange in self.conversation_history:
            history_text += f"User: {exchange['query']}\nSQL: {exchange['sql']}\n\n"
        
        # Get database schema and table info
        schema_info = self.db.get_usable_table_names()
        tables_info = self.db.get_table_info()
        
        # Create the prompt with the template
        prompt = self.prompt_template.format(
            conversation_history=history_text,
            query=query,
            topics=topics_str,
            schema_info=schema_info,
            tables_info=tables_info
        )
        
        # Invoke the language model for initial SQL generation
        response = self.llm.invoke(SHORT_PROMPT)
        generated_sql = response.content.strip()
        
        # # Verify the generated SQL
        # verification_prompt = self.verification_template.format(
        #     query=query,
        #     generated_sql=generated_sql,
        #     topics=topics_str,
        #     schema_info=schema_info,
        #     tables_info=tables_info
        # )
        
        # verification_result = self.llm.invoke(verification_prompt)
        
        # # If verification found issues, extract the corrected SQL
        # if not verification_result.content.startswith("VALID:"):
        #     # Extract corrected SQL from verification result
        #     corrected_sql = self._extract_sql_from_verification(verification_result.content)
        #     if corrected_sql:
        #         generated_sql = corrected_sql
        
        return AIMessage(content=generated_sql)
    
    def _extract_sql_from_verification(self, verification_text):
        """Extract corrected SQL from verification response."""
        # Look for SQL code blocks
        lines = verification_text.split('\n')
        sql_lines = []
        in_sql_block = False
        
        for line in lines:
            if line.strip().startswith('```sql'):
                in_sql_block = True
                continue
            elif line.strip() == '```' and in_sql_block:
                in_sql_block = False
                continue
            elif in_sql_block:
                sql_lines.append(line)
        
        if sql_lines:
            return '\n'.join(sql_lines)
        
        # If no code block found, look for SQL after common indicators
        indicators = ["Corrected SQL:", "Fixed SQL:", "Corrected query:"]
        for indicator in indicators:
            if indicator in verification_text:
                parts = verification_text.split(indicator, 1)
                if len(parts) > 1:
                    # Extract everything after the indicator until the next double newline or end
                    sql_part = parts[1].strip()
                    if "\n\n" in sql_part:
                        return sql_part.split("\n\n")[0].strip()
                    return sql_part
        
        return None

