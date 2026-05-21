---
name: delegated-worker
description: "Use when Hermes runs as a delegate_task worker for hermes-plugin-proactive-todo: parse a self-contained brief, write a sub-plan under parent_item_id, execute subitems, verify each, and return a structured handoff. Do not bind or clear coordinator goals."
metadata:
  hermes:
    tags:
      - proactive-todo
      - delegation
      - worker
      - subagent
    category: hermes-plugin
    version: "1.0.0"
    related_skills:
      - proactive-todo
      - orchestrating
---

# Delegated worker (proactive-todo)

## When to use

- You are executing **`delegate_task`** for a slice of a larger proactive todo plan.
- The brief includes **`plan_session_id`** (coordinator session) and **`parent_item_id`**.

The lead session owns the Hermes goal loop; you own **local tactics** and the sub-plan.

## Operating rules

### 1) Parse the brief

Extract:

- **Goal** and **constraints** (read-only phases, forbidden paths, risk limits)
- **Definition of done** (commands, artifacts, behaviors)
- Missing inputs from other slices — report immediately

### 2) Sub-plan

```text
1. proactive_todo_read(plan_session_id, focus_item_id=parent_item_id)
2. proactive_todo_write(plan_session_id, parent_item_id, merge=false, items=[...])
3. Loop: work ready_subitems; proactive_todo_verify(scope=item) per subitem
4. Handoff to lead — do NOT call proactive_todo_verify(scope=plan)
```

Use only `proactive_todo_*` tools, not built-in `todo`.

### 3) Execute

- Small, verifiable increments; run checks from the brief.
- Stay in scope; escalate if the fix needs broader changes than the slice.

### 4) Hand back

```text
## Handoff
- Done: ...
- Evidence: commands + outcomes / paths
- Decisions: ...
- Risks or follow-ups: ...
- Blockers (if any): what the lead must provide
```

## Escalation

Escalate before large refactors when:

- Requirements conflict or the brief is incomplete.
- Security, data loss, or migration impact outside the slice.
- Parallel work would touch the same files as another slice.

## Nested delegation

If the slice needs nested `delegate_task`, each child brief must be **self-contained** (no "see parent chat"). Include `plan_session_id` and the appropriate `parent_item_id` for nested sub-plans.
