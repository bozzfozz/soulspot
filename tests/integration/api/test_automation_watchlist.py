"""Integration tests for automation watchlist endpoints."""

from fastapi.testclient import TestClient


# Hey future me - listing watchlists should always be safe on an empty DB.
def test_automation_list_watchlists_empty(client: TestClient) -> None:
    response = client.get("/api/automation/watchlist")
    assert response.status_code == 200

    payload = response.json()
    assert "watchlists" in payload
    assert "limit" in payload
    assert "offset" in payload
    assert payload["watchlists"] == []


# Hey future me - invalid UUIDs should be rejected (ArtistId parsing raises ValueError).
def test_automation_create_watchlist_rejects_invalid_artist_id(client: TestClient) -> None:
    response = client.post(
        "/api/automation/watchlist",
        json={
            "artist_id": "not-a-uuid",
            "check_frequency_hours": 24,
            "auto_download": True,
            "quality_profile": "high",
        },
    )

    assert response.status_code in {400, 422}


# Hey future me - create+list roundtrip: we don't require the artist to exist in the DB.
def test_automation_create_watchlist_then_list(client: TestClient) -> None:
    artist_id = "00000000-0000-0000-0000-000000000001"

    create = client.post(
        "/api/automation/watchlist",
        json={
            "artist_id": artist_id,
            "check_frequency_hours": 24,
            "auto_download": True,
            "quality_profile": "high",
        },
    )
    assert create.status_code == 200

    created = create.json()
    assert created["artist_id"] == artist_id
    assert "id" in created

    listed = client.get("/api/automation/watchlist")
    assert listed.status_code == 200

    payload = listed.json()
    assert any(w["artist_id"] == artist_id for w in payload["watchlists"])
