from enum import Enum


class OSMCPService(Enum):
    """OSDU service identifiers, valued by their base URL path."""

    STORAGE = "/api/storage/v2"
    SEARCH = "/api/search/v2"
    LEGAL = "/api/legal/v1"  # Legal uses v1
    SCHEMA = "/api/schema-service/v1"
    FILE = "/api/file/v2"
    WORKFLOW = "/api/workflow/v1"
    ENTITLEMENTS = "/api/entitlements/v2"
    DATASET = "/api/dataset/v1"
    PARTITION = "/api/partition/v1"


def get_service_info_endpoint(service: OSMCPService) -> str:
    """Get the info/health endpoint for a given OSDU service."""
    return f"{service.value}/info"
