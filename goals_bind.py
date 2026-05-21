"""Bind proactive todo plans to Hermes GoalManager (/goal Ralph loop)."""

from __future__ import annotations

import logging
from typing import Any

from . import plan_logic as pl

logger = logging.getLogger(__name__)

GoalManager: Any = None
load_goal: Any = None
save_goal: Any = None

try:
    from hermes_cli.goals import GoalManager as _GoalManager
    from hermes_cli.goals import load_goal as _load_goal
    from hermes_cli.goals import save_goal as _save_goal

    GoalManager = _GoalManager
    load_goal = _load_goal
    save_goal = _save_goal
except ImportError:
    pass


def goals_available() -> bool:
    return GoalManager is not None and load_goal is not None and save_goal is not None


def build_standing_goal(plan: dict[str, Any], session_id: str) -> str:
    """Compose standing goal instructions for the judge."""
    user_goal = (plan.get("goal") or "").strip()
    lines = [
        "Execute the proactive todo execution plan for this session.",
        f"Coordinator session_id (use as plan_session_id in tools): {session_id}",
        "",
        "Workflow (required):",
        "1. proactive_todo_read before choosing the next step.",
        "2. Work ready_items from derived; respect depends_on.",
        "3. After each item's work: proactive_todo_verify(scope=item, item_id=..., criteria_results=...).",
        "4. When all items are done: proactive_todo_verify(scope=plan, criteria_results=...).",
        "5. Do not treat the work as complete until proactive_todo_verify(scope=plan) returns ok:true.",
        "6. In your final user-visible response when done, state explicitly that plan verification passed.",
        "7. Do not send PLAN_PROGRESS or per-item verify status to the user until the final deliverable.",
        "8. After item verify: continue with tools only; no user-visible progress messages.",
        "9. Do not re-list the plan checklist in user-visible replies during execution.",
        "10. Treat the PLAN_PROGRESS block below as authoritative for item/plan status.",
        "11. Mark goal DONE only when JUDGE_FLAGS show JUDGE_MAY_MARK_DONE: true "
        "(requires PLAN_VERIFIED: true and ALL_ITEMS_PASSED: true).",
        "",
        f"Plan outcome: {user_goal}",
    ]
    criteria = plan.get("acceptance_criteria") or []
    if criteria:
        lines.append("")
        lines.append("Plan acceptance criteria (all must be met at scope=plan verify):")
        for i, c in enumerate(criteria, 1):
            lines.append(f"  {i}. {c}")
    return "\n".join(lines)


def build_full_goal_text(plan: dict[str, Any], session_id: str) -> str:
    """Standing instructions plus machine-generated plan summary for the judge."""
    return build_standing_goal(plan, session_id) + "\n\n" + pl.format_plan_summary(plan)


def sync_goal_progress(session_id: str, plan: dict[str, Any]) -> bool:
    """Update active goal text from plan JSON without resetting turn budget."""
    if not session_id or not goals_available():
        return False
    try:
        state = load_goal(session_id)
        if state is None or state.status != "active":
            return False
        state.goal = build_full_goal_text(plan, session_id)
        save_goal(session_id, state)
        logger.debug("proactive_todo: goal progress synced session=%s", session_id)
        return True
    except Exception as exc:
        logger.debug("proactive_todo: goal sync skipped session=%s: %s", session_id, exc)
        return False


def bind_goal_on_plan_start(session_id: str, plan: dict[str, Any]) -> bool:
    """Set or replace standing goal when a root plan is created (merge=false)."""
    if not session_id or not goals_available():
        return False
    try:
        gm = GoalManager(session_id)
        if gm.has_goal():
            gm.clear()
        gm.set(build_full_goal_text(plan, session_id))
        logger.info("proactive_todo: goal bound session=%s", session_id)
        return True
    except Exception as exc:
        logger.debug("proactive_todo: goal bind skipped session=%s: %s", session_id, exc)
        return False


def bind_goal_on_plan_complete(session_id: str, plan: dict[str, Any]) -> bool:
    """Sync final digest into goal, then mark Hermes goal done."""
    if not session_id or not goals_available():
        return False
    try:
        sync_goal_progress(session_id, plan)
        gm = GoalManager(session_id)
        if gm.is_active():
            gm.mark_done("proactive todo plan verified")
            logger.info("proactive_todo: goal completed session=%s", session_id)
            return True
        return False
    except Exception as exc:
        logger.debug("proactive_todo: goal complete skipped session=%s: %s", session_id, exc)
        return False
