#!/usr/bin/env python3
"""Local smoke tests (run from plugin directory: python3 test_plugin.py)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class _FakeGoalState:
    def __init__(self, goal: str = "", status: str = "active"):
        self.goal = goal
        self.status = status


class _FakeGoalManager:
    instances: dict[str, "_FakeGoalManager"] = {}
    calls: list[tuple[str, str, str]] = []

    def __init__(self, session_id: str, **kwargs):
        existing = _FakeGoalManager.instances.get(session_id)
        if existing is not None:
            self.__dict__ = existing.__dict__
            return
        self.session_id = session_id
        self._goal: str | None = None
        self._active = False
        self._done = False
        _FakeGoalManager.instances[session_id] = self

    def has_goal(self) -> bool:
        return self._goal is not None and not self._done

    def is_active(self) -> bool:
        return self._active

    def clear(self) -> None:
        _FakeGoalManager.calls.append((self.session_id, "clear", ""))
        self._goal = None
        self._active = False

    def set(self, goal: str, **kwargs) -> None:
        _FakeGoalManager.calls.append((self.session_id, "set", goal[:80]))
        self._goal = goal
        self._active = True
        self._done = False

    def mark_done(self, reason: str) -> None:
        _FakeGoalManager.calls.append((self.session_id, "mark_done", reason))
        self._active = False
        self._done = True


def _fake_load_goal(session_id: str) -> _FakeGoalState | None:
    gm = _FakeGoalManager.instances.get(session_id)
    if not gm or not gm._goal:
        return None
    status = "active" if gm._active else "done"
    return _FakeGoalState(goal=gm._goal, status=status)


def _fake_save_goal(session_id: str, state: _FakeGoalState) -> None:
    gm = _FakeGoalManager.instances[session_id]
    gm._goal = state.goal
    gm._active = state.status == "active"


def _bootstrap_package():
    pkg_name = "hermes_plugin_proactive_todo"
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(ROOT)]
    pkg.__package__ = pkg_name
    sys.modules[pkg_name] = pkg

    import importlib.util

    for mod_name in ("store", "plan_logic", "goals_bind", "tools"):
        path = ROOT / f"{mod_name}.py"
        full = f"{pkg_name}.{mod_name}"
        spec = importlib.util.spec_from_file_location(full, path)
        module = importlib.util.module_from_spec(spec)
        module.__package__ = pkg_name
        sys.modules[full] = module
        spec.loader.exec_module(module)

    tools = sys.modules[f"{pkg_name}.tools"]
    goals_bind = sys.modules[f"{pkg_name}.goals_bind"]
    plan_logic = sys.modules[f"{pkg_name}.plan_logic"]
    goals_bind.GoalManager = _FakeGoalManager
    goals_bind.load_goal = _fake_load_goal
    goals_bind.save_goal = _fake_save_goal
    goals_bind.goals_available = lambda: True
    return tools, plan_logic


def main() -> None:
    os.environ["HERMES_HOME"] = tempfile.mkdtemp()
    _FakeGoalManager.instances.clear()
    _FakeGoalManager.calls.clear()
    tools, plan_logic = _bootstrap_package()
    sid = "test-session-1"

    summary_empty = plan_logic.format_plan_summary({
        "goal": "G",
        "items": [{"id": "x", "title": "T", "status": "pending", "items": []}],
    })
    assert "PLAN_PROGRESS" in summary_empty
    assert "JUDGE_FLAGS:" in summary_empty
    assert "JUDGE_MAY_MARK_DONE: false" in summary_empty
    assert "DONE_GATE: open" in summary_empty
    assert "⬜" in summary_empty

    r = json.loads(tools.proactive_todo_write({
        "goal": "Ship feature",
        "acceptance_criteria": ["Tests pass"],
        "merge": False,
        "items": [
            {"id": "a", "title": "Step A", "acceptance_criteria": ["A done"]},
            {"id": "b", "title": "Step B", "depends_on": ["a"], "acceptance_criteria": ["B done"]},
        ],
    }, session_id=sid))
    assert r["ok"], r
    assert r.get("goal_bound") is True
    bound_goal = _FakeGoalManager.instances[sid]._goal or ""
    assert "PLAN_PROGRESS" in bound_goal
    assert "Ship feature" in bound_goal

    for item_id, crit in [("a", ["A done"]), ("b", ["B done"])]:
        vr = json.loads(tools.proactive_todo_verify({
            "scope": "item",
            "item_id": item_id,
            "evidence": "ok",
            "criteria_results": [{"criterion": c, "met": True} for c in crit],
        }, session_id=sid))
        assert vr["ok"], vr
        assert "plan_summary" in vr
        assert vr.get("goal_synced") is True
        assert "✅" in vr["plan_summary"]

    plan_v = json.loads(tools.proactive_todo_verify({
        "scope": "plan",
        "evidence": "all done",
        "criteria_results": [{"criterion": "Tests pass", "met": True}],
    }, session_id=sid))
    assert plan_v["ok"], plan_v
    assert plan_v.get("goal_completed") is True
    assert "PLAN_VERIFIED: true" in plan_v["plan_summary"]
    assert "JUDGE_MAY_MARK_DONE: true" in plan_v["plan_summary"]
    assert "DONE_GATE: closed" in plan_v["plan_summary"]
    final_goal = _FakeGoalManager.instances[sid]._goal or ""
    assert "JUDGE_MAY_MARK_DONE: true" in final_goal
    assert any(c[1] == "mark_done" for c in _FakeGoalManager.calls)

    print("all smoke tests passed")


if __name__ == "__main__":
    main()
