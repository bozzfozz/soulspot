#!/usr/bin/env python3
"""Example demonstrating Phase 4 components working together.

This example shows how to use the application layer components:
- Use cases for business logic
- Token manager for OAuth
- Job queue for background processing
- Cache for API response optimization
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


async def example_cache_usage():
    """Example: Using the caching layer."""
    print("\n" + "=" * 60)
    print("Example 1: Caching Layer")
    print("=" * 60)

    from soulspot.application.cache import (
        MusicBrainzCache,
        SpotifyCache,
        TrackFileCache,
    )

    # MusicBrainz Cache
    print("\n1. MusicBrainz Cache:")
    mb_cache = MusicBrainzCache()

    # Simulate caching a recording
    recording = {"id": "recording-123", "title": "Test Song", "length": 240000}
    await mb_cache.cache_recording_by_isrc("USRC12345678", recording)
    print(f"   ✓ Cached recording: {recording['title']}")

    # Retrieve from cache
    cached = await mb_cache.get_recording_by_isrc("USRC12345678")
    print(f"   ✓ Retrieved from cache: {cached['title']}")

    # Get cache stats
    stats = mb_cache.get_stats()
    print(f"   ℹ Cache stats: {stats}")

    # Spotify Cache
    print("\n2. Spotify Cache:")
    spotify_cache = SpotifyCache()

    # Simulate caching a track
    track = {
        "id": "track-456",
        "name": "Test Track",
        "artists": [{"name": "Test Artist"}],
    }
    await spotify_cache.cache_track("track-456", track)
    print(f"   ✓ Cached track: {track['name']}")

    # Retrieve from cache
    cached_track = await spotify_cache.get_track("track-456")
    print(f"   ✓ Retrieved from cache: {cached_track['name']}")

    # Track File Cache
    print("\n3. Track File Cache:")
    file_cache = TrackFileCache()

    from soulspot.domain.value_objects import FilePath, TrackId

    track_id = TrackId.generate()
    file_path = FilePath("/tmp/test-track.mp3")

    await file_cache.cache_file_path(track_id, file_path)
    print(f"   ✓ Cached file path: {file_path}")

    # Retrieve from cache
    cached_path = await file_cache.get_file_path(track_id)
    print(f"   ✓ Retrieved from cache: {cached_path}")

    print("\n✅ Caching examples completed")


async def example_job_queue():
    """Example: Using the job queue system."""
    print("\n" + "=" * 60)
    print("Example 2: Job Queue System")
    print("=" * 60)

    from soulspot.application.workers import JobQueue, JobStatus, JobType

    # Create job queue
    job_queue = JobQueue(max_concurrent_jobs=3)
    print("\n1. Created job queue (max 3 concurrent jobs)")

    # Register a simple handler
    async def example_handler(job):
        print(f"   → Processing job {job.id[:8]}... (type: {job.job_type})")
        await asyncio.sleep(0.5)  # Simulate work
        return {"result": "success", "data": job.payload}

    job_queue.register_handler(JobType.DOWNLOAD, example_handler)
    print("2. Registered download handler")

    # Start workers
    await job_queue.start(num_workers=2)
    print("3. Started 2 workers")

    # Enqueue some jobs
    print("\n4. Enqueuing jobs:")
    job_ids = []
    for i in range(5):
        job_id = await job_queue.enqueue(
            job_type=JobType.DOWNLOAD,
            payload={"track_id": f"track-{i}", "quality": "best"},
        )
        job_ids.append(job_id)
        print(f"   ✓ Enqueued job {job_id[:8]}")

    # Wait for jobs to complete
    print("\n5. Waiting for jobs to complete...")
    await asyncio.sleep(2)

    # Check job statuses
    print("\n6. Job statuses:")
    for job_id in job_ids:
        job = await job_queue.get_job(job_id)
        status_icon = "✓" if job.status == JobStatus.COMPLETED else "⏳"
        print(f"   {status_icon} Job {job_id[:8]}: {job.status}")

    # Get queue statistics
    stats = job_queue.get_stats()
    print(f"\n7. Queue statistics: {stats}")

    # Stop workers
    await job_queue.stop()
    print("\n✅ Job queue example completed")


async def example_token_manager():
    """Example: Using the token manager."""
    print("\n" + "=" * 60)
    print("Example 3: Token Management")
    print("=" * 60)

    from soulspot.application.services import TokenManager

    # Note: This is a mock example without actual Spotify client
    class MockSpotifyClient:
        async def get_authorization_url(self, state, _code_verifier):
            return f"https://accounts.spotify.com/authorize?state={state}&code_challenge=..."

        async def exchange_code(self, _code, _code_verifier):
            return {
                "access_token": "mock_access_token",
                "refresh_token": "mock_refresh_token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "playlist-read-private",
            }

        async def refresh_token(self, _refresh_token):
            return {
                "access_token": "new_mock_access_token",
                "expires_in": 3600,
                "token_type": "Bearer",
            }

    mock_client = MockSpotifyClient()
    token_manager = TokenManager(mock_client)

    # Generate auth URL
    print("\n1. Generate authorization URL:")
    auth_url, state, code_verifier = await token_manager.get_authorization_url()
    print(f"   ✓ Auth URL: {auth_url[:60]}...")
    print(f"   ✓ State: {state[:20]}...")
    print(f"   ✓ Code verifier: {code_verifier[:20]}...")

    # Exchange code for token
    print("\n2. Exchange authorization code:")
    token_info = await token_manager.exchange_authorization_code(
        code="mock_auth_code",
        code_verifier=code_verifier,
        user_id="user123",
    )
    print(f"   ✓ Access token: {token_info.access_token}")
    print(f"   ✓ Expires at: {token_info.expires_at}")

    # Get valid token (should return existing token)
    print("\n3. Get valid token:")
    access_token = await token_manager.get_valid_token("user123")
    print(f"   ✓ Retrieved token: {access_token}")

    # Check token expiration
    print("\n4. Token expiration check:")
    is_expired = token_info.is_expired()
    expires_soon = token_info.expires_soon(threshold_seconds=3600)
    print(f"   ℹ Is expired: {is_expired}")
    print(f"   ℹ Expires soon (1h): {expires_soon}")

    # List stored tokens
    print("\n5. List stored tokens:")
    user_ids = token_manager.list_user_ids()
    print(f"   ℹ Users with tokens: {user_ids}")

    print("\n✅ Token manager example completed")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Phase 4 Component Examples")
    print("=" * 60)

    try:
        # Run examples
        await example_cache_usage()
        await example_job_queue()
        await example_token_manager()

        print("\n" + "=" * 60)
        print("✅ All examples completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
