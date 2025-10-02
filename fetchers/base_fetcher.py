"""
Base fetcher class for Congress.gov API endpoints
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from api.client import CongressAPIClient
from config.logging_config import get_logger

logger = get_logger(__name__)


class BaseFetcher(ABC):
    """Base class for API data fetchers"""

    def __init__(self, api_client: CongressAPIClient):
        """
        Initialize fetcher

        Args:
            api_client: Congress.gov API client
        """
        self.api_client = api_client

    @abstractmethod
    def fetch_all(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Fetch all records from API endpoint

        Returns:
            List of records
        """
        pass

    def fetch_with_details(self, items: List[Dict[str, Any]], detail_method: str) -> List[Dict[str, Any]]:
        """
        Fetch detailed information for a list of items

        Args:
            items: List of basic item records
            detail_method: Method name to call for details

        Returns:
            List of detailed records
        """
        detailed_items = []

        for item in items:
            try:
                detail_method_func = getattr(self, detail_method)
                detailed_item = detail_method_func(item)
                if detailed_item:
                    detailed_items.append(detailed_item)
            except Exception as e:
                logger.error(f"Error fetching details for {item}: {e}")
                # Include basic item if details fail
                detailed_items.append(item)

        return detailed_items

    def safe_get(self, data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """
        Safely get value from nested dictionary

        Args:
            data: Dictionary to search
            key: Key to find (supports dot notation for nesting)
            default: Default value if key not found

        Returns:
            Value or default
        """
        if '.' in key:
            keys = key.split('.')
            current = data
            for k in keys:
                if isinstance(current, dict) and k in current:
                    current = current[k]
                else:
                    return default
            return current
        else:
            return data.get(key, default)