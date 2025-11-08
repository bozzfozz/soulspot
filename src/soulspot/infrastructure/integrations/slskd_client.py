"""slskd HTTP client implementation for Soulseek downloads."""

from typing import Any

import httpx

from soulspot.config.settings import SlskdSettings
from soulspot.domain.ports import ISlskdClient


class SlskdClient(ISlskdClient):
    """HTTP client for slskd API operations."""

    def __init__(self, settings: SlskdSettings) -> None:
        """
        Initialize slskd client.

        Args:
            settings: slskd configuration settings
        """
        self.settings = settings
        self.base_url = settings.url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            headers = {
                "Content-Type": "application/json",
            }

            # Add API key or basic auth
            if self.settings.api_key:
                headers["X-API-Key"] = self.settings.api_key

            auth = None
            if not self.settings.api_key:
                auth = httpx.BasicAuth(self.settings.username, self.settings.password)

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                auth=auth,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def search(self, query: str, timeout: int = 30) -> list[dict[str, Any]]:
        """
        Search for files on the Soulseek network.

        Args:
            query: Search query string
            timeout: Search timeout in seconds

        Returns:
            List of search results with file information

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        # Start a search
        response = await client.post(
            "/api/v0/searches",
            json={"searchText": query},
            timeout=timeout,
        )
        response.raise_for_status()
        search_data = response.json()
        search_id = search_data["id"]

        # Get search results
        response = await client.get(f"/api/v0/searches/{search_id}")
        response.raise_for_status()
        results = response.json()

        # Extract file information from results
        files = []
        if "responses" in results:
            for user_response in results["responses"]:
                username = user_response.get("username", "")
                for file in user_response.get("files", []):
                    files.append(
                        {
                            "username": username,
                            "filename": file.get("filename", ""),
                            "size": file.get("size", 0),
                            "bitrate": file.get("bitRate", 0),
                            "length": file.get("length", 0),
                            "quality": file.get("quality", 0),
                        }
                    )

        return files

    async def download(self, username: str, filename: str) -> str:
        """
        Start a download from a user.

        Args:
            username: Username of the file owner
            filename: Full path to the file to download

        Returns:
            Download ID

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.post(
            "/api/v0/transfers/downloads",
            json={
                "username": username,
                "files": [filename],
            },
        )
        response.raise_for_status()

        # slskd returns download info, use filename as ID
        return f"{username}/{filename}"

    async def get_download_status(self, download_id: str) -> dict[str, Any]:
        """
        Get the status of a download.

        Args:
            download_id: Download ID (format: username/filename)

        Returns:
            Download status information

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If download_id format is invalid
        """
        if "/" not in download_id:
            raise ValueError("Invalid download_id format. Expected: username/filename")

        username, filename = download_id.split("/", 1)
        client = await self._get_client()

        # Get all downloads and filter
        response = await client.get("/api/v0/transfers/downloads")
        response.raise_for_status()
        downloads = response.json()

        for download in downloads:
            if download.get("username") == username and download.get("filename") == filename:
                return {
                    "id": download_id,
                    "username": username,
                    "filename": filename,
                    "state": download.get("state", "unknown"),
                    "progress": download.get("percentComplete", 0),
                    "bytes_transferred": download.get("bytesTransferred", 0),
                    "size": download.get("size", 0),
                }

        # Not found
        return {
            "id": download_id,
            "username": username,
            "filename": filename,
            "state": "not_found",
            "progress": 0,
            "bytes_transferred": 0,
            "size": 0,
        }

    async def list_downloads(self) -> list[dict[str, Any]]:
        """
        List all downloads.

        Returns:
            List of downloads with status information

        Raises:
            httpx.HTTPError: If the request fails
        """
        client = await self._get_client()

        response = await client.get("/api/v0/transfers/downloads")
        response.raise_for_status()
        downloads = response.json()

        result = []
        for download in downloads:
            username = download.get("username", "")
            filename = download.get("filename", "")
            result.append(
                {
                    "id": f"{username}/{filename}",
                    "username": username,
                    "filename": filename,
                    "state": download.get("state", "unknown"),
                    "progress": download.get("percentComplete", 0),
                    "bytes_transferred": download.get("bytesTransferred", 0),
                    "size": download.get("size", 0),
                }
            )

        return result

    async def cancel_download(self, download_id: str) -> None:
        """
        Cancel a download.

        Args:
            download_id: Download ID (format: username/filename)

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If download_id format is invalid
        """
        if "/" not in download_id:
            raise ValueError("Invalid download_id format. Expected: username/filename")

        username, filename = download_id.split("/", 1)
        client = await self._get_client()

        # slskd doesn't have a direct cancel endpoint, we use DELETE
        response = await client.delete(
            f"/api/v0/transfers/downloads/{username}",
            params={"filename": filename},
        )
        response.raise_for_status()

    async def __aenter__(self) -> "SlskdClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
