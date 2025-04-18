# sorry there was no time

RISK_VIEW_METADATA = """

TABLE NAMES:
['Applications', 'Groups', 'ResourceRoles', 'Resources', 'Roles', 'UserApplicati
ons', 'UserGroups', 'UserRol
es', 'Users']

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
)

/*
3 rows from Users table:
UserID  Name    Email   Department      Position        EmploymentStartDate     LastLogin       MFAStatus  A
ccountType      Status  risk_topic
U001    Alice Johnson   alice@example.com       Engineering     Software Engineer       2023-01-01      2023
-04-01  none    regular active  NO_MFA_USERS
U002    Bob Smith       bob@example.com IT      IT Manager      2022-01-01              sms     regular acti
ve      WEAK_MFA_USERS
U003    Charlie Davis   charlie@example.com     Finance Accountant      2021-06-15      2022-10-01      auth
enticator_app   regular active  INACTIVE_USERS
*/

"""