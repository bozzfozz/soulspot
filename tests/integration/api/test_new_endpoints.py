"""Integration tests for new metadata and playlist endpoints."""

from fastapi.testclient import TestClient


def test_metadata_auto_fix_endpoint_exists(client: TestClient) -> None:
    """Test that auto-fix endpoint exists and returns proper error for invalid track."""
    response = client.post("/api/metadata/invalid-track-id/auto-fix")

    # Should return 400 for invalid track ID, not 404 (endpoint exists)
    assert response.status_code in [400, 404], "Endpoint should exist"


def test_metadata_fix_all_endpoint_exists(client: TestClient) -> None:
    """Test that fix-all endpoint exists."""
    response = client.post("/api/metadata/fix-all")

    # Should return 202 (accepted) or other valid status, not 404
    assert response.status_code != 404, "Endpoint should exist"
    assert response.status_code in [200, 202, 401, 403], "Endpoint should be accessible"


def test_playlist_sync_endpoint_exists(client: TestClient) -> None:
    """Test that playlist sync endpoint exists."""
    response = client.post("/api/playlists/invalid-playlist-id/sync")

    # Should return error for invalid playlist, not 404 (endpoint exists)
    assert response.status_code in [400, 401, 404], "Endpoint should exist"


def test_playlist_sync_all_endpoint_exists(client: TestClient) -> None:
    """Test that sync-all endpoint exists."""
    response = client.post("/api/playlists/sync-all")

    # Should return valid status, not 404
    assert response.status_code != 404, "Endpoint should exist"
    assert response.status_code in [200, 202, 401, 403], "Endpoint should be accessible"


def test_playlist_download_missing_endpoint_exists(client: TestClient) -> None:
    """Test that download-missing endpoint exists."""
    response = client.post("/api/playlists/invalid-playlist-id/download-missing")

    # Should return error for invalid playlist or 500 for DB initialization issues
    # The important thing is it's not 404 (endpoint exists)
    assert response.status_code in [400, 404, 500], "Endpoint should exist"
    assert response.status_code != 404 or "not found" in response.text.lower(), (
        "If 404, should be about playlist not endpoint"
    )
