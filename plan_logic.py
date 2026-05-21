"""Tree operations, dependencies, readiness, and verification helpers."""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any

VALID_STATUSES = frozenset({
    "pending", "in_progress", "completed", "cancelled", "blocked",
})
VALID_VERIFICATION = frozenset({"unverified", "passed", "failed"})


def max_depth() -> int:
    try:
        return max(1, int(os.environ.get("PROACTIVE_TODO_MAX_DEPTH", "5")))
    except ValueError:
        return 5


def default_verification() -> dict[str, Any]:
    return {
        "status": "unverified",
        "evidence": "",
        "criteria_results": [],
        "checked_at": "",
    }


def normalize_item(raw: dict[str, Any]) -> dict[str, Any]:
    item_id = str(raw.get("id", "")).strip()
    if not item_id:
        raise ValueError("each item requires a non-empty id")

    status = str(raw.get("status", "pending")).strip().lower()
    if status not in VALID_STATUSES:
        status = "pending"

    verification = raw.get("verification")
    if not isinstance(verification, dict):
        verification = default_verification()
    else:
        vstatus = str(verification.get("status", "unverified")).strip().lower()
        if vstatus not in VALID_VERIFICATION:
            vstatus = "unverified"
        verification = {
            "status": vstatus,
            "evidence": str(verification.get("evidence", "")),
            "criteria_results": verification.get("criteria_results") or [],
            "checked_at": str(verification.get("checked_at", "")),
        }

    subitems_raw = raw.get("items") or []
    subitems = [normalize_item(s) for s in subitems_raw if isinstance(s, dict)]

    return {
        "id": item_id,
        "title": str(raw.get("title", "")).strip() or item_id,
        "description": str(raw.get("description", "")).strip(),
        "acceptance_criteria": [
            str(c).strip() for c in (raw.get("acceptance_criteria") or []) if str(c).strip()
        ],
        "recommended_models": [
            str(m).strip() for m in (raw.get("recommended_models") or []) if str(m).strip()
        ],
        "depends_on": [
            str(d).strip() for d in (raw.get("depends_on") or []) if str(d).strip()
        ],
        "status": status,
        "verification": verification,
        "items": subitems,
    }


def walk_items(
    items: list[dict[str, Any]],
    parent_path: list[str] | None = None,
):
    """Yield (item, path_ids) depth-first."""
    parent_path = parent_path or []
    for item in items:
        path = parent_path + [item["id"]]
        yield item, path
        yield from walk_items(item.get("items") or [], path)


def index_by_id(plan: dict[str, Any]) -> dict[str, tuple[dict[str, Any], list[str]]]:
    out: dict[str, tuple[dict[str, Any], list[str]]] = {}
    for item, path in walk_items(plan.get("items") or []):
        if item["id"] in out:
            raise ValueError(f"duplicate item id: {item['id']}")
        out[item["id"]] = (item, path)
    return out


def item_depth(path: list[str]) -> int:
    return len(path)


def find_parent_list(
    plan: dict[str, Any], parent_item_id: str | None,
) -> list[dict[str, Any]]:
    if not parent_item_id:
        return plan.setdefault("items", [])
    idx = index_by_id(plan)
    if parent_item_id not in idx:
        raise ValueError(f"parent_item_id not found: {parent_item_id}")
    parent, _path = idx[parent_item_id]
    return parent.setdefault("items", [])


