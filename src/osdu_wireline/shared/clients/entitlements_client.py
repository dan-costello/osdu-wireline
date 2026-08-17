"""Minimal OSDU Entitlements service client."""

from typing import Any

from ..service_urls import OSMCPService
from .base import OsduClient


class EntitlementsClient(OsduClient):
    """Minimal client for OSDU Entitlements service operations."""

    service = OSMCPService.ENTITLEMENTS

    async def get_my_groups(self) -> dict[str, Any]:
        """Get groups for the authenticated user."""
        return await self.get("/groups")
