"""OSDU HTTP clients: the shared base client and one subclass per service."""

from .base import OsduClient
from .entitlements_client import EntitlementsClient
from .legal_client import LegalClient
from .partition_client import PartitionClient
from .reservoir_ddms_client import ReservoirDDMSClient
from .schema_client import SchemaClient
from .search_client import BoundingBox, SearchClient
from .storage_client import StorageClient

__all__ = [
    "BoundingBox",
    "EntitlementsClient",
    "LegalClient",
    "OsduClient",
    "PartitionClient",
    "ReservoirDDMSClient",
    "SchemaClient",
    "SearchClient",
    "StorageClient",
]
