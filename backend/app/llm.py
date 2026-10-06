"""Thin wrapper around Claude: streams text out, tracks usage, and falls back to canned text in demo mode."""

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import anthropic

MODEL = os.getenv("VENTUREDESK_MODEL", "claude-opus-5-5")
DEMO_MODE = os.getenv("VENTUREDESK_DEMO", "0") == "1"

# USD per million tokens: input, output, cache write (5 min), cache read. Used for cost estimates only.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 5.00, 0.20),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
}
WEB_SEARCH_USD = 0.01  # $10 per 1,000 searches

WEB_SEARCH_TOOL = {"type": "web_search_20260209", "name": "web_search", "max_uses": 6}
MAX_CONTINUATIONS = 4

OnText = Callable[[str], Awaitable[None]]

_client: anthropic.AsyncAnthropic | None = None


class LLMError(RuntimeError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    web_searches: int = 0
    model: str = MODEL

    def add(self, u: Any) -> None:
        self.input_tokens += u.input_tokens or 0
        self.output_tokens += u.output_tokens or 0
        self.cache_write_tokens += getattr(u, "cache_creation_input_tokens", 0) or 0
        self.cache_read_tokens += getattr(u, "cache_read_input_tokens", 0) or 0
        server = getattr(u, "server_tool_use", None)
        if server is not None:
            self.web_searches += getattr(server, "web_search_requests", 0) or 0

    def cost_usd(self) -> float | None:
        price = PRICES.get(self.model)
        if price is None:
            return None
        inp, out, cw, cr = price
        tokens = (
            self.input_tokens * inp
            + self.output_tokens * out
            + self.cache_write_tokens * cw
            + self.cache_read_tokens * cr
        ) / 1_000_000
        return round(tokens + self.web_searches * WEB_SEARCH_USD, 4)


@dataclass
class Result:
    text: str
    usage: Usage = field(default_factory=Usage)


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def _system_blocks(role_prompt: str, shared_context: str) -> list[dict[str, Any]]:
    """Shared business context goes first and is cached, so every agent in a run reuses it."""
    blocks = []
    if shared_context:
        blocks.append({"type": "text", "text": shared_context, "cache_control": {"type": "ephemeral"}})
    blocks.append({"type": "text", "text": role_prompt})
    return blocks


async def generate(
    role_prompt: str,
    prompt: str,
    on_text: OnText,
    *,
    shared_context: str = "",
    effort: str = "medium",
    web_search: bool = False,
) -> Result:
    """Stream one agent's response, calling on_text for each chunk."""
    if DEMO_MODE:
        return await _demo_generate(role_prompt, on_text)

    usage = Usage()
    messages: list[dict[str, Any]] = [{"role": "user", "content": prompt}]
    extra: dict[str, Any] = {"tools": [WEB_SEARCH_TOOL]} if web_search else {}
    text_parts: list[str] = []

    try:
        for _ in range(MAX_CONTINUATIONS):
            async with _get_client().beta.messages.stream(
                model=MODEL,
                max_tokens=16000,
                system=_system_blocks(role_prompt, shared_context),
                messages=messages,
                output_config={"effort": effort},
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default"},
                **extra,
            ) as stream:
                async for chunk in stream.text_stream:
                    await on_text(chunk)
                message = await stream.get_final_message()

            usage.add(message.usage)
            usage.model = message.model
            text_parts.extend(b.text for b in message.content if b.type == "text")

            if message.stop_reason != "pause_turn":
                break
            # Server-side tool loop hit its limit; resend so it resumes where it stopped.
            messages = [messages[0], {"role": "assistant", "content": message.content}]
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

    return Result(text="".join(text_parts), usage=usage)


async def _demo_generate(role_prompt: str, on_text: OnText) -> Result:
    role = role_prompt.split(" at VentureDesk")[0].replace("You are the ", "").strip()
    text = (
        f"## {role} (demo)\n\n"
        "This is placeholder output because `VENTUREDESK_DEMO=1` is set.\n\n"
        "- Point one with a concrete next step [Onboarding SOP]\n"
        "- Point two with a number: **$49/month**\n"
        "- Point three: talk to 10 customers this week\n\n"
        "**Open questions:** Who pays? How soon do they need it?\n"
    )
    out = []
    for word in text.split(" "):
        piece = word + " "
        out.append(piece)
        await on_text(piece)
        await asyncio.sleep(0.02)
    words = len(out)
    return Result(text="".join(out), usage=Usage(input_tokens=words * 20, output_tokens=words * 2, model="demo"))
