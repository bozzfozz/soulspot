"""Add library naming settings to app_settings.

Revision ID: ll25008oop56
Revises: kk24007nno55
Create Date: 2025-11-28 14:00:00.000000

Hey future me - this migration adds LIBRARY NAMING SETTINGS for Lidarr-kompatible
file/folder structure!

Problem: SoulSpot needs to organize files in a specific folder structure that matches
Lidarr so both tools can coexist on the same music library. The naming pattern should
be configurable so users can match their Lidarr settings exactly.

Solution: Add naming.* settings to app_settings table. These are RUNTIME settings that
can be changed via the UI without restart. The defaults match Lidarr's recommended format:
- Artist folder: {Artist Name}
- Album folder: {Album Title} ({Release Year})
- Track file: {Track Number:00} - {Track Title}

Available template variables (Lidarr-compatible tokens):
- {Artist Name}, {Artist CleanName} - Artist name (clean = sanitized)
- {Album Title}, {Album CleanTitle} - Album title
- {Album Type} - album/single/ep/compilation
- {Release Year} - Year of release
- {Track Title}, {Track CleanTitle} - Track title
- {Track Number}, {Track Number:00} - Track number (with padding)
- {Medium}, {Medium:00} - Disc number for multi-disc albums

IMPORTANT: Only NEW downloads use these settings automatically. Existing files
can be renamed manually via batch-rename feature (optional).

Settings are stored as key-value pairs in app_settings with category='naming'.
"""

from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = "ll25008oop56"
down_revision = "kk24007nno55"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Insert library naming settings into app_settings table."""
    
    # Hey future me - we're using op.execute with raw SQL because we're inserting
    # data, not creating schema. The app_settings table already exists from an
    # earlier migration. We check if keys exist first to make this idempotent.
    
    settings = [
        # Template settings
        (
            "naming.artist_folder_format",
            "{Artist Name}",
            "string",
            "naming",
            "Template for artist folder names. Variables: {Artist Name}, {Artist CleanName}",
        ),
        (
            "naming.album_folder_format",
            "{Album Title} ({Release Year})",
            "string",
            "naming",
            "Template for album folder names. Variables: {Album Title}, {Album CleanTitle}, {Album Type}, {Release Year}",
        ),
        (
            "naming.standard_track_format",
            "{Track Number:00} - {Track Title}",
            "string",
            "naming",
            "Template for single-disc track filenames. Variables: {Track Number}, {Track Title}, etc.",
        ),
        (
            "naming.multi_disc_track_format",
            "{Medium:00}-{Track Number:00} - {Track Title}",
            "string",
            "naming",
            "Template for multi-disc track filenames. Adds disc number prefix.",
        ),
        # Boolean settings
        (
            "naming.rename_tracks",
            "true",
            "boolean",
            "naming",
            "Enable automatic file renaming on import",
        ),
        (
            "naming.replace_illegal_characters",
            "true",
            "boolean",
            "naming",
            "Replace characters not allowed in filenames (: ? * etc.)",
        ),
        (
            "naming.create_artist_folder",
            "true",
            "boolean",
            "naming",
            "Create artist folder if it doesn't exist",
        ),
        (
            "naming.create_album_folder",
            "true",
            "boolean",
            "naming",
            "Create album folder if it doesn't exist",
        ),
        # String settings for character replacement
        (
            "naming.colon_replacement",
            " -",
            "string",
            "naming",
            "Replacement for colon character in filenames",
        ),
        (
            "naming.slash_replacement",
            "-",
            "string",
            "naming",
            "Replacement for slash character in filenames",
        ),
    ]
    
    # Get reference to app_settings table
    app_settings = sa.table(
        "app_settings",
        sa.column("key", sa.String),
        sa.column("value", sa.Text),
        sa.column("value_type", sa.String),
        sa.column("category", sa.String),
        sa.column("description", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    
    now = datetime.now(timezone.utc)
    
    for key, value, value_type, category, description in settings:
        # Insert only if key doesn't exist (idempotent)
        op.execute(
            app_settings.insert()
            .prefix_with("OR IGNORE")  # SQLite syntax for INSERT OR IGNORE
            .values(
                key=key,
                value=value,
                value_type=value_type,
                category=category,
                description=description,
                created_at=now,
                updated_at=now,
            )
        )


def downgrade() -> None:
    """Remove library naming settings from app_settings table."""
    
    app_settings = sa.table(
        "app_settings",
        sa.column("key", sa.String),
        sa.column("category", sa.String),
    )
    
    # Delete all naming settings
    op.execute(
        app_settings.delete().where(app_settings.c.category == "naming")
    )
