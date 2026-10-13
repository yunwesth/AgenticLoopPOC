"""The agent loop. `chat` is injected so tests can script the model; `emit` receives audit events."""
from __future__ import annotations

import logging
import re
import time
from typing import Callable, Dict, List, Optional

from tools import SCHEMAS, run_tool

log = logging.getLogger("agent")

MAX_STEPS = 5
SYSTEM_PROMPT = (
    "You are a helpful assistant. For any arithmetic, always call the calculator tool "
    "instead of computing in your head, then state the result in a short sentence."
)

_THINK = re.compile(r"(?s)^.*?</think>|<think>.*$")


def clean(text: str) -> str:
    """Drop Qwen reasoning that leaks into content (an unclosed <think> drops the rest)."""
    return _THINK.sub("", text).strip() if ("</think>" in text or "<think>" in text) else text.strip()


Chat = Callable[[List[Dict], List[Dict]], Dict]
Emit = Callable[[Dict], None]


def _ms(t0: float) -> int:
    return int((time.perf_counter() - t0) * 1000)


def run_agent(history: List[Dict], chat: Chat, max_steps: int = MAX_STEPS, emit: Optional[Emit] = None) -> str:
    emit = emit or (lambda e: None)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(history)
    for step in range(1, max_steps + 1):
        emit({"type": "model_call", "step": step, "messages": len(messages)})
        t0 = time.perf_counter()
        reply = chat(messages, SCHEMAS)
        calls = reply.get("tool_calls") or []
        content = clean(reply.get("content", ""))
        emit({"type": "model_reply", "step": step, "ms": _ms(t0), "content": content,
              "tool_calls": [c.get("function", {}) for c in calls]})
        if not calls:
            emit({"type": "final", "step": step, "content": content})
            return content
        messages.append(reply)
        for call in calls:
            fn = call.get("function", {})
            name, args = fn.get("name", ""), fn.get("arguments", {})
            t1 = time.perf_counter()
            result = run_tool(name, args)
            log.info("step=%d tool=%s args=%s result=%s", step, name, args, result)
            emit({"type": "tool_result", "step": step, "tool": name, "args": args, "result": result, "ms": _ms(t1)})
            messages.append({"role": "tool", "tool_name": name, "content": result})
    emit({"type": "cap", "step": max_steps})
    return f"Stopped after {max_steps} steps without a final answer."
