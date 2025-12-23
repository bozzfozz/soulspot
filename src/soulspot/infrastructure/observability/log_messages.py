"""Structured log message templates for consistent, human-readable logging.

Hey future me - This module provides standardized log message templates that make logs
ACTUALLY USEFUL for debugging! Instead of cryptic messages like "Error: All connection
attempts failed", we now have:

    🔴 slskd Connection Failed
    ├─ Reason: All connection attempts failed
    ├─ Target: http://slskd:5030/api/v0/transfers/downloads
    └─ 💡 Check: Is slskd container running? Is SLSKD_URL correct in settings?

The templates follow these principles:
1. **Icon First** - Visual marker for quick scanning (🔴 = error, ⚠️ = warning, ✅ = success)
2. **Action/Entity** - What failed/succeeded (e.g., "Connection", "Download", "Sync")
3. **Context** - Relevant IDs, names, paths
4. **Hints** - Actionable troubleshooting steps

Usage:
    from soulspot.infrastructure.observability.log_messages import LogMessages

    logger.error(LogMessages.connection_failed(
        service="slskd",
        target="http://slskd:5030",
        hint="Check docker-compose.yml for service name"
    ))
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class LogTemplate:
    """A reusable log message template with placeholders.

    Hey future me - This is a structured template that can be formatted with specific
    values. The format() method replaces {placeholders} with actual values and adds
    visual formatting (icons, tree structure, hints).
    """

    icon: str
    title: str
    fields: dict[str, str]
    hint: str | None = None

    def format(self, **kwargs: Any) -> str:
        """Format the template with provided values.

        Args:
            **kwargs: Values to fill into template placeholders

        Returns:
            Formatted multi-line log message with icon, title, fields, and optional hint
        """
        # Title line with icon
        lines = [f"{self.icon} {self.title}"]

        # Field lines with tree structure
        field_items = list(self.fields.items())
        for i, (key, value_template) in enumerate(field_items):
            # Last field uses └─ instead of ├─
            prefix = "└─" if i == len(field_items) - 1 and not self.hint else "├─"

            # Format value template with kwargs
            try:
                value = value_template.format(**kwargs)
            except KeyError as e:
                value = f"<missing: {e}>"

            lines.append(f"{prefix} {key}: {value}")

        # Optional hint
        if self.hint:
            try:
                hint_text = self.hint.format(**kwargs)
            except KeyError as e:
                hint_text = f"<missing: {e}>"
            lines.append(f"└─ 💡 {hint_text}")

        return "\n".join(lines)


class LogMessages:
    """Collection of standardized log message templates.

    Hey future me - This is THE place for all log messages! Instead of scattered
    f-strings throughout the codebase, we centralize message formatting here. Benefits:
    - Consistent formatting across the app
    - Easy to update messages without touching business logic
    - Better i18n support in the future
    - Enforces including helpful context/hints

    Template categories:
    - Connection errors (network, HTTP, database)
    - Worker lifecycle (start/stop/error)
    - Data sync (Spotify, Deezer, slskd)
    - File operations (import, move, delete)
    - Authentication (OAuth, tokens)
    """

    # === Connection Errors ===

    @staticmethod
    def connection_failed(
        service: str,
        target: str,
        error: str | None = None,
        hint: str | None = None
    ) -> str:
        """Format a connection failure message.

        Args:
            service: Service name (e.g., "slskd", "Spotify", "MusicBrainz")
            target: Connection target (URL, host:port)
            error: Error message from exception
            hint: Custom troubleshooting hint

        Returns:
            Formatted log message

        Example:
            logger.error(LogMessages.connection_failed(
                service="slskd",
                target="http://slskd:5030",
                error="Connection timeout",
                hint="Check if slskd container is running: docker ps | grep slskd"
            ))
        """
        fields = {"Service": service, "Target": target}
        if error:
            fields["Reason"] = error

        default_hint = f"Check if {service} is running and accessible"

        template = LogTemplate(
            icon="🔴",
            title=f"{service} Connection Failed",
            fields=fields,
            hint=hint or default_hint
        )
        return template.format()

    @staticmethod
    def connection_timeout(
        service: str,
        timeout: float,
        hint: str | None = None
    ) -> str:
        """Format a connection timeout message.

        Args:
            service: Service name
            timeout: Timeout duration in seconds
            hint: Custom troubleshooting hint
        """
        default_hint = f"Increase timeout or check {service} performance"

        template = LogTemplate(
            icon="⏱️",
            title=f"{service} Connection Timeout",
            fields={"Timeout": f"{timeout}s"},
            hint=hint or default_hint
        )
        return template.format()

    # === Worker Lifecycle ===

    @staticmethod
    def worker_started(
        worker: str,
        interval: int | None = None,
        config: dict[str, Any] | None = None
    ) -> str:
        """Format a worker start message.

        Args:
            worker: Worker name
            interval: Check interval in seconds (if applicable)
            config: Additional config to display
        """
        fields: dict[str, str] = {}
        if interval:
            fields["Interval"] = f"{interval}s"
        if config:
            for key, value in config.items():
                fields[key] = str(value)

        template = LogTemplate(
            icon="✅",
            title=f"{worker} Started",
            fields=fields
        )
        return template.format()

    @staticmethod
    def worker_failed(
        worker: str,
        error: str,
        will_retry: bool = True,
        hint: str | None = None
    ) -> str:
        """Format a worker failure message.

        Args:
            worker: Worker name
            error: Error description
            will_retry: Whether worker will retry
            hint: Custom troubleshooting hint
        """
        status = "Will retry" if will_retry else "Stopped"

        template = LogTemplate(
            icon="❌",
            title=f"{worker} Failed",
            fields={"Reason": error, "Status": status},
            hint=hint
        )
        return template.format()

    # === Data Sync ===

    @staticmethod
    def sync_started(
        entity: str,
        source: str,
        count: int | None = None
    ) -> str:
        """Format a sync start message.

        Args:
            entity: What is being synced (e.g., "Followed Artists", "Playlists")
            source: Source service (e.g., "Spotify", "Deezer")
            count: Number of items (if known)
        """
        fields = {"Source": source}
        if count is not None:
            fields["Items"] = str(count)

        template = LogTemplate(
            icon="🔄",
            title=f"Syncing {entity}",
            fields=fields
        )
        return template.format()

    @staticmethod
    def sync_completed(
        entity: str,
        added: int = 0,
        updated: int = 0,
        removed: int = 0,
        errors: int = 0
    ) -> str:
        """Format a sync completion message.

        Args:
            entity: What was synced
            added: Number of items added
            updated: Number of items updated
            removed: Number of items removed
            errors: Number of errors
        """
        icon = "✅" if errors == 0 else "⚠️"
        fields = {
            "Added": str(added),
            "Updated": str(updated),
            "Removed": str(removed)
        }
        if errors > 0:
            fields["Errors"] = str(errors)

        template = LogTemplate(
            icon=icon,
            title=f"{entity} Sync Complete",
            fields=fields
        )
        return template.format()

    @staticmethod
    def sync_failed(
        entity: str,
        source: str,
        error: str,
        hint: str | None = None
    ) -> str:
        """Format a sync failure message.

        Args:
            entity: What failed to sync
            source: Source service
            error: Error description
            hint: Custom troubleshooting hint
        """
        default_hint = f"Check {source} authentication and API status"

        template = LogTemplate(
            icon="❌",
            title=f"{entity} Sync Failed",
            fields={"Source": source, "Reason": error},
            hint=hint or default_hint
        )
        return template.format()

    # === File Operations ===

    @staticmethod
    def file_imported(
        filename: str,
        source: str,
        destination: str
    ) -> str:
        """Format a file import success message.

        Args:
            filename: File being imported
            source: Source path
            destination: Destination path
        """
        template = LogTemplate(
            icon="📥",
            title="File Imported",
            fields={
                "File": filename,
                "From": source,
                "To": destination
            }
        )
        return template.format()

    @staticmethod
    def file_skipped(
        filename: str,
        reason: str,
        hint: str | None = None
    ) -> str:
        """Format a file skip message.

        Args:
            filename: File being skipped
            reason: Why it was skipped
            hint: What to do about it (if anything)
        """
        template = LogTemplate(
            icon="⏭️",
            title="File Skipped",
            fields={"File": filename, "Reason": reason},
            hint=hint
        )
        return template.format()

    @staticmethod
    def file_operation_failed(
        operation: str,
        filename: str,
        error: str,
        hint: str | None = None
    ) -> str:
        """Format a file operation failure message.

        Args:
            operation: Operation that failed (e.g., "Move", "Delete", "Rename")
            filename: File involved
            error: Error description
            hint: Troubleshooting hint
        """
        template = LogTemplate(
            icon="🔴",
            title=f"File {operation} Failed",
            fields={"File": filename, "Reason": error},
            hint=hint
        )
        return template.format()

    # === Authentication ===

    @staticmethod
    def auth_required(
        service: str,
        feature: str,
        hint: str | None = None
    ) -> str:
        """Format an authentication required message.

        Args:
            service: Service requiring auth
            feature: Feature that needs auth
            hint: How to authenticate
        """
        default_hint = f"Configure {service} authentication in Settings → Providers"

        template = LogTemplate(
            icon="🔑",
            title=f"{service} Authentication Required",
            fields={"Feature": feature},
            hint=hint or default_hint
        )
        return template.format()

    @staticmethod
    def token_expired(
        service: str,
        expires_at: str | None = None,
        hint: str | None = None
    ) -> str:
        """Format a token expiration message.

        Args:
            service: Service with expired token
            expires_at: When it expired
            hint: What to do
        """
        fields = {}
        if expires_at:
            fields["Expired"] = expires_at

        default_hint = f"Re-authenticate with {service} to refresh token"

        template = LogTemplate(
            icon="⏰",
            title=f"{service} Token Expired",
            fields=fields,
            hint=hint or default_hint
        )
        return template.format()

    # === Download Operations ===

    @staticmethod
    def download_started(
        track: str,
        artist: str,
        quality: str | None = None
    ) -> str:
        """Format a download start message.

        Args:
            track: Track title
            artist: Artist name
            quality: Quality preference
        """
        fields = {"Track": track, "Artist": artist}
        if quality:
            fields["Quality"] = quality

        template = LogTemplate(
            icon="⬇️",
            title="Download Started",
            fields=fields
        )
        return template.format()

    @staticmethod
    def download_completed(
        track: str,
        artist: str,
        file_path: str,
        duration: float | None = None
    ) -> str:
        """Format a download completion message.

        Args:
            track: Track title
            artist: Artist name
            file_path: Downloaded file path
            duration: Download duration in seconds
        """
        fields = {"Track": track, "Artist": artist, "Path": file_path}
        if duration:
            fields["Duration"] = f"{duration:.1f}s"

        template = LogTemplate(
            icon="✅",
            title="Download Complete",
            fields=fields
        )
        return template.format()

    @staticmethod
    def download_failed(
        track: str,
        artist: str,
        error: str,
        hint: str | None = None
    ) -> str:
        """Format a download failure message.

        Args:
            track: Track title
            artist: Artist name
            error: Error description
            hint: Troubleshooting hint
        """
        default_hint = "Check slskd connection and search results"

        template = LogTemplate(
            icon="❌",
            title="Download Failed",
            fields={"Track": track, "Artist": artist, "Reason": error},
            hint=hint or default_hint
        )
        return template.format()

    @staticmethod
    def download_retry_scheduled(
        track: str,
        artist: str,
        retry_count: int,
        next_retry_at: str,
        error_code: str | None = None
    ) -> str:
        """Format a download retry scheduled message.

        Hey future me - log when a failed download is scheduled for retry!

        Args:
            track: Track title
            artist: Artist name
            retry_count: Current retry attempt number
            next_retry_at: When the retry will happen
            error_code: Error code that triggered retry
        """
        fields = {
            "Track": track,
            "Artist": artist,
            "Retry": f"#{retry_count}",
            "Scheduled": next_retry_at,
        }
        if error_code:
            fields["Error Code"] = error_code

        template = LogTemplate(
            icon="🔄",
            title="Download Retry Scheduled",
            fields=fields,
            hint="Download will be retried automatically"
        )
        return template.format()

    @staticmethod
    def download_retry_exhausted(
        track: str,
        artist: str,
        total_retries: int,
        error_code: str | None = None
    ) -> str:
        """Format a download retries exhausted message.

        Hey future me - log when all retries have been used up!

        Args:
            track: Track title
            artist: Artist name
            total_retries: Total number of retries attempted
            error_code: Final error code
        """
        fields = {
            "Track": track,
            "Artist": artist,
            "Total Retries": str(total_retries),
        }
        if error_code:
            fields["Final Error"] = error_code

        template = LogTemplate(
            icon="⛔",
            title="Download Retries Exhausted",
            fields=fields,
            hint="Manual intervention required - try different source"
        )
        return template.format()

    @staticmethod
    def source_blocked(
        username: str,
        reason: str,
        scope: str = "USERNAME",
        expires_at: str | None = None
    ) -> str:
        """Format a source blocked message.

        Hey future me - log when a source gets blocked!

        Args:
            username: Blocked username
            reason: Why blocked
            scope: Blocklist scope (USERNAME, FILEPATH, SPECIFIC)
            expires_at: When block expires (or None for permanent)
        """
        fields = {
            "Username": username,
            "Reason": reason,
            "Scope": scope,
        }
        if expires_at:
            fields["Expires"] = expires_at

        template = LogTemplate(
            icon="🚫",
            title="Source Blocked",
            fields=fields,
            hint="Source will be skipped in future searches"
        )
        return template.format()

    # === Configuration ===

    @staticmethod
    def config_invalid(
        setting: str,
        value: Any,
        expected: str,
        hint: str | None = None
    ) -> str:
        """Format an invalid configuration message.

        Args:
            setting: Setting name
            value: Invalid value
            expected: Expected format/type
            hint: How to fix
        """
        template = LogTemplate(
            icon="⚙️",
            title="Invalid Configuration",
            fields={
                "Setting": setting,
                "Value": str(value),
                "Expected": expected
            },
            hint=hint or "Update setting in Settings UI"
        )
        return template.format()
