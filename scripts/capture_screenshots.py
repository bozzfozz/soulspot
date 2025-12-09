#!/usr/bin/env python3
"""Script to capture UI screenshots for documentation.

⚠️ DEPRECATED - ONE-TIME TASK: This script was used to capture initial UI screenshots for
documentation (stored in docs/ui-screenshots/). Screenshots already captured.

Historical screenshot capture script. For new screenshots, update manually or adapt this script.
"""

import asyncio
import time
from pathlib import Path

from playwright.async_api import async_playwright


async def capture_screenshots():
    """Capture screenshots of all main UI views."""

    # Configuration
    base_url = "http://localhost:8000"
    output_dir = Path("docs/ui-screenshots")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Views to capture
    views = [
        {
            "name": "auth",
            "url": f"{base_url}/ui/auth",
            "description": "Authentication/OAuth page",
        },
        {
            "name": "dashboard",
            "url": f"{base_url}/ui",
            "description": "Main dashboard with statistics",
        },
        {
            "name": "playlists",
            "url": f"{base_url}/ui/playlists",
            "description": "Playlists listing page",
        },
        {
            "name": "import_playlist",
            "url": f"{base_url}/ui/playlists/import",
            "description": "Import playlist page",
        },
        {
            "name": "downloads",
            "url": f"{base_url}/ui/downloads",
            "description": "Downloads page",
        },
    ]

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
        )
        page = await context.new_page()

        print(f"Starting screenshot capture from {base_url}")
        print(f"Output directory: {output_dir.absolute()}")
        print("-" * 60)

        for view in views:
            try:
                print(f"Capturing: {view['name']} - {view['description']}")

                # Navigate to the page
                await page.goto(view["url"], wait_until="networkidle", timeout=30000)

                # Wait a bit for any dynamic content
                await page.wait_for_timeout(1000)

                # Take screenshot
                screenshot_path = output_dir / f"{view['name']}.png"
                await page.screenshot(path=str(screenshot_path), full_page=True)

                print(f"  ✓ Saved to: {screenshot_path.name}")

            except Exception as e:
                print(f"  ✗ Error capturing {view['name']}: {e}")

        await browser.close()
        print("-" * 60)
        print("Screenshot capture complete!")


def wait_for_server(base_url: str = "http://localhost:8000", timeout: int = 30):
    """Wait for the server to be ready."""
    import requests

    print(f"Waiting for server at {base_url}...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{base_url}/health", timeout=2)
            if response.status_code == 200:
                print("Server is ready!")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)

    print(f"Server not ready after {timeout} seconds")
    return False


if __name__ == "__main__":
    # Wait for server to be ready
    if not wait_for_server():
        print("Error: Server not ready. Please start the server first.")
        exit(1)

    # Capture screenshots
    asyncio.run(capture_screenshots())
