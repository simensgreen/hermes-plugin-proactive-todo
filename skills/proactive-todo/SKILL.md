---
name: proactive-todo
description: "Use when hermes-plugin-proactive-todo is enabled and the user request needs a structured multi-step outcome: multiple deliverables, gather-and-synthesize, multi-file/repo work, delegation, or unclear scope—any subject. Load via skill_view before web/search/terminal. When unsure, use this skill."
metadata:
  hermes:
    tags:
      - proactive-todo
      - execution
      - verification
      - subagents
      - goals
    category: hermes-plugin
    version: "2.1.0"
    related_skills:
      - orchestrating
      - delegated-worker
---

# Proactive Todo (plugin)

Plugin skills are **opt-in** (`skill_view("hermes-plugin-proactive-todo:proactive-todo")`); not in the global skills index. Tool schemas repeat the same requirement.

Use `proactive_todo_write`, `proactive_todo_read`, and `proactive_todo_verify` for plan work.

## Trivial vs non-trivial (any topic)

Criteria depend on **structure of the request**, not subject.

**Non-trivial** if **any** apply:

| Signal | Meaning |
|--------|---------|
| 2+ deliverables | User expects multiple distinct outputs in one message |
| Multi-part question | Several sub-questions or dimensions |
| Gather + synthesize | External info → structured answer |
| Multi-step execution | More than 1–2 tool actions to finish honestly |
| Repo / multi-file / infra | Non-trivial code, config, or service work |
| Delegation | `delegate_task` or parallel independent slices |
| Completion-oriented | Finished outcome, not a chat reply |
| Unclear scope | Cannot list steps until decomposed |

**Quick test:** need ≥3 plan items or ≥2 tool rounds → non-trivial.

**Trivial** only if **all:** one outcome; one (or zero) tool call; no synthesis; no implied deliverable list.

**When unsure → non-trivial.**

**Anti-patterns:** one broad search + long prose instead of a plan; ask user to clarify when the brief already lists multiple asks; narrate plan checklist in user-visible messages.

## First turn (mandatory on non-trivial)

1. `skill_view("hermes-plugin-proactive-todo:proactive-todo")` — follow this file.
2. `proactive_todo_write` root plan (`merge=false`, `goal`, `acceptance_criteria`, `items[]`) **before** web search, browser, terminal, or `delegate_task`.
3. Do not ask the user to confirm planning or restate the brief.

## Goal loop (Hermes core)

After root `proactive_todo_write` (`merge=false`), the plugin binds a standing goal. Hermes continues until the judge accepts completion or the turn budget is exhausted.

- Do **not** run `/goal` manually for coordinator work.
- Do **not** tell the user the task is complete until `proactive_todo_verify(scope=plan)` returns `ok: true`.
- Subagents with `plan_session_id` do **not** get their own goal bind.

## User-visible output

- **No** per-item verify announcements to the user.
- **No** re-posting the plan tree or sub-item checklist between tool rounds.
- At most one short user-visible message if blocked; otherwise **one** substantive reply when done.
- Batch multiple `proactive_todo_verify(scope=item)` in one turn **without** user-visible prose between tool calls.
- Append `plan_summary` **only** from the last `verify(scope=plan)` into the final reply, verbatim once.
- Use `proactive_todo_read` when unsure of next step — do not rely on old verify tool blobs.

## Core rules

1. Extract **Goal** (one sentence) and **Tasks** before writing the plan.
2. Root plan: 3–7 items; expand with `merge=true` when needed.
3. `proactive_todo_read` before each next step and after context compression.
4. One root item `in_progress` at a time unless parallel-ready siblings.
5. After each item's work: `proactive_todo_verify(scope=item, ...)` in the same turn when possible.
6. `scope=item` verify returns compact `progress` only; full PLAN_PROGRESS is in the standing goal for the judge.

## Default workflow (lead)

```text
1. skill_view(proactive-todo) on non-trivial turn 1
2. proactive_todo_read (optional if no plan yet)
3. proactive_todo_write (root) -> goal auto-bound
4. Loop:
   a. proactive_todo_read
   b. ready_items / execute / delegate (see orchestrating)
   c. proactive_todo_verify(scope=item) — no user-visible progress spam
5. proactive_todo_verify(scope=plan)
6. One final user-visible reply + plan_summary from step 5
```

## Verification

`criteria_results` must list **every** acceptance criterion for the scope:

```json
[{"criterion": "exact text from plan", "met": true, "note": "checkable evidence"}]
```

Use `met: false` when evidence does not satisfy the criterion. Evidence must be checkable (paths, commands, URLs, quotes) — not vague prose.

Parent items with subitems cannot verify until all descendants are `completed` and `passed`.

## Nested sub-plans (subagents)

`delegate_task` brief must include:

- `plan_session_id` — coordinator session id
- `parent_item_id` — item to decompose
- `skill_view("hermes-plugin-proactive-todo:delegated-worker")`

Lead after handoff: `proactive_todo_read` → `proactive_todo_verify(scope=item, item_id=parent_item_id)`.

## Anti-patterns

- Tracking the plan only in prose
- Subagent calling `verify(scope=plan)`
- Lead `merge=false` on root while a subagent writes subitems under an in-flight parent
- Claiming success without `verify(scope=plan)`
- Echoing intermediate `plan_summary` from item verify to the user
