"""Automation: workflow rules endpoints.

Mounted under `/automation` by `automation.py`.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from soulspot.api.dependencies import get_db_session

router = APIRouter()


# Hey, automation rules are the WORKFLOW system - "when X happens, do Y"!
class CreateAutomationRuleRequest(BaseModel):
    """Request to create an automation rule."""

    name: str
    trigger: str  # "new_release", "missing_album", "quality_upgrade", "manual"
    action: str  # "search_and_download", "notify_only", "add_to_queue"
    priority: int = 0
    quality_profile: str = "high"
    apply_filters: bool = True
    auto_process: bool = True
    description: str | None = None


@router.post("/rules")
async def create_automation_rule(
    request: CreateAutomationRuleRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a new automation rule."""
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.entities import AutomationAction, AutomationTrigger

        service = AutomationWorkflowService(session)
        rule = await service.create_rule(
            name=request.name,
            trigger=AutomationTrigger(request.trigger),
            action=AutomationAction(request.action),
            priority=request.priority,
            quality_profile=request.quality_profile,
            apply_filters=request.apply_filters,
            auto_process=request.auto_process,
            description=request.description,
        )
        await session.commit()

        return {
            "id": str(rule.id.value),
            "name": rule.name,
            "trigger": rule.trigger.value,
            "action": rule.action.value,
            "enabled": rule.enabled,
            "priority": rule.priority,
            "quality_profile": rule.quality_profile,
            "apply_filters": rule.apply_filters,
            "auto_process": rule.auto_process,
            "description": rule.description,
            "created_at": rule.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to create automation rule: {e}"
        ) from e


@router.get("/rules")
async def list_automation_rules(
    trigger: str | None = None,
    enabled_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List automation rules."""
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.entities import AutomationTrigger

        service = AutomationWorkflowService(session)

        if enabled_only:
            rules = await service.list_enabled()
        elif trigger:
            rules = await service.list_by_trigger(AutomationTrigger(trigger))
        else:
            rules = await service.list_all(limit, offset)

        return {
            "rules": [
                {
                    "id": str(r.id.value),
                    "name": r.name,
                    "trigger": r.trigger.value,
                    "action": r.action.value,
                    "enabled": r.enabled,
                    "priority": r.priority,
                    "quality_profile": r.quality_profile,
                    "apply_filters": r.apply_filters,
                    "auto_process": r.auto_process,
                    "total_executions": r.total_executions,
                    "successful_executions": r.successful_executions,
                    "failed_executions": r.failed_executions,
                }
                for r in rules
            ],
            "count": len(rules),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list automation rules: {e}") from e


@router.get("/rules/{rule_id}")
async def get_automation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get a specific automation rule."""
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        service = AutomationWorkflowService(session)
        rule = await service.get_rule(AutomationRuleId.from_string(rule_id))

        if not rule:
            raise HTTPException(status_code=404, detail="Automation rule not found")

        return {
            "id": str(rule.id.value),
            "name": rule.name,
            "trigger": rule.trigger.value,
            "action": rule.action.value,
            "enabled": rule.enabled,
            "priority": rule.priority,
            "quality_profile": rule.quality_profile,
            "apply_filters": rule.apply_filters,
            "auto_process": rule.auto_process,
            "description": rule.description,
            "last_triggered_at": rule.last_triggered_at.isoformat()
            if rule.last_triggered_at
            else None,
            "total_executions": rule.total_executions,
            "successful_executions": rule.successful_executions,
            "failed_executions": rule.failed_executions,
            "created_at": rule.created_at.isoformat(),
            "updated_at": rule.updated_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get automation rule: {e}") from e


@router.post("/rules/{rule_id}/enable")
async def enable_automation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Enable an automation rule."""
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        service = AutomationWorkflowService(session)
        await service.enable_rule(AutomationRuleId.from_string(rule_id))
        await session.commit()

        return {"message": "Automation rule enabled successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to enable automation rule: {e}") from e


@router.post("/rules/{rule_id}/disable")
async def disable_automation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Disable an automation rule."""
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        service = AutomationWorkflowService(session)
        await service.disable_rule(AutomationRuleId.from_string(rule_id))
        await session.commit()

        return {"message": "Automation rule disabled successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to disable automation rule: {e}") from e


@router.delete("/rules/{rule_id}")
async def delete_automation_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    """Delete an automation rule."""
    try:
        from soulspot.application.services.automation_workflow_service import (
            AutomationWorkflowService,
        )
        from soulspot.domain.value_objects import AutomationRuleId

        service = AutomationWorkflowService(session)
        await service.delete_rule(AutomationRuleId.from_string(rule_id))
        await session.commit()

        return {"message": "Automation rule deleted successfully"}
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete automation rule: {e}") from e
