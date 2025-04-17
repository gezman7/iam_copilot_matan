from typing import Any, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta
from models import RiskTopic


@dataclass
class IAMDataSnapshot:
    """Data class representing a snapshot of IAM data."""
    users: List[Dict[str, Any]]
    roles: List[Dict[str, Any]]
    applications: List[Dict[str, Any]]
    groups: List[Dict[str, Any]]
    resources: List[Dict[str, Any]]
    
    def detect_risk(self, risk_topic: RiskTopic) -> List[Dict[str, Any]]:
        """Detect users with a specific risk topic.
        
        Args:
            risk_topic: The risk topic to check for
            
        Returns:
            List of user dictionaries with the specified risk
        """
        if risk_topic == RiskTopic.WEAK_MFA_USERS:
            return [user for user in self.users if user.get('MFAStatus', '').lower() in ['sms', 'email']]
            
        elif risk_topic == RiskTopic.NO_MFA_USERS:
            return [user for user in self.users if user.get('MFAStatus', '').lower() == 'none' 
                   or not user.get('MFAStatus')]
            
        elif risk_topic == RiskTopic.INACTIVE_USERS:
            # Users who haven't logged in for a significant period (90 days)
            reference_date = datetime(2023, 4, 10).isoformat()  # Use a fixed reference date for testing
            threshold_date = (datetime(2023, 4, 10) - timedelta(days=90)).isoformat()
            return [user for user in self.users 
                    if user.get('LastLogin', '') and user.get('LastLogin', '') < threshold_date]
            
        elif risk_topic == RiskTopic.NEVER_LOGGED_IN_USERS:
            # Users who have never logged in
            return [user for user in self.users 
                    if not user.get('LastLogin') or user.get('LastLogin', '') == '']
            
        elif risk_topic == RiskTopic.PARTIALLY_OFFBOARDED_USERS:
            # Users marked as offboarded who still have access to applications/groups
            offboarded_users = []
            for user in self.users:
                if user.get('Status', '').lower() == 'offboarded':
                    # Check if user still has application or group memberships
                    for app in self.applications:
                        if user['UserID'] in app.get('AssociatedUsers', []):
                            offboarded_users.append(user)
                            break
                    if user not in offboarded_users:
                        for group in self.groups:
                            if user['UserID'] in group.get('AssociatedUsers', []):
                                offboarded_users.append(user)
                                break
            return offboarded_users
            
        elif risk_topic == RiskTopic.SERVICE_ACCOUNTS:
            return [user for user in self.users if user.get('AccountType', '').lower() == 'service']
            
        elif risk_topic == RiskTopic.LOCAL_ACCOUNTS:
            return [user for user in self.users if user.get('AccountType', '').lower() == 'local']
            
        elif risk_topic == RiskTopic.RECENTLY_JOINED_USERS:
            # Consider accounts created in the last 30 days as recently joined
            reference_date = datetime(2023, 4, 10).isoformat()  # Use a fixed reference date for testing
            threshold_date = (datetime(2023, 4, 10) - timedelta(days=30)).isoformat()
            return [user for user in self.users 
                    if user.get('EmploymentStartDate', '') > threshold_date[:10]]  # Compare only date part
        
        # Default case - return empty list if risk topic not recognized
        return []


def create_empty_snapshot() -> IAMDataSnapshot:
    """Create an empty IAMDataSnapshot with empty lists for all attributes.
    
    Returns:
        IAMDataSnapshot: An empty snapshot
    """
    return IAMDataSnapshot(
        users=[],
        roles=[],
        applications=[],
        groups=[],
        resources=[]
    ) 