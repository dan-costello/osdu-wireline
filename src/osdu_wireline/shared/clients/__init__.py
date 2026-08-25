"""OSDU HTTP clients: the shared base client and one subclass per service."""

from .base import OsduClient
from .entitlements_client import EntitlementsClient
from .legal_client import LegalClient
from .partition_client import PartitionClient
from .schema_client import SchemaClient
from .search_client import BoundingBox, SearchClient
from .storage_client import StorageClient

__all__ = [
    "BoundingBox",
    "EntitlementsClient",
    "LegalClient",
    "OsduClient",
    "PartitionClient",
    "SchemaClient",
    "SearchClient",
    "StorageClient",
]
