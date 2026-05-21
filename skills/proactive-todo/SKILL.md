---
name: proactive-todo
description: "Use for multi-step in-session work when hermes-plugin-proactive-todo is enabled: build execution plans with acceptance criteria, dependencies, nested subitems, verification, and Hermes goal loop after root plan write."
metadata:
  hermes:
    tags:
      - proactive-todo
      - execution
      - verification
      - subagents
      - goals
    category: hermes-plugin
    version: "2.0.0"
    related_skills:
      - orchestrating
      - delegated-worker
---

# Proactive Todo (plugin)

## When to use

Activate when **hermes-plugin-proactive-todo** is enabled and the task needs more than one or two direct actions.

Do **not** use the built-in `todo` tool — use `proactive_todo_write`, `proactive_todo_read`, and `proactive_todo_verify` only.

## Goal loop (Hermes core)

After a **root** `proactive_todo_write` (`merge=false`), the plugin binds a standing goal via Hermes `GoalManager` (same mechanism as `/goal`). Hermes continues the session until the judge accepts completion or the turn budget is exhausted.

- You do **not** need to run `/goal` manually for coordinator work.
- Do **not** tell the user the task is complete until `proactive_todo_verify(scope=plan)` returns `ok: true`, then state that explicitly in your response.
- Subagents using `plan_session_id` do **not** get their own goal bind.

## Core rules

1. Extract **Goal** (one sentence) and **Tasks** from the user request before writing the plan.
2. Create the root plan with `proactive_todo_write` (`merge=false`, `goal`, `acceptance_criteria`, `items[]`).
3. Keep the initial plan short (3–7 root items); expand with `merge=true` when needed.
4. Call `proactive_todo_read` before choosing the next step and after context compression.
5. Only one root item `in_progress` at a time unless executing parallel-ready siblings.
6. After each item's work, `proactive_todo_verify(scope=item, item_id=..., criteria_results=...)`.
7. Never use built-in `todo` while this plugin is active.
8. Each `proactive_todo_verify` returns `plan_summary` (emoji progress). The standing Hermes goal is updated from the same snapshot for the judge.

## Default workflow (lead agent)

```text
1. proactive_todo_read
2. proactive_todo_write (root plan)  -> goal auto-bound
3. Loop (Hermes goal loop may continue turns until plan verify + judge done):
   a. proactive_todo_read
   b. Pick ready_items (respect depends_on)
   c. Execute or delegate_task (see skill orchestrating)
   d. proactive_todo_verify per completed item
4. proactive_todo_verify(scope=plan)
5. Brief user summary, then append `plan_summary` from the last verify response verbatim
```

## Nested sub-plans (subagents)

When a root item is large, delegate with `delegate_task` and include in the brief:

- `plan_session_id`: coordinator session id (same as lead session)
- `parent_item_id`: the root item id being decomposed
- Instruction to load `skill_view("hermes-plugin-proactive-todo:delegated-worker")`

**Lead after handoff:**

```text
proactive_todo_read -> proactive_todo_verify(scope=item, item_id=parent_item_id)
```

For deeper nesting, pass a **new** `parent_item_id` to the nested subagent.

## Item fields

Each item (at any depth) should include:

- `id` — globally unique in the plan
- `title`, `description`
- `acceptance_criteria` — verifiable checks
- `recommended_models` — advisory for delegate_task
- `depends_on` — ids of items that must be completed+passed first
- `items` — optional nested subitems

## Parallelism

Run items in parallel only when:

- Both appear in `ready_items` or `ready_subitems`
- They do not touch the same files, services, or mutable state

See skill `orchestrating` when unsure.

## Verification

`criteria_results` must list **every** acceptance criterion for the scope:

```json
[{"criterion": "exact text from plan", "met": true, "note": "how verified"}]
```

Parent items with subitems cannot verify until all descendants are `completed` and `passed`.

## Anti-patterns

- Tracking the plan only in prose
- Using built-in `todo` alongside this plugin
- Subagent calling `verify(scope=plan)`
- Lead `merge=false` on root while a subagent writes subitems under an in-flight parent
- Claiming success without `verify(scope=plan)`
