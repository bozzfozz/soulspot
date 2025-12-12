"""Integration tests for library duplicate detection endpoints."""

from fastapi.testclient import TestClient


# Hey future me - these tests purposely assert a stable, minimal JSON shape.
# The DB starts empty in integration tests, so totals should be 0 and groups empty.
def test_duplicates_artists_returns_empty_groups(client: TestClient) -> None:
    response = client.get("/api/library/duplicates/artists")
    assert response.status_code == 200

    payload = response.json()
    assert "duplicate_groups" in payload
    assert "total_groups" in payload
    assert "total_duplicates" in payload

    assert isinstance(payload["duplicate_groups"], list)
    assert payload["total_groups"] == 0
    assert payload["total_duplicates"] == 0


# Hey future me - same idea as artists: empty DB means empty groups.
def test_duplicates_albums_returns_empty_groups(client: TestClient) -> None:
    response = client.get("/api/library/duplicates/albums")
    assert response.status_code == 200

    payload = response.json()
    assert "duplicate_groups" in payload
    assert "total_groups" in payload
    assert "total_duplicates" in payload

    assert isinstance(payload["duplicate_groups"], list)
    assert payload["total_groups"] == 0
    assert payload["total_duplicates"] == 0


# Hey future me - merge endpoints should exist and validate input.
# We don't seed artists/albums here, so we only verify it rejects invalid IDs.
def test_duplicates_artists_merge_rejects_invalid_ids(client: TestClient) -> None:
    response = client.post(
        "/api/library/duplicates/artists/merge",
        json={"keep_id": "not-a-uuid", "merge_ids": ["also-not-a-uuid"]},
    )

    # Could be 400 (service validation) or 422 (schema validation)
    assert response.status_code in {400, 422}


# Hey future me - same as artists merge.
def test_duplicates_albums_merge_rejects_invalid_ids(client: TestClient) -> None:
    response = client.post(
        "/api/library/duplicates/albums/merge",
        json={"keep_id": "not-a-uuid", "merge_ids": ["also-not-a-uuid"]},
    )

    assert response.status_code in {400, 422}


# Hey future me - in tests we don't boot background workers, so the scan endpoint must
# return 503 (service unavailable) rather than crashing or returning 404.
def test_duplicates_scan_returns_503_without_worker(client: TestClient) -> None:
    response = client.post("/api/library/duplicates/scan")
    assert response.status_code == 503


# Hey future me - resolving a candidate that doesn't exist should be a clean 404.
def test_duplicates_candidate_resolve_missing_returns_404(client: TestClient) -> None:
    response = client.post(
        "/api/library/duplicates/00000000-0000-0000-0000-000000000000/resolve",
        json={"action": "dismiss"},
    )

    assert response.status_code == 404
