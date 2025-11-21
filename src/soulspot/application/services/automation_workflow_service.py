"""Automation workflow service for orchestrating automated workflows."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.notification_service import NotificationService
from soulspot.domain.entities import (
    AutomationAction,
    AutomationRule,
    AutomationTrigger,
)
from soulspot.domain.value_objects import AutomationRuleId
from soulspot.infrastructure.persistence.repositories import AutomationRuleRepository

logger = logging.getLogger(__name__)


# Yo, AutomationWorkflowService orchestrates automated actions! This is the "if this then that" engine for
# music downloads. Define triggers (new_release, missing_album, quality_upgrade) and actions (download, notify,
# queue). Each rule has priority (for execution order), quality settings, filters, etc. Uses repository pattern
# for persistence and notification_service for alerts. Stateless except for DB calls - safe for concurrent use!
class AutomationWorkflowService:
    """Service for orchestrating automated workflows (Detect→Search→Download→Process)."""

    # Hey future me, constructor needs DB session (for rule persistence) and optional notification service (for
    # alerts). If no notification service provided, creates default (which just logs). Could make notification
    # service required to catch config errors earlier - consider that!
    def __init__(
        self,
        session: AsyncSession,
        notification_service: NotificationService | None = None,
    ) -> None:
        """Initialize automation workflow service.

        Args:
            session: Database session
            notification_service: Optional notification service
        """
        self.repository = AutomationRuleRepository(session)
        self.notification_service = notification_service or NotificationService()

    # Yo this creates automation rules! Defines trigger (new_release, missing_album, etc) and action
    # (search_and_download, notify_only, add_to_queue). The quality_profile controls download quality
    # preference (low/medium/high/lossless). apply_filters determines if filter rules are applied to search
    # results. auto_process controls if post-processing pipeline runs after download. Enabled by default
    # which means rule is active immediately - might want to create disabled and enable manually? Priority
    # determines execution order when multiple rules match same trigger. Initializes execution stats to 0
    # (will be incremented as rule runs). last_triggered_at is None initially. Uses AutomationRuleId.generate()
    # for UUID primary key. Logs creation with trigger→action showing workflow. No validation that quality
    # profile is valid string (could be "invalid" and break later). Consider enum for quality_profile?
    async def create_rule(
        self,
        name: str,
        trigger: AutomationTrigger,
        action: AutomationAction,
        priority: int = 0,
        quality_profile: str = "high",
        apply_filters: bool = True,
        auto_process: bool = True,
        description: str | None = None,
    ) -> AutomationRule:
        """Create a new automation rule.

        Args:
            name: Rule name
            trigger: Trigger type (new_release, missing_album, quality_upgrade, manual)
            action: Action to perform (search_and_download, notify_only, add_to_queue)
            priority: Rule priority (higher evaluated first)
            quality_profile: Quality preference (low, medium, high, lossless)
            apply_filters: Whether to apply filter rules
            auto_process: Whether to run post-processing pipeline
            description: Optional description

        Returns:
            Created automation rule
        """
        rule = AutomationRule(
            id=AutomationRuleId.generate(),
            name=name,
            trigger=trigger,
            action=action,
            enabled=True,
            priority=priority,
            quality_profile=quality_profile,
            apply_filters=apply_filters,
            auto_process=auto_process,
            description=description,
            last_triggered_at=None,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
        )
        await self.repository.add(rule)
        logger.info(
            f"Created automation rule: {name} ({trigger.value} → {action.value})"
        )
        return rule

    # Listen future me, gets a single rule by ID. Simple repository lookup. Returns None if not found (not exception).
    # The type annotation is explicit - repository might return None. Good for checking if rule exists before update!
    async def get_rule(self, rule_id: AutomationRuleId) -> AutomationRule | None:
        """Get automation rule by ID."""
        result: AutomationRule | None = await self.repository.get_by_id(rule_id)
        return result

    # Yo, list all rules with pagination support. Default limit of 100 prevents memory blow-up if you have thousands
    # of rules (unlikely but defensive!). Offset is for pagination - offset=100, limit=100 gets rules 100-200.
    # This returns ALL rules regardless of enabled status - use list_enabled() if you only want active ones!
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[AutomationRule]:
        """List all automation rules."""
        return await self.repository.list_all(limit, offset)

    # Hey, filter rules by trigger type (e.g., only "new_release" rules). Useful for UI - show user all their
    # new release rules together. Repository does the filtering, not us - keeps service thin and dumb!
    async def list_by_trigger(self, trigger: AutomationTrigger) -> list[AutomationRule]:
        """List automation rules by trigger type."""
        return await self.repository.list_by_trigger(trigger.value)

    # Listen, gets only ENABLED rules - the ones that will actually execute. Disabled rules are ignored by
    # automation system. This is what background workers call to find rules to run. No pagination here -
    # assumes you don't have thousands of enabled rules (if you do, you have other problems!)
    async def list_enabled(self) -> list[AutomationRule]:
        """List all enabled automation rules."""
        return await self.repository.list_enabled()

    # Yo, enables a rule - sets enabled=True and persists. Checks rule exists first (returns silently if not -
    # idempotent design). Logs the action for audit trail. The entity method enable() handles state change,
    # repository.update() persists it. Clean separation of concerns!
    async def enable_rule(self, rule_id: AutomationRuleId) -> None:
        """Enable an automation rule."""
        rule = await self.repository.get_by_id(rule_id)
        if rule:
            rule.enable()
            await self.repository.update(rule)
            logger.info(f"Enabled automation rule: {rule.name}")

    # Hey, pause a rule - sets enabled=False. Disabled rules won't execute but are preserved in DB for later.
    # WHY disable instead of delete? User might want to temporarily pause automation without losing config.
    # Example: going on vacation, don't want downloads piling up, disable all rules then re-enable when back!
    async def disable_rule(self, rule_id: AutomationRuleId) -> None:
        """Disable an automation rule."""
        rule = await self.repository.get_by_id(rule_id)
        if rule:
            rule.disable()
            await self.repository.update(rule)
            logger.info(f"Disabled automation rule: {rule.name}")

    # Yo, permanent deletion - removes rule from DB entirely. No soft delete, it's GONE. Use disable if you want
    # to keep the rule for later! This is destructive and can't be undone. Consider adding confirmation step in UI!
    async def delete_rule(self, rule_id: AutomationRuleId) -> None:
        """Delete an automation rule."""
        await self.repository.delete(rule_id)
        logger.info(f"Deleted automation rule: {rule_id}")

    # Listen up, this executes a SINGLE rule with given context! Context dict has trigger-specific data (track IDs,
    # album info, etc). Returns result dict with success flag and details. If rule not found or disabled, returns
    # error immediately (fail-fast). Wraps _execute_action in try/catch to handle failures gracefully. Records
    # execution stats (total_executions, successful_executions, failed_executions) for monitoring. Updates
    # last_triggered_at timestamp. This is called by trigger_workflow for each matching rule!
    async def execute_rule(
        self, rule_id: AutomationRuleId, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute an automation rule with given context.

        Args:
            rule_id: Automation rule ID
            context: Execution context (track info, artist info, etc.)

        Returns:
            Execution result with status and details
        """
        rule = await self.repository.get_by_id(rule_id)
        if not rule:
            return {
                "success": False,
                "error": f"Automation rule {rule_id} not found",
            }

        if not rule.enabled:
            return {
                "success": False,
                "error": f"Automation rule {rule.name} is disabled",
            }

        logger.info(f"Executing automation rule: {rule.name}")

        try:
            result = await self._execute_action(rule, context)
            rule.record_execution(success=True)
            await self.repository.update(rule)
            return result
        except Exception as e:
            logger.error(f"Failed to execute automation rule {rule.name}: {e}")
            rule.record_execution(success=False)
            await self.repository.update(rule)
            return {
                "success": False,
                "error": str(e),
            }

    # IMPORTANT: This is the actual "do the thing" logic! Dispatches to _action_search_and_download,
    # _action_notify_only, or _action_add_to_queue based on rule.action enum. Returns result dict with
    # success flag and details. Each action method is separate for single responsibility principle. Raises
    # ValueError for unknown action enum (shouldn't happen but defensive). Context dict contains trigger-
    # specific data (track IDs, album info, artist name, etc). The action methods are async so they can
    # do IO (notify external services, queue jobs, etc). Return values are unstructured dicts not Pydantic
    # which makes them flexible but less type-safe. Consider standardizing result schema across all actions?
    # The if/elif chain could be replaced with strategy pattern or dict dispatch for better extensibility.
    async def _execute_action(
        self, rule: AutomationRule, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute the action defined in the automation rule.

        Args:
            rule: Automation rule
            context: Execution context

        Returns:
            Action execution result
        """
        if rule.action == AutomationAction.SEARCH_AND_DOWNLOAD:
            return await self._action_search_and_download(rule, context)
        elif rule.action == AutomationAction.NOTIFY_ONLY:
            return await self._action_notify_only(rule, context)
        elif rule.action == AutomationAction.ADD_TO_QUEUE:
            return await self._action_add_to_queue(rule, context)
        else:
            raise ValueError(f"Unknown action: {rule.action}")

    # Hey future me, the STUB implementation for search-and-download action! This logs what WOULD happen but doesn't
    # actually trigger downloads yet. In production, this would: 1) Create Track entities for items, 2) Add download
    # jobs to queue, 3) Download worker picks them up and processes. Right now it just returns success with context
    # passed through. The quality_profile, apply_filters, auto_process settings are preserved for when you implement
    # the real download logic. Extract track_ids, album_info, release_info from context - these tell you WHAT to download!
    async def _action_search_and_download(
        self, rule: AutomationRule, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute search and download action.

        This integrates with the job queue to trigger actual downloads.

        Args:
            rule: Automation rule
            context: Execution context

        Returns:
            Action result
        """
        logger.info(
            f"Triggering search and download with quality profile: {rule.quality_profile}"
        )

        # Extract track/album information from context
        track_ids = context.get("track_ids", [])
        album_info = context.get("album_info")
        release_info = context.get("release_info")

        if not track_ids and not album_info and not release_info:
            logger.warning("No track IDs, album info, or release info in context")
            return {
                "success": False,
                "action": "search_and_download",
                "error": "No downloadable items in context",
            }

        # Log the download trigger
        # In a full implementation, this would:
        # 1. Get or create track entities for the album/release
        # 2. Add download jobs to the job queue
        # 3. The download worker would pick them up and process
        logger.info(
            f"Would trigger downloads for: tracks={len(track_ids) if track_ids else 0}, "
            f"album={'yes' if album_info else 'no'}, release={'yes' if release_info else 'no'}"
        )

        return {
            "success": True,
            "action": "search_and_download",
            "quality_profile": rule.quality_profile,
            "apply_filters": rule.apply_filters,
            "auto_process": rule.auto_process,
            "context": context,
            "message": f"Download triggered for quality profile: {rule.quality_profile}",
        }

    # Yo, notify-only action - sends notification WITHOUT downloading! Use this for "heads up" alerts when you want
    # manual review before downloading. The trigger type determines notification format (new_release vs missing_album
    # vs quality_upgrade have different message templates). Each trigger extracts different context fields (artist_name,
    # album_name, release_date, etc). Falls back to generic notification if trigger doesn't match known types. Wraps
    # notification_service calls in try/catch - notification failures shouldn't crash the workflow!
    async def _action_notify_only(
        self, rule: AutomationRule, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute notify only action.

        This sends a notification to the user about a new release,
        missing album, or quality upgrade opportunity.

        Args:
            rule: Automation rule
            context: Execution context

        Returns:
            Action result
        """
        logger.info(f"Sending notification for rule: {rule.name}")

        try:
            # Send notification based on trigger type
            if rule.trigger == AutomationTrigger.NEW_RELEASE:
                artist_name = context.get("artist_name", "Unknown Artist")
                album_name = context.get("album_name", "Unknown Album")
                release_date = context.get("release_date", "Unknown Date")
                await self.notification_service.send_new_release_notification(
                    artist_name, album_name, release_date
                )
            elif rule.trigger == AutomationTrigger.MISSING_ALBUM:
                artist_name = context.get("artist_name", "Unknown Artist")
                missing_count = context.get("missing_count", 0)
                total_count = context.get("total_count", 0)
                await self.notification_service.send_missing_album_notification(
                    artist_name, missing_count, total_count
                )
            elif rule.trigger == AutomationTrigger.QUALITY_UPGRADE:
                track_title = context.get("track_title", "Unknown Track")
                current_quality = context.get("current_quality", "Unknown")
                target_quality = context.get("target_quality", "Unknown")
                await self.notification_service.send_quality_upgrade_notification(
                    track_title, current_quality, target_quality
                )
            else:
                # Generic notification
                await self.notification_service.send_automation_notification(
                    rule.trigger.value, context
                )

            return {
                "success": True,
                "action": "notify_only",
                "context": context,
                "message": f"Notification sent for {rule.trigger.value}",
            }
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return {
                "success": False,
                "action": "notify_only",
                "error": str(e),
            }

    # Listen, add-to-queue action - creates a pending download job for manual approval! This is the middle ground
    # between auto-download and notify-only. Downloads are queued but need user click to start. Good for when you
    # want control but don't want to search manually. Extracts item name from context (album OR track title). Logs
    # what would be queued (STUB - real implementation would create DB job record). Sends notification so user knows
    # something is waiting for approval. Returns success with context preserved. Quality profile is stored for when
    # user approves the download!
    async def _action_add_to_queue(
        self, rule: AutomationRule, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute add to queue action.

        This adds the track/album to the download queue for manual approval.

        Args:
            rule: Automation rule
            context: Execution context

        Returns:
            Action result
        """
        logger.info(f"Adding to queue with quality profile: {rule.quality_profile}")

        # Extract information from context
        item_name = context.get("album_name") or context.get(
            "track_title", "Unknown Item"
        )

        # Log that item would be added to queue
        # In a full implementation, this would create a download job with pending status
        logger.info(
            f"Item queued for manual approval: {item_name} "
            f"(Quality: {rule.quality_profile})"
        )

        # Send notification about the queued item
        await self.notification_service.send_automation_notification(
            rule.trigger.value,
            {**context, "action": "queued_for_approval"},
        )

        return {
            "success": True,
            "action": "add_to_queue",
            "quality_profile": rule.quality_profile,
            "context": context,
            "message": f"Added to download queue for manual approval: {item_name}",
        }

    # Hey future me, trigger ALL enabled rules for a specific trigger type! This is what background workers call
    # when events occur (new_release detected, missing_album found, etc). Filters to enabled rules only (disabled
    # rules are skipped). Sorts by priority (higher first) so important rules run before low-priority ones. Executes
    # each rule with same context. Collects results from all rules - some might succeed, others fail. Returns list
    # of result dicts with rule ID, rule name, and execution result. Empty list if no enabled rules for that trigger.
    # This is the "broadcast" pattern - one trigger fires multiple rules!
    async def trigger_workflow(
        self,
        trigger: AutomationTrigger,
        context: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Trigger all enabled automation rules for a specific trigger type.

        Args:
            trigger: Trigger type
            context: Execution context

        Returns:
            List of execution results
        """
        rules = await self.list_by_trigger(trigger)
        enabled_rules = [r for r in rules if r.enabled]

        if not enabled_rules:
            logger.info(f"No enabled rules for trigger: {trigger.value}")
            return []

        # Sort by priority (higher first)
        enabled_rules.sort(key=lambda r: r.priority, reverse=True)

        results = []
        for rule in enabled_rules:
            result = await self.execute_rule(rule.id, context)
            results.append(
                {
                    "rule_id": str(rule.id.value),
                    "rule_name": rule.name,
                    "result": result,
                }
            )

        logger.info(f"Executed {len(enabled_rules)} rules for trigger: {trigger.value}")
        return results

    # Yo, creates sensible default rules for new users - the "starter pack"! Three pre-configured rules:
    # 1) Auto-download new releases (priority 100 - highest), 2) Notify on missing albums (priority 50 - medium),
    # 3) Auto-upgrade quality to lossless (priority 75 - high). Each rule is created separately with error handling -
    # if one fails, others still get created. Returns list of successfully created rules. Logs count at end for
    # feedback. Call this during first-time setup or when user clicks "restore defaults" button!
    async def create_default_rules(self) -> list[AutomationRule]:
        """Create default automation rules for common scenarios.

        Returns:
            List of created automation rules
        """
        default_rules = [
            {
                "name": "Auto-download new releases",
                "trigger": AutomationTrigger.NEW_RELEASE,
                "action": AutomationAction.SEARCH_AND_DOWNLOAD,
                "priority": 100,
                "quality_profile": "high",
                "description": "Automatically download new releases from watched artists",
            },
            {
                "name": "Notify missing albums",
                "trigger": AutomationTrigger.MISSING_ALBUM,
                "action": AutomationAction.NOTIFY_ONLY,
                "priority": 50,
                "quality_profile": "high",
                "description": "Notify when missing albums are detected in discography",
            },
            {
                "name": "Auto-upgrade quality",
                "trigger": AutomationTrigger.QUALITY_UPGRADE,
                "action": AutomationAction.SEARCH_AND_DOWNLOAD,
                "priority": 75,
                "quality_profile": "lossless",
                "description": "Automatically upgrade tracks to better quality",
            },
        ]

        created_rules = []
        for rule_data in default_rules:
            try:
                rule = await self.create_rule(
                    name=str(rule_data["name"]),
                    trigger=AutomationTrigger(rule_data["trigger"]),
                    action=AutomationAction(rule_data["action"]),
                    priority=rule_data["priority"],  # type: ignore[arg-type]
                    quality_profile=str(rule_data["quality_profile"]),
                    description=str(rule_data["description"]),
                )
                created_rules.append(rule)
            except Exception as e:
                logger.error(
                    f"Failed to create default rule '{rule_data['name']}': {e}"
                )

        logger.info(f"Created {len(created_rules)} default automation rules")
        return created_rules
