"""The run lifecycle.

brief -> specialists (in parallel) -> review -> founder approval -> final plan

At the approval step the founder can send feedback to any specialist; those
specialists redo their section, the reviewer checks again, and the run returns
to awaiting approval.
"""

import asyncio
from typing import Any

from . import agents, llm, store


def _set_status(run: dict[str, Any], status: str) -> None:
    run["status"] = status
    store.save_run(run)
    store.bus.publish(run["id"], {"type": "status", "status": status})


async def _write_section(run: dict[str, Any], section: str, system: str, prompt: str, effort: str = "medium") -> None:
    run["sections"][section] = ""
    store.bus.publish(run["id"], {"type": "section_start", "section": section})

    async def on_text(chunk: str) -> None:
        run["sections"][section] += chunk
        store.bus.publish(run["id"], {"type": "delta", "section": section, "text": chunk})

    run["sections"][section] = await llm.generate(system, prompt, on_text, effort=effort)
    store.save_run(run)
    store.bus.publish(run["id"], {"type": "section_done", "section": section, "text": run["sections"][section]})


def _founder_input(run: dict[str, Any]) -> str:
    return f"Company or working name: {run['company'] or '(not named yet)'}\n\nThe founder's idea:\n{run['idea']}"


def _team_work(run: dict[str, Any]) -> str:
    parts = [f"# Brief\n\n{run['sections']['brief']}"]
    for s in agents.SPECIALISTS:
        parts.append(run["sections"].get(s.key, ""))
    return "\n\n---\n\n".join(parts)


def _specialist_input(run: dict[str, Any], key: str) -> str:
    prompt = f"Project brief:\n\n{run['sections']['brief']}"
    feedback = run["feedback"].get(key)
    if feedback:
        prompt += (
            f"\n\nYour previous draft:\n\n{run['sections'].get(key, '')}"
            f"\n\nThe founder asked for these changes:\n{feedback}\n\nRewrite your section accordingly."
        )
    return prompt


async def _run_specialists(run: dict[str, Any], keys: list[str]) -> None:
    await asyncio.gather(
        *(
            _write_section(run, k, agents.specialist_prompt(agents.SPECIALISTS_BY_KEY[k]), _specialist_input(run, k))
            for k in keys
        )
    )


async def _review(run: dict[str, Any]) -> None:
    _set_status(run, "reviewing")
    await _write_section(run, "review", agents.REVIEWER_PROMPT, _team_work(run))
    _set_status(run, "awaiting_approval")


async def _guard(run: dict[str, Any], work) -> None:
    try:
        await work
    except Exception as e:  # surface any failure to the UI instead of leaving the run hanging
        run["error"] = str(e)
        _set_status(run, "failed")


async def start(run: dict[str, Any]) -> None:
    async def work():
        _set_status(run, "drafting_brief")
        await _write_section(run, "brief", agents.STRATEGIST_PROMPT, _founder_input(run))
        _set_status(run, "specialists_working")
        await _run_specialists(run, [s.key for s in agents.SPECIALISTS])
        await _review(run)

    await _guard(run, work())


async def revise(run: dict[str, Any], feedback: dict[str, str]) -> None:
    async def work():
        run["feedback"] = feedback
        _set_status(run, "specialists_working")
        await _run_specialists(run, list(feedback))
        run["feedback"] = {}
        await _review(run)

    await _guard(run, work())


async def approve(run: dict[str, Any]) -> None:
    async def work():
        _set_status(run, "writing_plan")
        prompt = f"{_founder_input(run)}\n\n{_team_work(run)}\n\n# Reviewer notes\n\n{run['sections']['review']}"
        await _write_section(run, "final", agents.FINAL_PLAN_PROMPT, prompt, effort="high")
        _set_status(run, "done")

    await _guard(run, work())
