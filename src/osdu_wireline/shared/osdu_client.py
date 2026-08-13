"""HTTP client for OSDU API interactions.

This module implements an async HTTP client with connection pooling
and retry logic as defined in ADR-005.
"""

import asyncio
from types import TracebackType
from typing import Any, Self
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientSession, ClientTimeout

from .app_context import get_app_context
from .auth_handler import AuthHandler
from .config_manager import ConfigManager
from .exceptions import OSMCPAPIError, OSMCPConnectionError


class OsduClient:
    """Async HTTP client for OSDU APIs with connection pooling and retries.

    Use as an async context manager so the HTTP session is closed
    automatically:

        async with OsduClient() as client:
            data = await client.get("/api/path")
    """

    def __init__(
        self,
        config: ConfigManager | None = None,
        auth_handler: AuthHandler | None = None,
    ):
        """Initialize OSDU client.

        Args:
            config: Configuration manager instance, defaults to the shared one
            auth_handler: Authentication handler, defaults to the shared one
        """
        if config is None or auth_handler is None:
            context = get_app_context()
            config = config if config is not None else context.config
            auth_handler = auth_handler if auth_handler is not None else context.auth

        self.config = config
        self.auth_handler = auth_handler
        self._session: ClientSession | None = None
        self._base_url: str = config.get_required("server", "url")
        self._data_partition: str = config.get_required("server", "data_partition")
        self._timeout = config.get("server", "timeout", 30)

    @property
    def data_partition(self) -> str:
        """Data partition this client targets."""
        return self._data_partition

    @property
    def server_url(self) -> str:
        """Base OSDU server URL."""
        return self._base_url

    async def __aenter__(self) -> Self:
        """Open the HTTP session.

        Returns:
            This client instance
        """
        await self._ensure_session()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the HTTP session."""
        await self.close()

    async def _ensure_session(self) -> ClientSession:
        """Ensure HTTP session is created.

        Returns:
            Active aiohttp session
        """
        if self._session is None or self._session.closed:
            timeout = ClientTimeout(total=self._timeout)
            self._session = ClientSession(timeout=timeout)
        return self._session

    async def _make_request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary

        Raises:
            OSMCPAPIError: For API errors
            OSMCPConnectionError: For connection errors
        """
        url = urljoin(self._base_url, path)
        session = await self._ensure_session()

        # Set up headers
        headers = kwargs.get("headers", {})
        headers["Authorization"] = (
            f"Bearer {await self.auth_handler.get_access_token()}"
        )
        headers["data-partition-id"] = self._data_partition
        headers["Content-Type"] = "application/json"
        kwargs["headers"] = headers

        # Retry logic with exponential backoff
        max_retries = 3
        base_delay = 1  # seconds

        for attempt in range(max_retries):
            try:
                async with session.request(method, url, **kwargs) as response:
                    if response.status >= 400:
                        error_text = await response.text()
                        raise OSMCPAPIError(
                            f"Request failed: {error_text}", response.status
                        )

                    # Return JSON response
                    try:
                        return await response.json()
                    except Exception:
                        # Handle non-JSON responses (e.g., plain text)
                        text = await response.text()
                        return {"response": text}

            except aiohttp.ClientError as e:
                if attempt == max_retries - 1:
                    raise OSMCPConnectionError(f"Connection error: {e}")

                # Exponential backoff
                delay = base_delay * (2**attempt)
                await asyncio.sleep(delay)

            except Exception as e:
                if "OSMCPAPIError" in str(type(e)):
                    raise
                raise OSMCPAPIError(f"Unexpected error: {e}")
        # If all retries failed but we didn't explicitly raise an exception
        raise OSMCPConnectionError("Maximum retry attempts reached without success")

    async def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """GET request with retry logic.

        Args:
            path: API path
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary
        """
        return await self._make_request("GET", path, **kwargs)

    async def post(self, path: str, data: Any, **kwargs: Any) -> dict[str, Any]:
        """POST request with retry logic.

        Args:
            path: API path
            data: Request body data
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary
        """
        kwargs["json"] = data
        return await self._make_request("POST", path, **kwargs)

    async def put(self, path: str, data: Any, **kwargs: Any) -> dict[str, Any]:
        """PUT request with retry logic.

        Args:
            path: API path
            data: Request body data
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary
        """
        kwargs["json"] = data
        return await self._make_request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> dict[str, Any]:
        """DELETE request with retry logic.

        Args:
            path: API path
            **kwargs: Additional request parameters

        Returns:
            Response data as dictionary
        """
        return await self._make_request("DELETE", path, **kwargs)

    async def close(self) -> None:
        """Clean up HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
