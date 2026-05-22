# hermes-plugin-proactive-todo

Proactive execution plans for Hermes Agent: nested items, acceptance criteria, dependencies, model hints, verification, and **Hermes `/goal` loop** binding (no separate gateway continuation).

Replaces the built-in `todo` tool when enabled.

## Tools

| Tool | Purpose |
|------|---------|
| `proactive_todo_write` | Create/update root plan or sub-plan under `parent_item_id` |
| `proactive_todo_read` | Read plan + `ready_items`, `ready_subitems`, blockers |
| `proactive_todo_verify` | Verify item or full plan against criteria |

## Bundled skills (opt-in)

After the plugin loads, tools are available immediately. Bundled skills are **opt-in**: they are **not** listed in the default global skills index / `<available_skills>` in the system prompt ([Bundle skills](https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin#bundle-skills); same as `hermes-plugin-searxng`). Tool descriptions instruct `skill_view` before use.

```text
skill_view("hermes-plugin-proactive-todo:proactive-todo")
```

(`hermes-plugin-proactive-todo` is the plugin `name` in `plugin.yaml`; folder names under `skills/`.)

| Skill | Role |
|-------|------|
| `proactive-todo` | Lead agent: plan tools + goal loop |
| `orchestrating` | Lead: delegation, parallelism, verify gates |
| `delegated-worker` | `delegate_task` worker: sub-plans and handoff |

## Goal-driven execution

On **root** `proactive_todo_write` (`merge=false`, no `parent_item_id`), the plugin calls Hermes `GoalManager` for the coordinator `session_id`. The standing goal instructs the agent to use plan tools until `proactive_todo_verify(scope=plan)` succeeds.

On successful **plan** verify, the plugin syncs a final digest into the goal and calls `GoalManager.mark_done()`.

**Two channels for plan progress:**

| Channel | Content |
|---------|---------|
| Standing goal (judge) | Full `PLAN_PROGRESS` via `sync_goal_progress` on every write and verify |
| Tool JSON to the model | `scope=item`: compact `progress`; `scope=plan`: `completion_note` one-liner (no PLAN_PROGRESS by default) |

After `scope=plan` succeeds, the user-facing reply is **deliverable only** — no plan, verify, or `completion_note` in chat.

You do **not** need to type `/goal` manually when the plugin is enabled and you create a root plan.

Configure Hermes goals in `~/.hermes/config.yaml`:

```yaml
goals:
  max_turns: 20

auxiliary:
  goal_judge:
    provider: openrouter
    model: google/gemini-3-flash-preview
```

Requires `hermes_cli.goals` (Hermes Agent) in the same Python environment as the plugin.

## Install

1. Copy or clone this directory to `$HERMES_HOME/plugins/hermes-plugin-proactive-todo`.
2. Enable the plugin:

```bash
hermes plugins enable hermes-plugin-proactive-todo
```

3. Enable proactive todo toolset and disable built-in `todo` (avoid duplicate tools):

```bash
hermes tools enable proactive_todo
hermes tools disable todo
```

Per platform: in profile `platform_toolsets`, enable `proactive_todo` and disable `todo` on **each** channel you use (CLI, messengers, etc.).

4. Restart Hermes / gateway if running.

5. Verify:

```bash
hermes plugins list
hermes tools list | grep proactive_todo
```

Plans are stored at `$HERMES_HOME/proactive-todos/{session_id}.json`.

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `PROACTIVE_TODO_MAX_DEPTH` | `5` | Max nesting depth for subitems |

## Subagent delegation

Include in `delegate_task` brief:

- `plan_session_id` — lead/coordinator session id
- `parent_item_id` — item to decompose
- Load skill `hermes-plugin-proactive-todo:delegated-worker`

Subagents write sub-plans with `proactive_todo_write(parent_item_id=...)`. They must not call `proactive_todo_verify(scope=plan)`. Goal binding applies only to the **coordinator** session.

## Limitations

- The goal judge evaluates the **last assistant response**, not the plan JSON file — the standing goal text requires explicit plan verification in the workflow.
- Subagent sessions do not receive goal bind.
- Plugin does not patch `judge_goal()` in Hermes core.

## License

MIT (match your Hermes deployment).
