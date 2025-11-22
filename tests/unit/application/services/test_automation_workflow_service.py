"""Unit tests for automation workflow service."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.application.services.automation_workflow_service import (
    AutomationWorkflowService,
)
from soulspot.domain.entities import AutomationAction, AutomationRule, AutomationTrigger
from soulspot.domain.value_objects import AutomationRuleId


class TestAutomationWorkflowService:
    """Test AutomationWorkflowService class."""

    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def mock_notification_service(self):
        """Create mock notification service."""
        mock = MagicMock()
        mock.send_automation_notification = AsyncMock()
        return mock

    @pytest.fixture
    def service(self, mock_session, mock_notification_service):
        """Create AutomationWorkflowService instance."""
        return AutomationWorkflowService(
            session=mock_session,
            notification_service=mock_notification_service,
        )

    @pytest.fixture
    def sample_rule(self):
        """Create sample automation rule."""
        return AutomationRule(
            id=AutomationRuleId.generate(),
            name="Test Rule",
            trigger=AutomationTrigger.NEW_RELEASE,
            action=AutomationAction.SEARCH_AND_DOWNLOAD,
            enabled=True,
            priority=0,
            quality_profile="high",
            apply_filters=True,
            auto_process=True,
            description="Test automation rule",
            last_triggered_at=None,
            total_executions=0,
            successful_executions=0,
            failed_executions=0,
        )

    def test_init(self, service, mock_session, mock_notification_service):
        """Test service initialization."""
        assert service.repository is not None
        assert service.notification_service == mock_notification_service

    def test_init_default_notification_service(self, mock_session):
        """Test initialization with default notification service."""
        service = AutomationWorkflowService(session=mock_session)
        assert service.notification_service is not None

    @pytest.mark.asyncio
    async def test_create_rule(self, service):
        """Test creating an automation rule."""
        service.repository.add = AsyncMock()

        rule = await service.create_rule(
            name="Test Rule",
            trigger=AutomationTrigger.NEW_RELEASE,
            action=AutomationAction.SEARCH_AND_DOWNLOAD,
            priority=1,
            quality_profile="high",
            apply_filters=True,
            auto_process=True,
            description="Test description",
        )

        assert rule.name == "Test Rule"
        assert rule.trigger == AutomationTrigger.NEW_RELEASE
        assert rule.action == AutomationAction.SEARCH_AND_DOWNLOAD
        assert rule.enabled is True
        assert rule.priority == 1
        assert rule.quality_profile == "high"
        assert rule.apply_filters is True
        assert rule.auto_process is True
        assert rule.description == "Test description"
        assert rule.total_executions == 0

        service.repository.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_rule(self, service, sample_rule):
        """Test getting a rule by ID."""
        service.repository.get_by_id = AsyncMock(return_value=sample_rule)

        result = await service.get_rule(sample_rule.id)

        assert result == sample_rule
        service.repository.get_by_id.assert_called_once_with(sample_rule.id)

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self, service):
        """Test getting a non-existent rule."""
        service.repository.get_by_id = AsyncMock(return_value=None)

        rule_id = AutomationRuleId.generate()
        result = await service.get_rule(rule_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_all(self, service, sample_rule):
        """Test listing all rules."""
        service.repository.list_all = AsyncMock(return_value=[sample_rule])

        result = await service.list_all(limit=50, offset=0)

        assert result == [sample_rule]
        service.repository.list_all.assert_called_once_with(50, 0)

    @pytest.mark.asyncio
    async def test_list_by_trigger(self, service, sample_rule):
        """Test listing rules by trigger type."""
        service.repository.list_by_trigger = AsyncMock(return_value=[sample_rule])

        result = await service.list_by_trigger(AutomationTrigger.NEW_RELEASE)

        assert result == [sample_rule]
        service.repository.list_by_trigger.assert_called_once_with("new_release")

    @pytest.mark.asyncio
    async def test_list_enabled(self, service, sample_rule):
        """Test listing enabled rules."""
        service.repository.list_enabled = AsyncMock(return_value=[sample_rule])

        result = await service.list_enabled()

        assert result == [sample_rule]
        service.repository.list_enabled.assert_called_once()

    @pytest.mark.asyncio
    async def test_enable_rule(self, service, sample_rule):
        """Test enabling a rule."""
        sample_rule.enabled = False
        service.repository.get_by_id = AsyncMock(return_value=sample_rule)
        service.repository.update = AsyncMock()

        await service.enable_rule(sample_rule.id)

        assert sample_rule.enabled is True
        service.repository.update.assert_called_once_with(sample_rule)

    @pytest.mark.asyncio
    async def test_enable_rule_not_found(self, service):
        """Test enabling a non-existent rule."""
        service.repository.get_by_id = AsyncMock(return_value=None)
        service.repository.update = AsyncMock()

        rule_id = AutomationRuleId.generate()
        await service.enable_rule(rule_id)

        # Should not call update if rule not found
        service.repository.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_disable_rule(self, service, sample_rule):
        """Test disabling a rule."""
        sample_rule.enabled = True
        service.repository.get_by_id = AsyncMock(return_value=sample_rule)
        service.repository.update = AsyncMock()

        await service.disable_rule(sample_rule.id)

        assert sample_rule.enabled is False
        service.repository.update.assert_called_once_with(sample_rule)

    @pytest.mark.asyncio
    async def test_delete_rule(self, service, sample_rule):
        """Test deleting a rule."""
        service.repository.delete = AsyncMock()

        await service.delete_rule(sample_rule.id)

        service.repository.delete.assert_called_once_with(sample_rule.id)

    @pytest.mark.asyncio
    async def test_execute_rule_success(self, service, sample_rule):
        """Test successful rule execution."""
        service.repository.get_by_id = AsyncMock(return_value=sample_rule)
        service.repository.update = AsyncMock()
        service._execute_action = AsyncMock(return_value={"success": True, "data": "test"})

        context = {"track_id": "123"}
        result = await service.execute_rule(sample_rule.id, context)

        assert result["success"] is True
        assert sample_rule.total_executions == 1
        assert sample_rule.successful_executions == 1
        assert sample_rule.failed_executions == 0
        service.repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_rule_not_found(self, service):
        """Test executing non-existent rule."""
        service.repository.get_by_id = AsyncMock(return_value=None)

        rule_id = AutomationRuleId.generate()
        result = await service.execute_rule(rule_id, {})

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_rule_disabled(self, service, sample_rule):
        """Test executing disabled rule."""
        sample_rule.enabled = False
        service.repository.get_by_id = AsyncMock(return_value=sample_rule)

        result = await service.execute_rule(sample_rule.id, {})

        assert result["success"] is False
        assert "disabled" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_rule_failure(self, service, sample_rule):
        """Test rule execution failure."""
        service.repository.get_by_id = AsyncMock(return_value=sample_rule)
        service.repository.update = AsyncMock()
        service._execute_action = AsyncMock(side_effect=Exception("Test error"))

        context = {"track_id": "123"}
        result = await service.execute_rule(sample_rule.id, context)

        assert result["success"] is False
        assert "Test error" in result["error"]
        assert sample_rule.total_executions == 1
        assert sample_rule.successful_executions == 0
        assert sample_rule.failed_executions == 1

    @pytest.mark.asyncio
    async def test_execute_action_search_and_download(self, service, sample_rule):
        """Test search and download action."""
        sample_rule.action = AutomationAction.SEARCH_AND_DOWNLOAD
        service._action_search_and_download = AsyncMock(return_value={"success": True})

        context = {"track_id": "123"}
        result = await service._execute_action(sample_rule, context)

        assert result["success"] is True
        service._action_search_and_download.assert_called_once_with(sample_rule, context)

    @pytest.mark.asyncio
    async def test_execute_action_notify_only(self, service, sample_rule):
        """Test notify only action."""
        sample_rule.action = AutomationAction.NOTIFY_ONLY
        service._action_notify_only = AsyncMock(return_value={"success": True})

        context = {"track_id": "123"}
        result = await service._execute_action(sample_rule, context)

        assert result["success"] is True
        service._action_notify_only.assert_called_once_with(sample_rule, context)

    @pytest.mark.asyncio
    async def test_execute_action_add_to_queue(self, service, sample_rule):
        """Test add to queue action."""
        sample_rule.action = AutomationAction.ADD_TO_QUEUE
        service._action_add_to_queue = AsyncMock(return_value={"success": True})

        context = {"track_id": "123"}
        result = await service._execute_action(sample_rule, context)

        assert result["success"] is True
        service._action_add_to_queue.assert_called_once_with(sample_rule, context)

    @pytest.mark.asyncio
    async def test_execute_action_unknown(self, service, sample_rule):
        """Test unknown action raises error."""
        # Create a rule with an invalid action (by bypassing normal creation)
        sample_rule.action = MagicMock()
        sample_rule.action.value = "invalid_action"

        with pytest.raises(ValueError, match="Unknown action"):
            await service._execute_action(sample_rule, {})

    @pytest.mark.asyncio
    async def test_action_search_and_download(self, service, sample_rule):
        """Test search and download action implementation."""
        context = {
            "track_ids": ["123", "456"],
            "album_info": {"name": "Test Album"},
        }

        result = await service._action_search_and_download(sample_rule, context)

        assert result["success"] is True
        assert "context" in result

    @pytest.mark.asyncio
    async def test_action_notify_only(self, service, sample_rule, mock_notification_service):
        """Test notify only action."""
        context = {"message": "Test notification"}

        result = await service._action_notify_only(sample_rule, context)

        # Should return success
        assert "success" in result or result is not None

    @pytest.mark.asyncio
    async def test_action_add_to_queue(self, service, sample_rule):
        """Test add to queue action."""
        context = {"track_id": "123"}

        result = await service._action_add_to_queue(sample_rule, context)

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_trigger_workflow(self, service, sample_rule):
        """Test triggering workflow for a trigger type."""
        service.repository.list_by_trigger = AsyncMock(return_value=[sample_rule])
        service.execute_rule = AsyncMock(return_value={"success": True})

        context = {"test": "data"}
        results = await service.trigger_workflow(AutomationTrigger.NEW_RELEASE, context)

        assert len(results) == 1
        assert results[0]["rule_id"] == str(sample_rule.id.value)
        assert results[0]["rule_name"] == sample_rule.name
        assert "result" in results[0]
        service.execute_rule.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_workflow_no_rules(self, service):
        """Test triggering workflow with no matching rules."""
        service.repository.list_by_trigger = AsyncMock(return_value=[])

        results = await service.trigger_workflow(AutomationTrigger.NEW_RELEASE, {})

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_trigger_workflow_multiple_rules(self, service):
        """Test triggering workflow with multiple rules."""
        rule1 = AutomationRule(
            id=AutomationRuleId.generate(),
            name="Rule 1",
            trigger=AutomationTrigger.NEW_RELEASE,
            action=AutomationAction.SEARCH_AND_DOWNLOAD,
            enabled=True,
            priority=1,
            quality_profile="high",
            apply_filters=True,
            auto_process=True,
        )

        rule2 = AutomationRule(
            id=AutomationRuleId.generate(),
            name="Rule 2",
            trigger=AutomationTrigger.NEW_RELEASE,
            action=AutomationAction.NOTIFY_ONLY,
            enabled=True,
            priority=0,
            quality_profile="medium",
            apply_filters=False,
            auto_process=False,
        )

        service.repository.list_by_trigger = AsyncMock(return_value=[rule1, rule2])
        service.execute_rule = AsyncMock(return_value={"success": True})

        results = await service.trigger_workflow(AutomationTrigger.NEW_RELEASE, {})

        assert len(results) == 2
        assert service.execute_rule.call_count == 2
