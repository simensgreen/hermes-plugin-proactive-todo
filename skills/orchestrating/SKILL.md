---
name: orchestrating
description: "Use when one Hermes session leads proactive-todo work: living plan with deps, delegate_task for independent slices, verify each item, Hermes goal loop on coordinator session, replan when facts change."
metadata:
  hermes:
    tags:
      - proactive-todo
      - orchestration
      - delegation
      - parallel
      - multi-agent
    category: hermes-plugin
    version: "1.0.0"
    related_skills:
      - proactive-todo
      - delegated-worker
---

# Orchestrating (proactive-todo lead)

## Purpose

One **lead** session owns the plan, **parallelism**, **verification**, and **replanning**. Workers get self-contained `delegate_task` briefs. Execution continues via Hermes **goal loop** after root `proactive_todo_write` (no manual `/goal` required).

## When to use

- Work items have **dependencies**.
- Some items are **independent** and safe to delegate.
- You need a single place to track status and update the plan.

## Lead workflow

### 1) Stabilize context

Gather minimum facts before fixing the plan. Use read-only discovery or narrow `delegate_task` when the footprint is unknown.

### 2) Publish plan

Use `proactive_todo_write` (root, `merge=false`) with goal, plan-level `acceptance_criteria`, and 3–7 items with `depends_on` where needed. This **binds** the Hermes standing goal for the session.

### 3) Delegate

- `delegate_task` with full `goal` + `context` (paths, DoD, constraints) — workers do not see lead chat.
- One slice per delegation for unrelated work.
- In brief: `plan_session_id`, `parent_item_id`, load `hermes-plugin-proactive-todo:delegated-worker`.
- **Serialize** tasks that share files, migrations, or lockfiles.

### 4) Track status

- `proactive_todo_read` before each next step.
- Map delegation results to plan item ids; `proactive_todo_verify(scope=item)` when a slice is done.

### 5) Verify before done

- Item-level verify with evidence and `criteria_results`.
- Plan-level `proactive_todo_verify(scope=plan)` only when all items are complete — this also marks the Hermes goal done.

### 6) Replan

Revise with `proactive_todo_write(merge=true)` when requirements or verification fail. A new root plan (`merge=false`) replaces the plan and re-binds the goal.

### 7) Integrate

Merge parallel outcomes; run project-wide checks after shared-surface edits.

## Parallelism

- **Parallelize** disjoint paths when both ids are in `ready_items` and surfaces do not conflict.
- **Serialize** shared files or serial release steps.

## Anti-patterns

- Merging unrelated work into one `delegate_task`
- Worker calling `verify(scope=plan)`
- Telling the user the task is done before plan verify returns `ok: true`