def find_item(plan: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    idx = index_by_id(plan)
    if item_id in idx:
        return idx[item_id][0]
    return None


def is_passed(item: dict[str, Any]) -> bool:
    return (
        item.get("status") == "completed"
        and (item.get("verification") or {}).get("status") == "passed"
    )


def descendants_complete(item: dict[str, Any]) -> tuple[bool, list[str]]:
    incomplete: list[str] = []
    for sub, _path in walk_items(item.get("items") or []):
        if not is_passed(sub):
            incomplete.append(sub["id"])
    return (len(incomplete) == 0, incomplete)


def deps_satisfied(plan: dict[str, Any], item: dict[str, Any]) -> bool:
    idx = index_by_id(plan)
    for dep_id in item.get("depends_on") or []:
        if dep_id not in idx:
            return False
        dep_item, _ = idx[dep_id]
        if not is_passed(dep_item):
            return False
    return True


def compute_ready(items: list[dict[str, Any]], plan: dict[str, Any]) -> list[str]:
    ready: list[str] = []
    for item, _path in walk_items(items):
        if item["status"] not in ("pending", "in_progress", "blocked"):
            continue
        if deps_satisfied(plan, item):
            ready.append(item["id"])
    return ready


def check_dep_cycle(plan: dict[str, Any]) -> None:
    idx = index_by_id(plan)

    def visit(node_id: str, stack: set[str]) -> None:
        if node_id in stack:
            raise ValueError(f"depends_on cycle involving {node_id}")
        if node_id not in idx:
            return
        stack.add(node_id)
        item, _ = idx[node_id]
        for dep in item.get("depends_on") or []:
            visit(dep, stack)
        stack.remove(node_id)

    for item_id in idx:
        visit(item_id, set())


def max_tree_depth(items: list[dict[str, Any]], base_depth: int = 1) -> int:
    if not items:
        return base_depth - 1 if base_depth > 1 else 0
    deepest = base_depth
    for item in items:
        sub_depth = max_tree_depth(item.get("items") or [], base_depth + 1)
        deepest = max(deepest, sub_depth)
    return deepest


def validate_plan_depth(plan: dict[str, Any], extra_items: list[dict[str, Any]] | None = None) -> None:
    depth = max_tree_depth(plan.get("items") or [])
    if extra_items is not None:
        depth = max(depth, max_tree_depth(extra_items))
    if depth > max_depth():
        raise ValueError(f"plan depth {depth} exceeds PROACTIVE_TODO_MAX_DEPTH ({max_depth()})")


def merge_items(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    merge: bool,
) -> list[dict[str, Any]]:
    incoming_norm = [normalize_item(i) for i in incoming]
    if not merge:
        return incoming_norm

    by_id = {item["id"]: deepcopy(item) for item in existing}
    order = [item["id"] for item in existing]

    for inc in incoming_norm:
        iid = inc["id"]
        if iid in by_id:
            cur = by_id[iid]
            for key in ("title", "description", "status"):
                if inc.get(key):
                    cur[key] = inc[key]
            if inc.get("acceptance_criteria"):
                cur["acceptance_criteria"] = inc["acceptance_criteria"]
            if inc.get("recommended_models"):
                cur["recommended_models"] = inc["recommended_models"]
            if inc.get("depends_on"):
                cur["depends_on"] = inc["depends_on"]
            if inc.get("verification"):
                cur["verification"] = inc["verification"]
            if inc.get("items"):
                cur["items"] = merge_items(
                    cur.get("items") or [],
                    inc["items"],
                    merge=True,
                )
        else:
            by_id[iid] = inc
            order.append(iid)

    return [by_id[i] for i in order if i in by_id]


def path_string(path: list[str]) -> str:
    return " > ".join(path) if path else ""


def blocking_reasons(plan: dict[str, Any]) -> list[dict[str, str]]:
    reasons: list[dict[str, str]] = []
    idx = index_by_id(plan)
    for item, path in walk_items(plan.get("items") or []):
        if item["status"] in ("completed", "cancelled"):
            continue
        for dep_id in item.get("depends_on") or []:
            if dep_id not in idx:
                reasons.append({
                    "item_id": item["id"],
                    "path": path_string(path),
                    "reason": f"missing dependency id: {dep_id}",
                })
            elif not is_passed(idx[dep_id][0]):
                reasons.append({
                    "item_id": item["id"],
                    "path": path_string(path),
                    "reason": f"waiting on dependency: {dep_id}",
                })
    return reasons


def active_subplans(plan: dict[str, Any]) -> list[str]:
    active: list[str] = []
    for item, path in walk_items(plan.get("items") or []):
        if item["status"] == "in_progress" and item.get("items"):
            active.append(path_string(path))
    return active


def plan_tree_complete(plan: dict[str, Any]) -> bool:
    for item, _path in walk_items(plan.get("items") or []):
        if item["status"] != "completed":
            return False
        if (item.get("verification") or {}).get("status") != "passed":
            return False
    return bool(plan.get("items"))


def build_derived(
    plan: dict[str, Any],
    focus_item_id: str | None = None,
) -> dict[str, Any]:
    idx = index_by_id(plan)
    root_items = plan.get("items") or []

    ready_items = compute_ready(root_items, plan)

    focus_item = None
    ready_subitems: list[str] = []
    parent_context: dict[str, str] | None = None

    if focus_item_id:
        if focus_item_id not in idx:
            raise ValueError(f"focus_item_id not found: {focus_item_id}")
        focus_item, fpath = idx[focus_item_id]
        ready_subitems = compute_ready(focus_item.get("items") or [], plan)
        if len(fpath) > 1:
            parent_id = fpath[-2]
            parent, _ = idx[parent_id]
            parent_context = {
                "id": parent_id,
                "title": parent.get("title", ""),
            }
        parent_context = parent_context or {
            "id": focus_item_id,
            "title": focus_item.get("title", ""),
            "description": (focus_item.get("description") or "")[:500],
        }

    item_paths = {iid: path_string(path) for iid, (_it, path) in idx.items()}

    return {
        "ready_items": ready_items,
        "ready_subitems": ready_subitems,
        "parallel_groups": [ready_items] if ready_items else [],
        "parallel_subitem_groups": [ready_subitems] if ready_subitems else [],
        "blocking_reasons": blocking_reasons(plan),
        "plan_complete": plan_tree_complete(plan),
        "plan_verified": bool(plan.get("plan_verified")),
        "active_subplans": active_subplans(plan),
        "item_paths": item_paths,
        "focus_item": (
            {
                "id": focus_item["id"],
                "title": focus_item.get("title", ""),
                "status": focus_item.get("status", ""),
            }
            if focus_item
            else None
        ),
        "parent_context": parent_context,
    }


def subtree_copy(plan: dict[str, Any], focus_item_id: str) -> dict[str, Any]:
    item = find_item(plan, focus_item_id)
    if not item:
        raise ValueError(f"focus_item_id not found: {focus_item_id}")
    return {
        "goal": plan.get("goal", ""),
        "focus_root": deepcopy(item),
        "items": deepcopy(item.get("items") or []),
    }


def item_status_emoji(item: dict[str, Any]) -> str:
    """Single-line status marker from plan JSON (authoritative for summaries)."""
    status = item.get("status", "pending")
    vstatus = (item.get("verification") or {}).get("status", "unverified")

    if status == "cancelled":
        return "⛔"
    if status == "blocked":
        return "🚫"
    if vstatus == "passed" and status == "completed":
        return "✅"
    if vstatus == "failed":
        return "❌"
    if status == "completed":
        return "⚠️"
    if status == "in_progress":
        return "🔄"
    return "⬜"


def item_verify_label(item: dict[str, Any]) -> str:
    vstatus = (item.get("verification") or {}).get("status", "unverified")
    if vstatus == "passed":
        return "passed"
    if vstatus == "failed":
        return "failed"
    if item.get("status") == "completed":
        return "completed_unverified"
    return item.get("status", "pending")


def count_item_stats(plan: dict[str, Any]) -> tuple[int, int, int]:
    """Return (passed_count, total_count, failed_verify_count)."""
    passed = total = failed = 0
    for item, _path in walk_items(plan.get("items") or []):
        total += 1
        if is_passed(item):
            passed += 1
        elif (item.get("verification") or {}).get("status") == "failed":
            failed += 1
    return passed, total, failed


def build_judge_flags(plan: dict[str, Any]) -> dict[str, str]:
    """Explicit boolean flags for goal_judge (plain key: value, ASCII only)."""
    passed, total, failed = count_item_stats(plan)
    plan_verified = bool(plan.get("plan_verified"))
    tree_complete = plan_tree_complete(plan)
    all_items_passed = total > 0 and passed == total
    has_failed_verify = failed > 0

    judge_may_mark_done = (
        plan_verified
        and tree_complete
        and all_items_passed
        and not has_failed_verify
    )
    work_remaining = not judge_may_mark_done

    ready = compute_ready(plan.get("items") or [], plan)
    in_progress = sum(
        1
        for item, _path in walk_items(plan.get("items") or [])
        if item.get("status") == "in_progress"
    )

    return {
        "DONE_GATE": "closed" if judge_may_mark_done else "open",
        "JUDGE_MAY_MARK_DONE": "true" if judge_may_mark_done else "false",
        "WORK_REMAINING": "true" if work_remaining else "false",
        "PLAN_VERIFIED": "true" if plan_verified else "false",
        "PLAN_TREE_COMPLETE": "true" if tree_complete else "false",
        "ALL_ITEMS_PASSED": "true" if all_items_passed else "false",
        "HAS_FAILED_VERIFY": "true" if has_failed_verify else "false",
        "ITEMS_PASSED": f"{passed}/{total}",
        "READY_ITEM_COUNT": str(len(ready)),
        "IN_PROGRESS_ITEM_COUNT": str(in_progress),
    }


def format_plan_summary(plan: dict[str, Any]) -> str:
    """Compact plan digest with judge flags and emoji markers."""
    flags = build_judge_flags(plan)
    outcome = (plan.get("goal") or "").strip() or "(no goal text)"

    lines = [
        "--- PLAN_PROGRESS (authoritative, do not invent) ---",
        "JUDGE_FLAGS:",
    ]
    for key in (
        "DONE_GATE",
        "JUDGE_MAY_MARK_DONE",
        "WORK_REMAINING",
        "PLAN_VERIFIED",
        "PLAN_TREE_COMPLETE",
        "ALL_ITEMS_PASSED",
        "HAS_FAILED_VERIFY",
        "ITEMS_PASSED",
        "READY_ITEM_COUNT",
        "IN_PROGRESS_ITEM_COUNT",
    ):
        lines.append(f"{key}: {flags[key]}")

    lines.append(f"OUTCOME: {outcome}")

    plan_criteria = plan.get("acceptance_criteria") or []
    if plan_criteria:
        crit_state = "met" if flags["PLAN_VERIFIED"] == "true" else "pending"
        lines.append(f"PLAN_CRITERIA: {crit_state} ({len(plan_criteria)} defined)")

    lines.append("ITEMS:")

    for item, path in walk_items(plan.get("items") or []):
        emoji = item_status_emoji(item)
        path_label = path_string(path) or item["id"]
        title = (item.get("title") or item["id"]).strip()
        label = item_verify_label(item)
        lines.append(f"{emoji} {path_label} | {title} | {label}")

    lines.append("--- END PLAN_PROGRESS ---")
    return "\n".join(lines)
