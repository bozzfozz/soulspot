"""
Example: Circuit Breaker Usage

This example demonstrates how the Circuit Breaker pattern protects external
service calls in SoulSpot.
"""

# mypy: ignore-errors

import asyncio
import logging

from soulspot.config.settings import Settings, SpotifySettings
from soulspot.infrastructure.integrations.circuit_breaker_wrapper import (
    CircuitBreakerSpotifyClient,
)
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient
from soulspot.infrastructure.observability.circuit_breaker import CircuitBreakerError

# Configure logging to see circuit breaker events
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def main() -> None:
    """Demonstrate circuit breaker behavior."""
    # Initialize settings
    settings = Settings(
        spotify=SpotifySettings(
            client_id="example-client-id",
            client_secret="example-secret",
            redirect_uri="http://localhost:8000/callback",
        )
    )

    # Create Spotify client wrapped with circuit breaker
    base_client = SpotifyClient(settings.spotify)
    protected_client = CircuitBreakerSpotifyClient(base_client, settings)

    print("\n=== Circuit Breaker Demo ===\n")
    print("This example simulates API failures to demonstrate circuit breaker behavior:")
    print("1. First 5 calls will 'fail' (simulated)")
    print("2. Circuit opens after 5 failures")
    print("3. Subsequent calls are immediately blocked")
    print("4. After timeout, circuit moves to HALF_OPEN")
    print("5. Successful calls close the circuit\n")

    # Simulate 5 failed API calls
    print("--- Phase 1: Triggering failures (5 calls) ---")
    for i in range(5):
        try:
            # This will fail because we don't have valid credentials
            await protected_client.get_track("invalid-track-id", "invalid-token")
        except Exception as e:
            print(f"Call {i+1}: Failed with {type(e).__name__}")

    # Circuit should now be OPEN
    print("\n--- Phase 2: Circuit is OPEN - calls blocked ---")
    try:
        await protected_client.get_track("any-track-id", "any-token")
    except CircuitBreakerError as e:
        print("✋ Circuit breaker blocked the call!")
        print(f"   Service: {e.service_name}")
        print(f"   Retry after: {e.retry_after:.1f} seconds")

    # Check circuit breaker statistics
    print("\n--- Circuit Breaker Statistics ---")
    # Note: In real usage, you'd access the internal circuit breaker
    # For this demo, we're showing what statistics are available
    print("State: OPEN")
    print("Total requests: 6")
    print("Total failures: 5")
    print("Total successes: 0")
    print("Current failure count: 5")

    print("\n--- Demo Complete ---")
    print(
        "In production, the circuit breaker would automatically transition to HALF_OPEN"
    )
    print("after the timeout period (default: 60 seconds) and test if the service")
    print("has recovered.")

    # Clean up
    await protected_client.close()


if __name__ == "__main__":
    asyncio.run(main())
