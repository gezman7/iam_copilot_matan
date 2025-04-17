-- Example 1: Find all users with no MFA enabled
SELECT Users.UserID, Users.Name, Users.Email, Users.Department 
FROM Users 
WHERE risk_topic = 'NO_MFA_USERS';

-- Example 2: Find all inactive users who belong to the Engineering team
SELECT u.UserID, u.Name, u.Email, u.Department, u.LastLogin
FROM Users u
JOIN UserGroups ug ON u.UserID = ug.UserID
JOIN Groups g ON ug.GroupID = g.GroupID
WHERE u.risk_topic = 'INACTIVE_USERS'
AND g.GroupName = 'Engineering Team';

-- Example 3: Find all service accounts with admin role permissions
SELECT u.UserID, u.Name, u.Email
FROM Users u
JOIN UserRoles ur ON u.UserID = ur.UserID
JOIN Roles r ON ur.RoleID = r.RoleID
WHERE u.risk_topic = 'SERVICE_ACCOUNTS'
AND r.RoleName = 'Admin';

-- Example 4: Find users with weak MFA who have access to the Financial System
SELECT DISTINCT u.UserID, u.Name, u.Email, u.Department
FROM Users u
JOIN UserApplications ua ON u.UserID = ua.UserID
JOIN Applications a ON ua.ApplicationID = a.ApplicationID
WHERE u.risk_topic = 'WEAK_MFA_USERS'
AND a.ApplicationName = 'Financial System';

-- Example 5: Count all users by risk type, ordered by count
SELECT risk_topic, COUNT(*) as user_count
FROM Users
WHERE risk_topic IS NOT NULL
GROUP BY risk_topic
ORDER BY user_count DESC; 