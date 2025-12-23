"""slskd HTTP client implementation for Soulseek downloads."""

from typing import Any

import httpx

from soulspot.config.settings import SlskdSettings
from soulspot.domain.exceptions import ConfigurationError, ValidationError
from soulspot.domain.ports import ISlskdClient


class SlskdClient(ISlskdClient):
    """HTTP client for slskd API operations."""

    # Hey future me, slskd is the Soulseek daemon that does actual P2P downloading. This init
    # is important: we strip the trailing slash from base_url because httpx gets confused
    # when you have double slashes in URLs. Learned that the hard way with 404 errors!
    # Client creation is lazy (in _get_client) to avoid asyncio headaches.
    # UPDATE: Now validates URL has http:// or https:// protocol to prevent cryptic httpx errors!
    def __init__(self, settings: SlskdSettings) -> None:
        """
        Initialize slskd client.

        Args:
            settings: slskd configuration settings

        Raises:
            ConfigurationError: If URL is missing or doesn't have http:// or https:// protocol
        """
        self.settings = settings

        # Validate URL has protocol before httpx tries to use it
        url = settings.url.strip()
        if not url:
            raise ConfigurationError(
                "slskd URL is empty. Please configure slskd.url in Settings or "
                "set SLSKD_URL environment variable."
            )
        if not url.startswith(("http://", "https://")):
            raise ConfigurationError(
                f"slskd URL '{url}' is missing http:// or https:// protocol. "
                "Please use a valid URL like 'http://localhost:5030'"
            )

        self.base_url = url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    # Listen up, slskd supports TWO auth methods: API key (preferred) OR basic auth.
    # API key goes in X-API-Key header. If no API key, fall back to username/password.
    # NEVER send both - pick one! Timeout is 30s because Soulseek searches can be SLOW
    # when the network is busy. Don't reduce this or you'll get timeouts during peak hours.
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

    # Hey, cleanup is critical! If you don't close this, you'll leak file descriptors and
    # eventually hit system limits. Always use this as async context manager or call close()!
    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # Yo future me, Soulseek search is a TWO-STEP process: 1) POST to start search, get ID
    # 2) GET results by ID. The search happens async on the P2P network, so results trickle in.
    # 30s timeout is barely enough - if network is slow, you might get ZERO results even though
    # files exist! Consider increasing timeout for rare/obscure tracks. Also, search quality
    # varies WILDLY - generic terms return tons of crap, specific terms might find nothing.
    # Pro tip: Include artist name + track name for best results. The slskd API uses camelCase
    # (searchText, bitRate) not snake_case - watch out when parsing responses!
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

    # Hey future me, this STARTS a download but doesn't wait for it to finish! It's async.
    # The download happens in the background via P2P. slskd doesn't give us a clean download_id
    # so we construct one ourselves: "username/filename". This is a bit hacky but it works.
    # GOTCHA: If the user is offline or has you blocked, this will succeed here but fail later
    # during actual transfer. Always check download status afterwards! Also, "files" is an ARRAY
    # because slskd supports batch downloads, but we only send one file at a time for simplicity.
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

    # Listen future me, slskd has NO "get download by ID" endpoint! We have to fetch ALL
    # downloads and filter ourselves. This is INEFFICIENT but unavoidable. If you have 100+
    # active downloads, this gets slow. The download_id format "username/filename" is our
    # own invention (see download() method). We use split("/", 1) not just split("/") because
    # filenames can contain slashes! If a download completes or fails, it might disappear from
    # the list - that's why we return "not_found" state instead of throwing an error.
    async def get_download_status(self, download_id: str) -> dict[str, Any]:
        """
        Get the status of a download.

        Args:
            download_id: Download ID (format: username/filename)

        Returns:
            Download status information

        Raises:
            httpx.HTTPError: If the request fails
            ValidationError: If download_id format is invalid
        """
        if "/" not in download_id:
            raise ValidationError(
                "Invalid download_id format. Expected: username/filename"
            )

        username, filename = download_id.split("/", 1)
        client = await self._get_client()

        # Get all downloads and filter
        response = await client.get("/api/v0/transfers/downloads")
        response.raise_for_status()
        downloads = response.json()

        for download in downloads:
            if (
                download.get("username") == username
                and download.get("filename") == filename
            ):
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

    # Yo, this gets ALL downloads - active, queued, completed, failed, everything. In a busy
    # system this can be a BIG list. Consider pagination if you're dealing with hundreds of
    # downloads. The response format matches what we normalize in get_download_status() so at
    # least that's consistent. Use this sparingly - it's not cheap!
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

    # Hey future me, canceling is done via DELETE but the API is weird: username goes in the
    # path, filename goes as a query param. Why? No idea. Just roll with it. If the download
    # is already complete or doesn't exist, slskd will 404. Don't let that crash your app -
    # handle it gracefully. Also, canceling doesn't delete the partial file from disk! You
    # need to clean that up manually if you care about disk space.
    async def cancel_download(self, download_id: str) -> None:
        """
        Cancel a download.

        Args:
            download_id: Download ID (format: username/filename)

        Raises:
            httpx.HTTPError: If the request fails
            ValidationError: If download_id format is invalid
        """
        if "/" not in download_id:
            raise ValidationError(
                "Invalid download_id format. Expected: username/filename"
            )

        username, filename = download_id.split("/", 1)
        client = await self._get_client()

        # slskd doesn't have a direct cancel endpoint, we use DELETE
        response = await client.delete(
            f"/api/v0/transfers/downloads/{username}",
            params={"filename": filename},
        )
        response.raise_for_status()

    # Hey, always use this client with "async with SlskdClient(...) as client:" to ensure
    # proper cleanup. Your future self will thank you when you don't have connection leaks!
    async def __aenter__(self) -> "SlskdClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    # Hey future me - dieser Test-Endpoint prüft ob slskd erreichbar und authentifiziert ist!
    # Wird vom Onboarding genutzt um Credentials VOR dem Speichern zu validieren.
    # Returned version string bei Erfolg, None bei Fehler.
    async def test_connection(self) -> dict[str, Any]:
        """Test connection to slskd API.

        Attempts to connect and authenticate with slskd.
        Used by onboarding to validate credentials before saving.

        Returns:
            Dict with success status, optional version, and error message

        Example:
            {"success": True, "version": "0.21.0"}
            {"success": False, "error": "Authentication failed"}
        """
        try:
            client = await self._get_client()

            # Try to hit the application endpoint
            response = await client.get("/api/v0/application", timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "version": data.get("version", "unknown"),
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "error": "Authentication failed - invalid API key or credentials",
                }
            elif response.status_code == 403:
                return {
                    "success": False,
                    "error": "Access denied - insufficient permissions",
                }
            else:
                return {
                    "success": False,
                    "error": f"Unexpected status code: {response.status_code}",
                }

        except httpx.ConnectError:
            return {
                "success": False,
                "error": f"Cannot connect to {self.base_url} - is slskd running?",
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Connection timeout - server not responding",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
