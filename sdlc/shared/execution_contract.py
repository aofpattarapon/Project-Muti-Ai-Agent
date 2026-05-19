"""
Unified Runtime Execution Contract
=================================

Shared contract for:
  - workflow mode detection (full-loop vs bypass)
  - role-aware default task type selection
  - approval/rework/reject syntax parsing
  - standard runtime metadata used by Discord + Web bridge

Phase 12.3 goal:
  Keep the current runtime stable while giving every role the same
  execution vocabulary and router hints.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Optional

from shared.model_router import TaskType


class WorkflowMode(str, Enum):
    FULL_LOOP = "full_loop"
    BYPASS = "bypass"


class DecisionAction(str, Enum):
    APPROVE = "approved"
    REWORK = "rework_requested"
    REJECT = "rejected"


ROLE_DEFAULT_TASK_TYPES: dict[str, TaskType] = {
    "ceo": TaskType.PLANNING,
    "pm": TaskType.PLANNING,
    "ba": TaskType.PLANNING,
    "sa": TaskType.REASONING,
    "uxui": TaskType.PLANNING,
    "dev": TaskType.CODE_GENERATION,
    "qa": TaskType.REVIEW,
    "devops": TaskType.CODE_GENERATION,
}


MODE_ALIASES = {
    "full-loop": WorkflowMode.FULL_LOOP,
    "full_loop": WorkflowMode.FULL_LOOP,
    "full loop": WorkflowMode.FULL_LOOP,
    "pipeline": WorkflowMode.FULL_LOOP,
    "workflow": WorkflowMode.FULL_LOOP,
    "bypass": WorkflowMode.BYPASS,
    "single-role": WorkflowMode.BYPASS,
    "single_role": WorkflowMode.BYPASS,
    "single role": WorkflowMode.BYPASS,
    "direct": WorkflowMode.BYPASS,
}


TASK_TYPE_ALIASES = {
    "code": TaskType.CODE_GENERATION,
    "code_generation": TaskType.CODE_GENERATION,
    "coding": TaskType.CODE_GENERATION,
    "implementation": TaskType.CODE_GENERATION,
    "reasoning": TaskType.REASONING,
    "analysis": TaskType.REASONING,
    "architecture": TaskType.REASONING,
    "planning": TaskType.PLANNING,
    "requirements": TaskType.PLANNING,
    "document": TaskType.PLANNING,
    "docs": TaskType.PLANNING,
    "review": TaskType.REVIEW,
    "qa": TaskType.REVIEW,
    "status": TaskType.STATUS,
    "report": TaskType.STATUS,
    "generic": TaskType.GENERIC,
}


@dataclass
class ExecutionContext:
    role: str
    workflow_mode: WorkflowMode
    task_type: TaskType
    revision_count: int
    project_id: str = ""
    project_name: str = ""
    source: str = "runtime"
    requires_handoff: bool = True

    def to_dict(self) -> dict:
        data = asdict(self)
        data["workflow_mode"] = self.workflow_mode.value
        data["task_type"] = self.task_type.value
        return data


@dataclass
class DecisionIntent:
    action: DecisionAction
    note: str = ""


def _normalize_text(value: str) -> str:
    return " ".join((value or "").strip().split()).lower()


def _coerce_task_type(value: Optional[str]) -> Optional[TaskType]:
    if not value:
        return None
    normalized = _normalize_text(value).replace("-", "_")
    if normalized in TASK_TYPE_ALIASES:
        return TASK_TYPE_ALIASES[normalized]
    try:
        return TaskType(normalized)
    except Exception:
        return None


def _detect_workflow_mode(role: str, input_data: dict) -> WorkflowMode:
    explicit = (
        input_data.get("workflow_mode")
        or input_data.get("execution_mode")
        or input_data.get("mode")
    )
    if explicit:
        normalized = _normalize_text(str(explicit))
        if normalized in MODE_ALIASES:
            return MODE_ALIASES[normalized]

    if input_data.get("bypass_role") == role:
        return WorkflowMode.BYPASS
    if input_data.get("direct_request") or input_data.get("single_role_request"):
        return WorkflowMode.BYPASS
    return WorkflowMode.FULL_LOOP


def resolve_execution_context(role: str, input_data: dict, project_id: str = "", project_name: str = "") -> ExecutionContext:
    workflow_mode = _detect_workflow_mode(role, input_data)
    task_type = (
        _coerce_task_type(input_data.get("task_type"))
        or _coerce_task_type(input_data.get("work_type"))
        or ROLE_DEFAULT_TASK_TYPES.get(role, TaskType.GENERIC)
    )
    revision_count = int(input_data.get("revision_count", 0) or 0)
    source = str(input_data.get("source", "runtime"))
    requires_handoff = workflow_mode == WorkflowMode.FULL_LOOP

    return ExecutionContext(
        role=role,
        workflow_mode=workflow_mode,
        task_type=task_type,
        revision_count=revision_count,
        project_id=project_id,
        project_name=project_name,
        source=source,
        requires_handoff=requires_handoff,
    )


def parse_decision_message(content: str) -> Optional[DecisionIntent]:
    """
    Accept both unified syntax and legacy syntax:
      APPROVE
      REJECT <reason>
      REWORK <what to fix>
      !approve
      !reject <reason>
      !revise <comment>
    """
    if not content:
        return None

    raw = content.strip()
    normalized = _normalize_text(raw)

    if normalized.startswith("approve") or normalized.startswith("!approve"):
        note = raw.split(" ", 1)[1].strip() if " " in raw else ""
        return DecisionIntent(action=DecisionAction.APPROVE, note=note)

    if normalized.startswith("reject") or normalized.startswith("!reject"):
        note = raw.split(" ", 1)[1].strip() if " " in raw else ""
        return DecisionIntent(action=DecisionAction.REJECT, note=note)

    if normalized.startswith("rework") or normalized.startswith("!revise"):
        note = raw.split(" ", 1)[1].strip() if " " in raw else ""
        return DecisionIntent(action=DecisionAction.REWORK, note=note)

    return None


def decision_help_text() -> str:
    return "Reply: `APPROVE` | `REWORK <what to fix>` | `REJECT <reason>`"


def summarize_mode_label(workflow_mode: WorkflowMode) -> str:
    return "bypass" if workflow_mode == WorkflowMode.BYPASS else "full-loop"

