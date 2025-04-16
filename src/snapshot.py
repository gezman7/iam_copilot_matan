from abc import ABC, abstractmethod
from typing import Any, Dict, List
from dataclasses import dataclass


@dataclass
class IAMDataSnapshot:
    """Data class representing a snapshot of IAM data."""
    users: List[Dict[str, Any]]
    roles: List[Dict[str, Any]]
    applications: List[Dict[str, Any]]
    groups: List[Dict[str, Any]]
    resources: List[Dict[str, Any]]


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


class Loader(ABC):
    """Interface for data loaders."""
    
    @abstractmethod
    def load_data(self) -> IAMDataSnapshot:
        """Load data and return a snapshot.
        
        Returns:
            IAMDataSnapshot: A snapshot of the data loaded from the source
        """
        pass
