import json
import logging


from .loader import Loader, IAMDataSnapshot
from ..models import IAMUser

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
    