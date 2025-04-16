from enum import Enum

class RiskTopic(Enum):
    """Enum representing different IAM risk topics for users."""
    
    WEAK_MFA_USERS = "WEAK_MFA_USERS"  # Users with MFA methods that are considered weak or less secure
    INACTIVE_USERS = "INACTIVE_USERS"  # Users who have not logged in for a significant period
    NEVER_LOGGED_IN_USERS = "NEVER_LOGGED_IN_USERS"  # Users who have never logged into the system after being provisioned
    PARTIALLY_OFFBOARDED_USERS = "PARTIALLY_OFFBOARDED_USERS"  # Users who have not been completely removed from all systems post-offboarding
    SERVICE_ACCOUNTS = "SERVICE_ACCOUNTS"  # Non-human accounts used for application or service access
    LOCAL_ACCOUNTS = "LOCAL_ACCOUNTS"  # Accounts that are local to a specific system or application, not managed centrally
    RECENTLY_JOINED_USERS = "RECENTLY_JOINED_USERS"  # Users who have recently joined and may require additional monitoring

    @staticmethod
    def get_all_risks():
        """Return a list of all risk topics."""
        return list(RiskTopic) 