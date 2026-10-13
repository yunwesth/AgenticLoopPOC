"""Audit trail: JSONL persistence plus the live trace text shown in the chat."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Dict, List

AUDIT_FILE = os.environ.get("AUDIT_FILE", "/data/audit.jsonl")
_lock = threading.Lock()

TRACE_HEAD = "> **Agent loop**"
TRACE_END = "\n\n---\n\n"
_TRACE_RE = re.compile(r"(?s)^> \*\*Agent loop\*\*.*?\n\n---\n\n")


def strip_trace(text: str) -> str:
    """Open WebUI sends earlier assistant turns back to us; the model must not see our trace."""
    return _TRACE_RE.sub("", text, count=1)


def write_audit(rid: str, event: Dict) -> None:
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "request": rid, **event}
    try:
        with _lock, open(AUDIT_FILE, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except OSError:
        pass  # auditing must never break an answer


def read_audit(limit: int = 100) -> List[Dict]:
    try:
        with open(AUDIT_FILE) as f:
            lines = f.readlines()[-limit:]
    except OSError:
        return []
    return [json.loads(x) for x in lines if x.strip()]


def format_event(e: Dict) -> str:
    t, step = e["type"], e.get("step")
    if t == "model_call":
        return f"> - `step {step}` asking the model ({e['messages']} messages, tools: calculator)"
    if t == "model_reply":
        if e["tool_calls"]:
            c = e["tool_calls"][0]
            return f"> - `step {step}` model chose tool `{c.get('name')}({json.dumps(c.get('arguments'))})` ({e['ms']} ms)"
        return f"> - `step {step}` model gave a final answer, no tool call ({e['ms']} ms)"
    if t == "tool_result":
        return f"> - `step {step}` tool `{e['tool']}` returned `{e['result']}` ({e['ms']} ms)"
    if t == "cap":
        return f"> - stopped: reached the {step}-step cap"
    return ""
