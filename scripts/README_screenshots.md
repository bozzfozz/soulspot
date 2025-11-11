# UI Screenshot Capture Script

Automated script to capture screenshots of all main UI views for documentation purposes.

## Prerequisites

```bash
pip install playwright requests
playwright install chromium
```

## Usage

1. Start the development server:
```bash
poetry run uvicorn soulspot.main:app --host 0.0.0.0 --port 8000
```

2. Run the screenshot script:
```bash
python3 scripts/capture_screenshots.py
```

Screenshots will be saved to `docs/ui-screenshots/`.

## Configuration

Edit the script to customize:
- `base_url`: Server URL (default: http://localhost:8000)
- `output_dir`: Screenshot directory (default: docs/ui-screenshots)
- `views`: List of views to capture

## Output

The script captures:
- `auth.png` - Authentication/OAuth page
- `dashboard.png` - Main dashboard
- `playlists.png` - Playlists listing
- `import_playlist.png` - Import playlist form
- `downloads.png` - Downloads page

All screenshots are full-page captures at 1920x1080 resolution.
