"""Unit tests for the Claude session module — no Slack, no live SDK subprocess.

The turn-grouping logic (`turns`) is pure w.r.t. the SDK client: it consumes any
async iterable of SDK message objects, so it can be exercised with hand-built
messages. This is the point of keeping the Claude concerns in their own module.

Run:  .venv/Scripts/python.exe -m tests.test_claude_session
(or under pytest if an async plugin is available).
"""

from __future__ import annotations

import asyncio

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

from slack_agent.claude_session import build_options, turns


def _assistant(*texts: str) -> AssistantMessage:
    return AssistantMessage(content=[TextBlock(text=t) for t in texts], model="test")


def _result() -> ResultMessage:
    return ResultMessage(
        subtype="success",
        duration_ms=1,
        duration_api_ms=1,
        is_error=False,
        num_turns=1,
        session_id="test",
    )


async def _feed(items):
    for x in items:
        yield x


async def _collect(items) -> list[str]:
    return [t async for t in turns(_feed(items))]


async def check_multiblock_joined() -> None:
    assert await _collect([_assistant("hello"), _assistant("world"), _result()]) == [
        "hello\n\nworld"
    ]


async def check_empty_turn_skipped() -> None:
    # A ResultMessage with no assistant text yields nothing (silent/tool-only turn).
    assert await _collect([_result(), _result()]) == []


async def check_proactive_turn_after_empty() -> None:
    # An empty turn followed by a real (e.g. proactive) turn: only the real one.
    seq = [_result(), _assistant("proactive fact"), _result()]
    assert await _collect(seq) == ["proactive fact"]


async def check_whitespace_blocks_ignored() -> None:
    assert await _collect([_assistant("  ", "\n"), _assistant("real"), _result()]) == [
        "real"
    ]


def check_build_options_shape() -> None:
    opts = build_options(can_use_tool=lambda *a, **k: None)
    assert opts.permission_mode == "default"
    assert opts.can_use_tool is not None
    assert opts.cwd  # resolved to a path


async def _main() -> None:
    await check_multiblock_joined()
    await check_empty_turn_skipped()
    await check_proactive_turn_after_empty()
    await check_whitespace_blocks_ignored()
    check_build_options_shape()
    print("ALL_TESTS_OK")


if __name__ == "__main__":
    asyncio.run(_main())
