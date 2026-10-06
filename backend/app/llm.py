"""Thin wrapper around Claude: streams text out and falls back to canned text in demo mode."""

import asyncio
import os
from typing import Awaitable, Callable

import anthropic

MODEL = os.getenv("VENTUREDESK_MODEL", "claude-opus-5-5")
DEMO_MODE = os.getenv("VENTUREDESK_DEMO", "0") == "1"

OnText = Callable[[str], Awaitable[None]]

_client: anthropic.AsyncAnthropic | None = None


class LLMError(RuntimeError):
    pass


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


async def generate(system: str, prompt: str, on_text: OnText, effort: str = "medium") -> str:
    """Stream a single response, calling on_text for each chunk. Returns the full text."""
    if DEMO_MODE:
        return await _demo_generate(system, on_text)

    try:
        async with _get_client().beta.messages.stream(
            model=MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
        ) as stream:
            async for chunk in stream.text_stream:
                await on_text(chunk)
            message = await stream.get_final_message()
    except anthropic.AuthenticationError as e:
        raise LLMError("Claude rejected the credentials. Set ANTHROPIC_API_KEY or run `ant auth login`.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Rate limited by the Claude API. Try again in a minute.") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error ({e.status_code}): {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Couldn't reach the Claude API. Check your internet connection.") from e

    if message.stop_reason == "refusal":
        raise LLMError("Claude declined this request.")

    return "".join(b.text for b in message.content if b.type == "text")


async def _demo_generate(system: str, on_text: OnText) -> str:
    role = system.split(" at VentureDesk")[0].replace("You are the ", "").strip()
    text = (
        f"## {role} (demo)\n\n"
        "This is placeholder output because `VENTUREDESK_DEMO=1` is set.\n\n"
        "- Point one with a concrete next step\n"
        "- Point two with a number: **$49/month**\n"
        "- Point three: talk to 10 customers this week\n\n"
        "**Open questions:** Who pays? How soon do they need it?\n"
    )
    out = []
    for word in text.split(" "):
        piece = word + " "
        out.append(piece)
        await on_text(piece)
        await asyncio.sleep(0.03)
    return "".join(out)
