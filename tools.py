"""Tool handlers for proactive todo plans."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import goals_bind
from . import plan_logic as pl
from .store import empty_plan, load_plan, save_plan


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _resolve_session(args: dict[str, Any], kwargs: dict[str, Any]) -> str:
    sid = (args.get("plan_session_id") or kwargs.get("session_id") or "").strip()
    if not sid:
        sid = (kwargs.get("task_id") or "").strip()
    if not sid:
        raise ValueError("plan_session_id or session_id is required")
    return sid


def _load_or_empty(session_id: str) -> dict[str, Any]:
    plan = load_plan(session_id)
    if plan is None:
        return empty_plan()
    return plan


_VERIFY_EVIDENCE_MAX = 200


def _sync_goal_only(session_id: str, plan: dict[str, Any]) -> dict[str, Any]:
    """Sync standing goal; omit plan_summary from tool payload."""
    payload: dict[str, Any] = {}
    if goals_bind.sync_goal_progress(session_id, plan):
        payload["goal_synced"] = True
    return payload


def _goal_payload(
    session_id: str,
    plan: dict[str, Any],
    *,
    include_summary: bool = False,
) -> dict[str, Any]:
    payload = _sync_goal_only(session_id, plan)
    if include_summary:
        payload["plan_summary"] = pl.format_plan_summary(plan)
    return payload


def _cap_evidence(text: str, max_len: int = _VERIFY_EVIDENCE_MAX) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _slim_verification(verification: dict[str, Any] | None) -> dict[str, Any]:
    if not verification:
        return {"status": "unverified"}
    out: dict[str, Any] = {"status": verification.get("status", "unverified")}
    evidence = str(verification.get("evidence") or "").strip()
    if evidence:
        out["evidence"] = _cap_evidence(evidence)
    return out


def _verify_failure_payload(
    session_id: str,
    plan: dict[str, Any],
    *,
    include_plan_summary: bool,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "session_id": session_id,
        "progress": pl.format_progress_flags(plan),
        **_sync_goal_only(session_id, plan),
    }
    if include_plan_summary:
        out["plan_summary"] = pl.format_plan_summary(plan)
    return out


def _response(
    plan: dict[str, Any],
    session_id: str,
    *,
    include_full_plan: bool = True,
    focus_item_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    derived = pl.build_derived(plan, focus_item_id)
    out: dict[str, Any] = {
        "ok": True,
        "session_id": session_id,
        "derived": derived,
    }
    if include_full_plan:
        out["plan"] = plan
    elif focus_item_id:
        out["subtree"] = pl.subtree_copy(plan, focus_item_id)
    if extra:
        out.update(extra)
    return out


def proactive_todo_write(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        session_id = _resolve_session(args, kwargs)
        parent_item_id = (args.get("parent_item_id") or "").strip() or None
        merge = bool(args.get("merge", False))
        incoming = args.get("items")
        include_full = bool(args.get("include_full_plan", True))

        plan = _load_or_empty(session_id)

        if incoming is not None and isinstance(incoming, list):
            disallowed = pl.collect_disallowed_write_statuses(incoming)
            if disallowed:
                return _json({
                    "ok": False,
                    "error": (
                        "status completed is only allowed via proactive_todo_verify; "
                        "call proactive_todo_verify(scope=item) after each item's work"
                    ),
                    "disallowed_item_ids": disallowed,
                })

        if parent_item_id:
            idx = pl.index_by_id(plan)
            if parent_item_id not in idx:
                return _json({"ok": False, "error": f"parent_item_id not found: {parent_item_id}"})
            parent, path = idx[parent_item_id]
            if parent["status"] == "pending":
                parent["status"] = "in_progress"

            if incoming is None:
                return _json({"ok": False, "error": "items is required for sub-plan writes"})

            target_list = pl.find_parent_list(plan, parent_item_id)
            new_items = pl.merge_items(target_list, incoming, merge)
            pl.validate_plan_depth(plan, new_items)

            depth_parent = pl.item_depth(path) + pl.max_tree_depth(new_items)
            if depth_parent > pl.max_depth():
                return _json({
                    "ok": False,
                    "error": f"sub-plan depth exceeds PROACTIVE_TODO_MAX_DEPTH ({pl.max_depth()})",
                })

            parent["items"] = new_items
        else:
            if not merge:
                goal = (args.get("goal") or "").strip()
                if not goal:
                    return _json({"ok": False, "error": "goal is required for a new root plan"})
                plan["goal"] = goal
                plan["acceptance_criteria"] = [
                    str(c).strip()
                    for c in (args.get("acceptance_criteria") or [])
                    if str(c).strip()
                ]
                plan["status"] = "active"
                plan["plan_verified"] = False
                if incoming is None:
                    return _json({"ok": False, "error": "items is required for a new root plan"})
                plan["items"] = [pl.normalize_item(i) for i in incoming if isinstance(i, dict)]
            else:
                if incoming is None:
                    return _json({"ok": False, "error": "items is required for merge=true"})
                plan["items"] = pl.merge_items(
                    plan.get("items") or [],
                    incoming,
                    merge=True,
                )
                if args.get("goal"):
                    plan["goal"] = str(args["goal"]).strip()
                if args.get("acceptance_criteria") is not None:
                    plan["acceptance_criteria"] = [
                        str(c).strip()
                        for c in args["acceptance_criteria"]
                        if str(c).strip()
                    ]

            pl.validate_plan_depth(plan)

        pl.check_dep_cycle(plan)
        pl.index_by_id(plan)

        save_plan(session_id, plan)

        extra: dict[str, Any] = {}
        if not parent_item_id and not merge:
            if goals_bind.bind_goal_on_plan_start(session_id, plan):
                extra["goal_bound"] = True
        extra.update(_sync_goal_only(session_id, plan))

        return _json(_response(
            plan,
            session_id,
            include_full_plan=include_full,
            focus_item_id=parent_item_id if parent_item_id and not include_full else None,
            extra=extra or None,
        ))
    except ValueError as exc:
        return _json({"ok": False, "error": str(exc)})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})


def proactive_todo_read(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        session_id = _resolve_session(args, kwargs)
        focus_item_id = (args.get("focus_item_id") or "").strip() or None
        include_full = bool(args.get("include_full_plan", True))

        plan = load_plan(session_id)
        if plan is None:
            return _json({
                "ok": True,
                "session_id": session_id,
                "plan": None,
                "derived": {
                    "ready_items": [],
                    "ready_subitems": [],
                    "plan_complete": False,
                    "plan_verified": False,
                },
            })

        return _json(_response(
            plan,
            session_id,
            include_full_plan=include_full,
            focus_item_id=focus_item_id,
        ))
    except ValueError as exc:
        return _json({"ok": False, "error": str(exc)})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})


def _check_criteria(
    criteria: list[str],
    criteria_results: list[dict[str, Any]],
) -> tuple[bool, list[str]]:
    if not criteria:
        return True, []

    by_text: dict[str, bool] = {}
    for row in criteria_results:
        if not isinstance(row, dict):
            continue
        crit = str(row.get("criterion", "")).strip()
        if crit:
            by_text[crit] = bool(row.get("met"))

    failed: list[str] = []
    for c in criteria:
        if not by_text.get(c):
            failed.append(c)
    return len(failed) == 0, failed


def proactive_todo_verify(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        session_id = _resolve_session(args, kwargs)
        scope = str(args.get("scope", "")).strip().lower()
        evidence = str(args.get("evidence", "")).strip()
        criteria_results = args.get("criteria_results") or []
        mark_complete = bool(args.get("mark_complete", True))
        include_plan_summary = bool(args.get("include_plan_summary", False))

        plan = load_plan(session_id)
        if plan is None:
            return _json({"ok": False, "error": "no plan for this session"})

        now = datetime.now(timezone.utc).isoformat()

        if scope == "item":
            item_id = (args.get("item_id") or "").strip()
            if not item_id:
                return _json({"ok": False, "error": "item_id is required when scope=item"})

            item = pl.find_item(plan, item_id)
            if item is None:
                return _json({"ok": False, "error": f"item not found: {item_id}"})

            sub_ok, incomplete = pl.descendants_complete(item)
            if not sub_ok:
                return _json({
                    "ok": False,
                    "must_continue": True,
                    "incomplete_subitems": incomplete,
                    "error": "all subitems must be completed and passed before verifying parent",
                })

            passed, failed_crit = _check_criteria(
                item.get("acceptance_criteria") or [],
                criteria_results,
            )
            if not passed:
                item["verification"] = {
                    "status": "failed",
                    "evidence": evidence,
                    "criteria_results": criteria_results,
                    "checked_at": now,
                }
                save_plan(session_id, plan)
                return _json({
                    "ok": False,
                    "must_continue": True,
                    "failed_criteria": failed_crit,
                    "error": "acceptance criteria not met",
                    **_verify_failure_payload(
                        session_id,
                        plan,
                        include_plan_summary=include_plan_summary,
                    ),
                })

            item["verification"] = {
                "status": "passed",
                "evidence": evidence,
                "criteria_results": criteria_results,
                "checked_at": now,
            }
            if mark_complete:
                item["status"] = "completed"

            save_plan(session_id, plan)
            item_line = pl.format_item_progress_line(plan, item_id)
            out: dict[str, Any] = {
                "ok": True,
                "scope": "item",
                "item_id": item_id,
                "session_id": session_id,
                "verification": _slim_verification(item["verification"]),
                "progress": pl.format_progress_flags(plan),
                **_sync_goal_only(session_id, plan),
            }
            if item_line:
                out["item_line"] = item_line
            if include_plan_summary:
                out["plan_summary"] = pl.format_plan_summary(plan)
            return _json(out)

        if scope == "plan":
            if not pl.plan_tree_complete(plan):
                return _json({
                    "ok": False,
                    "must_continue": True,
                    "error": "not all items are completed and passed",
                })

            passed, failed_crit = _check_criteria(
                plan.get("acceptance_criteria") or [],
                criteria_results,
            )
            if not passed:
                return _json({
                    "ok": False,
                    "must_continue": True,
                    "failed_criteria": failed_crit,
                    "error": "plan-level acceptance criteria not met",
                })

            plan["plan_verified"] = True
            plan["status"] = "completed"
            save_plan(session_id, plan)
            goal_extra: dict[str, Any] = _goal_payload(
                session_id,
                plan,
                include_summary=True,
            )
            if goals_bind.bind_goal_on_plan_complete(session_id, plan):
                goal_extra["goal_completed"] = True
            return _json({
                "ok": True,
                "scope": "plan",
                "plan_verified": True,
                "session_id": session_id,
                **goal_extra,
            })

        return _json({"ok": False, "error": "scope must be item or plan"})
    except ValueError as exc:
        return _json({"ok": False, "error": str(exc)})
    except Exception as exc:
        return _json({"ok": False, "error": str(exc)})
