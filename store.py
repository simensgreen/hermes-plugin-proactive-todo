"""Persistent plan storage under HERMES_HOME."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PLAN: dict[str, Any] = {
    "goal": "",
    "acceptance_criteria": [],
    "status": "active",
    "items": [],
    "plan_verified": False,
    "updated_at": "",
}


def hermes_home() -> Path:
    raw = os.environ.get("HERMES_HOME", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".hermes"


def plans_dir() -> Path:
    return hermes_home() / "proactive-todos"


def plan_path(session_id: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)
    return plans_dir() / f"{safe}.json"


def load_plan(session_id: str) -> dict[str, Any] | None:
    path = plan_path(session_id)
    if not path.is_file():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def save_plan(session_id: str, plan: dict[str, Any]) -> None:
    path = plan_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    plan["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def empty_plan() -> dict[str, Any]:
    p = dict(DEFAULT_PLAN)
    p["updated_at"] = datetime.now(timezone.utc).isoformat()
    return p
