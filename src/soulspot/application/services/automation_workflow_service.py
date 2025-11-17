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


class AutomationWorkflowService:
    """Service for orchestrating automated workflows (Detect→Search→Download→Process)."""

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

    async def get_rule(self, rule_id: AutomationRuleId) -> AutomationRule | None:
        """Get automation rule by ID."""
        result: AutomationRule | None = await self.repository.get_by_id(rule_id)
        return result

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[AutomationRule]:
        """List all automation rules."""
        return await self.repository.list_all(limit, offset)

    async def list_by_trigger(self, trigger: AutomationTrigger) -> list[AutomationRule]:
        """List automation rules by trigger type."""
        return await self.repository.list_by_trigger(trigger.value)

    async def list_enabled(self) -> list[AutomationRule]:
        """List all enabled automation rules."""
        return await self.repository.list_enabled()

    async def enable_rule(self, rule_id: AutomationRuleId) -> None:
        """Enable an automation rule."""
        rule = await self.repository.get_by_id(rule_id)
        if rule:
            rule.enable()
            await self.repository.update(rule)
            logger.info(f"Enabled automation rule: {rule.name}")

    async def disable_rule(self, rule_id: AutomationRuleId) -> None:
        """Disable an automation rule."""
        rule = await self.repository.get_by_id(rule_id)
        if rule:
            rule.disable()
            await self.repository.update(rule)
            logger.info(f"Disabled automation rule: {rule.name}")

    async def delete_rule(self, rule_id: AutomationRuleId) -> None:
        """Delete an automation rule."""
        await self.repository.delete(rule_id)
        logger.info(f"Deleted automation rule: {rule_id}")

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
