"""Artwork serving endpoint for local library images.

Hey future me - this serves locally stored album/artist artwork!

The image_path stored in the database is relative to IMAGE_PATH setting.
This endpoint resolves the full path and serves the file securely.

Security: Uses Path.resolve() + is_relative_to() to prevent path traversal attacks.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from soulspot.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/artwork", tags=["artwork"])


# Hey future me - this serves local artwork files from the IMAGE_PATH directory!
# Security is critical here: we MUST prevent path traversal attacks (../../etc/passwd).
# The resolve() + is_relative_to() pattern ensures the file is actually inside image_path.
@router.get("/{file_path:path}")
async def serve_artwork(
    file_path: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """Serve artwork file from local storage.

    Args:
        file_path: Relative path to artwork file (from image_path setting)

    Returns:
        FileResponse with the image file

    Raises:
        404 if file not found
        403 if path traversal attempted
    """
    # Get image base path from settings
    image_base = settings.storage.image_path

    # Resolve the full path and check it's within image_base (security!)
    try:
        full_path = (image_base / file_path).resolve()

        # Security check: ensure resolved path is still inside image_base
        if not full_path.is_relative_to(image_base.resolve()):
            logger.warning(f"Path traversal attempt blocked: {file_path}")
            raise HTTPException(status_code=403, detail="Access denied")

    except Exception as e:
        logger.error(f"Error resolving artwork path: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid path") from e

    # Check file exists
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Artwork not found")

    # Determine media type from extension
    suffix = full_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        path=full_path,
        media_type=media_type,
        filename=full_path.name,
    )
