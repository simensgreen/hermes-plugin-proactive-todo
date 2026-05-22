"""Tool schemas for proactive todo plan tools."""

_SKILL_REF = (
    'Non-trivial work: skill_view("hermes-plugin-proactive-todo:proactive-todo") '
    "before this tool (plugin skills are opt-in, not in the global skills index). "
)

_COMMON_PARAMS = {
    "plan_session_id": {
        "type": "string",
        "description": (
            "Coordinator session id for the plan file. Subagents must pass the lead "
            "session id. Defaults to the current session."
        ),
    },
    "parent_item_id": {
        "type": "string",
        "description": (
            "Write scope: null = root plan; set to a parent item id to replace or "
            "merge that item's subitems (sub-plan for delegate_task workers)."
        ),
    },
}

PROACTIVE_TODO_WRITE = {
    "name": "proactive_todo_write",
    "description": (
        "Create or update a proactive execution plan (replaces built-in todo when this "
        "plugin is enabled). Use when the request is non-trivial (multiple deliverables, "
        "gather-and-synthesize, multi-step or multi-file work, delegation, unclear scope; "
        "when unsure, treat as non-trivial). "
        + _SKILL_REF
        + "On a new non-trivial task: skill_view then root plan before web search, browser, "
        "or terminal. Root plan: omit parent_item_id, merge=false, provide goal + items. "
        "Sub-plan (subagent): set plan_session_id + parent_item_id, merge=false to "
        "replace subitems under that parent. merge=true patches by global item id. "
        "Do not use merge=false on an existing root plan (resets progress); use merge=true. "
        "Do not set status=completed in write — only proactive_todo_verify marks items "
        "completed and passed. Use in_progress while working. "
        "Never use the built-in todo tool when this plugin is active."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            **_COMMON_PARAMS,
            "merge": {
                "type": "boolean",
                "description": "false: replace at scope; true: patch items by id.",
                "default": False,
            },
            "goal": {
                "type": "string",
                "description": "One-sentence outcome (root plan only, merge=false).",
            },
            "acceptance_criteria": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Plan-level acceptance criteria (root, merge=false).",
            },
            "items": {
                "type": "array",
                "description": "Plan items at root or under parent_item_id.",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "acceptance_criteria": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "recommended_models": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "depends_on": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "status": {
                            "type": "string",
                            "enum": [
                                "pending",
                                "in_progress",
                                "cancelled",
                                "blocked",
                            ],
                            "description": (
                                "Workflow status only. completed is set by "
                                "proactive_todo_verify(scope=item), not write."
                            ),
                        },
                        "items": {
                            "type": "array",
                            "description": "Nested subitems (same shape, recursive).",
                            "items": {"type": "object"},
                        },
                    },
                    "required": ["id"],
                },
            },
            "include_full_plan": {
                "type": "boolean",
                "description": "If false, return a compact response after sub-plan writes.",
                "default": True,
            },
        },
        "required": [],
    },
}

PROACTIVE_TODO_READ = {
    "name": "proactive_todo_read",
    "description": (
        "Read the proactive execution plan and derived metadata (ready_items, "
        "ready_subitems, blockers). Call before each execution step and after context "
        "compression. Subagents: set plan_session_id and focus_item_id to the "
        "delegated parent item. " + _SKILL_REF
    ),
    "parameters": {
        "type": "object",
        "properties": {
            **_COMMON_PARAMS,
            "focus_item_id": {
                "type": "string",
                "description": (
                    "Narrow derived fields to this item's subtree (for subagents)."
                ),
            },
            "include_full_plan": {
                "type": "boolean",
                "description": "If false, omit full plan tree (metadata only).",
                "default": True,
            },
        },
        "required": [],
    },
}

PROACTIVE_TODO_VERIFY = {
    "name": "proactive_todo_verify",
    "description": (
        "Verify an item or the whole plan against acceptance criteria. Items with "
        "subitems cannot pass until all descendants are completed and passed. Do not "
        "tell the user the task is finished until scope=plan returns ok:true. "
        "Syncs PLAN_PROGRESS into the standing goal for the judge (not in tool JSON by "
        "default). scope=item: compact progress only. scope=plan: completion_note for agent "
        "context only — never mention plan/verify/todos to the user. Omit item_id "
        "for scope=plan. Subagents must not call scope=plan. "
        + _SKILL_REF
    ),
    "parameters": {
        "type": "object",
        "properties": {
            **_COMMON_PARAMS,
            "scope": {
                "type": "string",
                "enum": ["item", "plan"],
                "description": "item: verify one node; plan: verify entire tree + plan criteria.",
            },
            "item_id": {
                "type": "string",
                "description": "Required when scope=item. Omit when scope=plan.",
            },
            "evidence": {
                "type": "string",
                "description": "What was checked (commands, paths, links).",
            },
            "criteria_results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "criterion": {"type": "string"},
                        "met": {"type": "boolean"},
                        "note": {"type": "string"},
                    },
                    "required": ["criterion", "met"],
                },
                "description": "One entry per acceptance criterion for this scope.",
            },
            "mark_complete": {
                "type": "boolean",
                "description": "scope=item only: if true and verify passes, set status completed.",
                "default": True,
            },
            "include_plan_summary": {
                "type": "boolean",
                "description": (
                    "If true, include full PLAN_PROGRESS plan_summary in tool JSON (judge "
                    "channel only). Default false for both scopes."
                ),
                "default": False,
            },
        },
        "required": ["scope"],
    },
}
