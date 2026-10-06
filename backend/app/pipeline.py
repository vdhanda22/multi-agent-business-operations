"""The run lifecycle (the central command layer).

brief -> research -> specialists (in parallel) -> review -> founder approval -> final plan

Every agent receives the same business profile and knowledge library as a cached
shared context. At the approval step the founder can send feedback to any specialist;
those specialists redo their section, the reviewer checks again, and the run returns
to awaiting approval. Every step is written to the activity log.
"""

import asyncio
import time
from html import escape
from typing import Any

from . import agents, llm, store

AGENT_NAMES = {
    "brief": "Lead Strategist",
    "research": "Research Lead",
    "review": "Reviewer",
    "final": "Lead Strategist",
    **{s.key: s.title for s in agents.SPECIALISTS},
}


def build_shared_context(business_id: str) -> str:
    """Render the business profile and its library as the context every agent shares."""
    biz = store.get_business(business_id)
    if not biz:
        return ""
    parts = [
        "<business_profile>",
        f"Name: {biz['name']}",
        f"Description: {biz['description'] or '(none given)'}",
        "</business_profile>",
    ]
    docs = store.list_documents(business_id, with_content=True)
    if docs:
        parts.append("<knowledge_library>")
        for d in docs:
            label = "SOP" if d["kind"] == "sop" else "Knowledge"
            parts.append(f'<document type="{label}" title="{escape(d["title"])}">\n{d["content"]}\n</document>')
        parts.append("</knowledge_library>")
    return "\n".join(parts)


def _set_status(run: dict[str, Any], status: str) -> None:
    run["status"] = status
    store.save_run(run)
    store.bus.publish(run["id"], {"type": "status", "status": status})
    store.log_activity(run["id"], "Command layer", "status", status.replace("_", " "))


async def _write_section(
    run: dict[str, Any], section: str, system: str, prompt: str, *, effort: str = "medium", web_search: bool = False
) -> None:
    agent = AGENT_NAMES[section]
    run["sections"][section] = ""
    store.bus.publish(run["id"], {"type": "section_start", "section": section})
    store.log_activity(run["id"], agent, "started", "with web search" if web_search else "")
    started = time.monotonic()

    async def on_text(chunk: str) -> None:
        run["sections"][section] += chunk
        store.bus.publish(run["id"], {"type": "delta", "section": section, "text": chunk})

    try:
        result = await llm.generate(
            system, prompt, on_text, shared_context=run.get("_context", ""), effort=effort, web_search=web_search
        )
    except Exception as e:
        store.log_activity(run["id"], agent, "failed", str(e), {"duration_ms": int((time.monotonic() - started) * 1000)})
        raise

    run["sections"][section] = result.text
    store.save_run(run)
    store.bus.publish(run["id"], {"type": "section_done", "section": section, "text": result.text})
    u = result.usage
    store.log_activity(
        run["id"],
        agent,
        "finished",
        f"{len(result.text.split())} words",
        {
            "duration_ms": int((time.monotonic() - started) * 1000),
            "model": u.model,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "cache_read_tokens": u.cache_read_tokens,
            "cache_write_tokens": u.cache_write_tokens,
            "web_searches": u.web_searches,
            "cost_usd": u.cost_usd(),
        },
    )


def _founder_input(run: dict[str, Any]) -> str:
    return f"Business: {run['company'] or '(not named yet)'}\n\nThe founder's request:\n{run['idea']}"


def _brief_and_research(run: dict[str, Any]) -> str:
    return f"# Project brief\n\n{run['sections']['brief']}\n\n# Market research\n\n{run['sections'].get('research', '')}"


def _team_work(run: dict[str, Any]) -> str:
    parts = [_brief_and_research(run)]
    for s in agents.SPECIALISTS:
        parts.append(run["sections"].get(s.key, ""))
    return "\n\n---\n\n".join(parts)


def _specialist_input(run: dict[str, Any], key: str) -> str:
    prompt = _brief_and_research(run)
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
    run["_context"] = build_shared_context(run["business_id"]) if run.get("business_id") else ""
    try:
        await work
    except Exception as e:  # surface any failure to the UI instead of leaving the run hanging
        run["error"] = str(e)
        _set_status(run, "failed")
    finally:
        run.pop("_context", None)


async def start(run: dict[str, Any]) -> None:
    async def work():
        docs = store.list_documents(run["business_id"]) if run.get("business_id") else []
        store.log_activity(run["id"], "Command layer", "context", f"Loaded business profile and {len(docs)} library documents")
        _set_status(run, "drafting_brief")
        await _write_section(run, "brief", agents.STRATEGIST_PROMPT, _founder_input(run))
        _set_status(run, "researching")
        await _write_section(run, "research", agents.RESEARCH_PROMPT, run["sections"]["brief"], web_search=True)
        _set_status(run, "specialists_working")
        await _run_specialists(run, [s.key for s in agents.SPECIALISTS])
        await _review(run)

    await _guard(run, work())


async def revise(run: dict[str, Any], feedback: dict[str, str]) -> None:
    async def work():
        for key, text in feedback.items():
            store.log_activity(run["id"], "Founder", "feedback", f"To {AGENT_NAMES[key]}: {text}")
        run["feedback"] = feedback
        _set_status(run, "specialists_working")
        await _run_specialists(run, list(feedback))
        run["feedback"] = {}
        await _review(run)

    await _guard(run, work())


async def approve(run: dict[str, Any]) -> None:
    async def work():
        store.log_activity(run["id"], "Founder", "approved", "Approved the team's work")
        _set_status(run, "writing_plan")
        prompt = f"{_founder_input(run)}\n\n{_team_work(run)}\n\n# Reviewer notes\n\n{run['sections']['review']}"
        await _write_section(run, "final", agents.FINAL_PLAN_PROMPT, prompt, effort="high")
        _set_status(run, "done")

    await _guard(run, work())
