"""Tool schemas for proactive todo plan tools."""

_SKILL_REF = (
    'Load workflow first: skill_view("hermes-plugin-proactive-todo:proactive-todo"). '
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
        "plugin is enabled). Use for multi-step work: goal, acceptance criteria, items "
        "with depends_on, recommended_models, and nested subitems. "
        + _SKILL_REF
        + "Root plan: omit parent_item_id, merge=false, provide goal + items. "
        "Sub-plan (subagent): set plan_session_id + parent_item_id, merge=false to "
        "replace subitems under that parent. merge=true patches by global item id. "
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
                                "completed",
                                "cancelled",
                                "blocked",
                            ],
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
        "tell the user the task is finished until scope=plan returns ok:true. Returns "
        "plan_summary (emoji progress) and syncs the Hermes standing goal for the judge. "
        "Append plan_summary to the user-facing final message. Subagents must not call "
        "scope=plan. " + _SKILL_REF
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
                "description": "Required when scope=item.",
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
                "description": "If true and verify passes, set status completed.",
                "default": True,
            },
        },
        "required": ["scope"],
    },
}
