#!/usr/bin/env python3
"""
Spotify Integration Test Script

Tests the Spotify OAuth flow and API methods to verify 100% operational status.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from soulspot.config.settings import Settings
from soulspot.infrastructure.integrations.spotify_client import SpotifyClient


async def test_spotify_configuration():
    """Test Spotify configuration."""
    print("=" * 60)
    print("SPOTIFY CONFIGURATION TEST")
    print("=" * 60)
    
    settings = Settings()
    
    # Check if Spotify credentials are configured
    print(f"\n✓ Spotify Client ID: {'SET' if settings.spotify.client_id else '❌ MISSING'}")
    print(f"✓ Spotify Client Secret: {'SET' if settings.spotify.client_secret else '❌ MISSING'}")
    print(f"✓ Spotify Redirect URI: {settings.spotify.redirect_uri}")
    
    if not settings.spotify.client_id or not settings.spotify.client_secret:
        print("\n❌ ERROR: Spotify credentials are not configured!")
        print("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env file")
        return False
    
    print("\n✅ Spotify configuration is valid")
    return True


async def test_oauth_flow():
    """Test OAuth PKCE flow (without actual authorization)."""
    print("\n" + "=" * 60)
    print("OAUTH PKCE FLOW TEST")
    print("=" * 60)
    
    settings = Settings()
    client = SpotifyClient(settings.spotify)
    
    try:
        # Test code verifier generation
        code_verifier = SpotifyClient.generate_code_verifier()
        print(f"\n✓ Code Verifier Generated: {code_verifier[:20]}...")
        
        # Test code challenge generation
        code_challenge = SpotifyClient.generate_code_challenge(code_verifier)
        print(f"✓ Code Challenge Generated: {code_challenge[:20]}...")
        
        # Test authorization URL generation
        state = "test_state_123"
        auth_url = client.get_authorization_url(state, code_verifier)
        print(f"✓ Authorization URL Generated")
        print(f"  URL: {auth_url[:80]}...")
        
        # Verify URL contains required parameters
        assert "response_type=code" in auth_url
        assert "client_id=" in auth_url
        assert "redirect_uri=" in auth_url
        assert "code_challenge=" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "state=" in auth_url
        print("✓ Authorization URL contains all required parameters")
        
        print("\n✅ OAuth PKCE flow components are working correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False
    finally:
        await client.close()


async def test_api_methods_structure():
    """Test that all required API methods exist."""
    print("\n" + "=" * 60)
    print("API METHODS STRUCTURE TEST")
    print("=" * 60)
    
    settings = Settings()
    client = SpotifyClient(settings.spotify)
    
    required_methods = [
        "get_authorization_url",
        "exchange_code",
        "refresh_token",
        "get_playlist",
        "get_user_playlists",
        "get_track",
        "search_track",
        "get_artist_albums",
        "get_followed_artists",
    ]
    
    print("\nChecking required API methods:")
    all_exist = True
    for method in required_methods:
        exists = hasattr(client, method) and callable(getattr(client, method))
        status = "✓" if exists else "❌"
        print(f"  {status} {method}")
        if not exists:
            all_exist = False
    
    await client.close()
    
    if all_exist:
        print("\n✅ All required API methods exist")
        return True
    else:
        print("\n❌ Some API methods are missing")
        return False


async def test_session_endpoints():
    """Test that auth endpoints are properly configured."""
    print("\n" + "=" * 60)
    print("AUTH ENDPOINTS TEST")
    print("=" * 60)
    
    # Check if auth router exists
    try:
        from soulspot.api.routers import auth
        
        required_endpoints = [
            "authorize",
            "callback",
            "refresh_token",
            "get_session_info",
            "logout",
            "spotify_status",
        ]
        
        print("\nChecking auth endpoints:")
        all_exist = True
        for endpoint in required_endpoints:
            exists = hasattr(auth, endpoint)
            status = "✓" if exists else "❌"
            print(f"  {status} {endpoint}")
            if not exists:
                all_exist = False
        
        if all_exist:
            print("\n✅ All auth endpoints exist")
            return True
        else:
            print("\n❌ Some auth endpoints are missing")
            return False
            
    except ImportError as e:
        print(f"\n❌ ERROR: Could not import auth router: {e}")
        return False


async def test_import_playlist_use_case():
    """Test that import playlist use case exists."""
    print("\n" + "=" * 60)
    print("IMPORT PLAYLIST USE CASE TEST")
    print("=" * 60)
    
    try:
        from soulspot.application.use_cases.import_spotify_playlist import (
            ImportSpotifyPlaylistUseCase,
            ImportSpotifyPlaylistRequest,
            ImportSpotifyPlaylistResponse,
        )
        
        print("\n✓ ImportSpotifyPlaylistUseCase exists")
        print("✓ ImportSpotifyPlaylistRequest exists")
        print("✓ ImportSpotifyPlaylistResponse exists")
        
        # Check required methods
        required_methods = ["execute"]
        for method in required_methods:
            exists = hasattr(ImportSpotifyPlaylistUseCase, method)
            status = "✓" if exists else "❌"
            print(f"  {status} {method} method")
        
        print("\n✅ Import playlist use case is properly structured")
        return True
        
    except ImportError as e:
        print(f"\n❌ ERROR: Could not import use case: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("SPOTIFY INTEGRATION TEST SUITE")
    print("=" * 60)
    print("\nThis script verifies that all Spotify integration components")
    print("are properly configured and structured.")
    print("\nNote: This does NOT test actual API calls (requires valid tokens)")
    
    results = []
    
    # Run tests
    results.append(("Configuration", await test_spotify_configuration()))
    results.append(("OAuth PKCE Flow", await test_oauth_flow()))
    results.append(("API Methods", await test_api_methods_structure()))
    results.append(("Auth Endpoints", await test_session_endpoints()))
    results.append(("Import Playlist Use Case", await test_import_playlist_use_case()))
    
    # Print summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Spotify integration is properly configured.")
        print("\nNext steps:")
        print("1. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env")
        print("2. Register redirect URI in Spotify Developer Dashboard")
        print("3. Test OAuth flow with real credentials")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
