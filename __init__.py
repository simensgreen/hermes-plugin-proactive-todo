"""Proactive todo plugin — registration."""

from pathlib import Path

from . import schemas, tools


def _register_bundled_skills(ctx) -> None:
    skills_dir = Path(__file__).parent / "skills"
    if not skills_dir.is_dir():
        return
    for child in sorted(skills_dir.iterdir()):
        skill_md = child / "SKILL.md"
        if child.is_dir() and skill_md.exists():
            ctx.register_skill(child.name, skill_md)


def register(ctx):
    ctx.register_tool(
        name="proactive_todo_write",
        schema=schemas.PROACTIVE_TODO_WRITE,
        handler=tools.proactive_todo_write,
        toolset="proactive_todo",
    )
    ctx.register_tool(
        name="proactive_todo_read",
        schema=schemas.PROACTIVE_TODO_READ,
        handler=tools.proactive_todo_read,
        toolset="proactive_todo",
    )
    ctx.register_tool(
        name="proactive_todo_verify",
        schema=schemas.PROACTIVE_TODO_VERIFY,
        handler=tools.proactive_todo_verify,
        toolset="proactive_todo",
    )
    _register_bundled_skills(ctx)
