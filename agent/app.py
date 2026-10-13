"""OpenAI-compatible wrapper so Open WebUI can talk to the loop."""
from __future__ import annotations

import json
import queue
import threading
import logging
import os
import time
import uuid

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse, StreamingResponse

from loop import run_agent
from trace import TRACE_END, TRACE_HEAD, format_event, read_audit, strip_trace, write_audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11435")
MODEL = os.environ.get("MODEL", "qwen3:4b")
NUM_CTX = int(os.environ.get("NUM_CTX", "4096"))
AGENT_NAME = "calc-agent"

app = FastAPI()


def ollama_chat(messages, tools):
    body = {"model": MODEL, "messages": messages, "tools": tools, "stream": False,
            "think": False, "options": {"num_ctx": NUM_CTX}}
    r = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=120)
    r.raise_for_status()
    return r.json()["message"]


@app.get("/healthz")
def healthz():
    return {"ok": True, "model": MODEL}


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": AGENT_NAME, "object": "model", "owned_by": "local"}]}


@app.get("/audit")
def audit(limit: int = 100):
    return read_audit(limit)


def _clean_history(messages):
    out = []
    for m in messages:
        if m.get("role") not in ("user", "assistant"):
            continue
        content = m.get("content")
        if isinstance(content, str):
            content = strip_trace(content)
        out.append({"role": m["role"], "content": content})
    return out


@app.post("/v1/chat/completions")
def completions(req: dict):
    history = _clean_history(req.get("messages", []))
    rid = uuid.uuid4().hex[:8]
    cid, created = f"chatcmpl-{rid}", int(time.time())
    write_audit(rid, {"type": "request", "model": MODEL, "stream": bool(req.get("stream")),
                      "question": history[-1]["content"] if history else ""})

    def chunk(delta, finish=None):
        c = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": AGENT_NAME,
             "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
        return f"data: {json.dumps(c)}\n\n"

    if not req.get("stream"):
        try:
            text = run_agent(history, ollama_chat, emit=lambda e: write_audit(rid, e))
        except Exception as exc:
            logging.exception("agent failed")
            write_audit(rid, {"type": "error", "error": str(exc)})
            text = f"Agent error: {exc}"
        return JSONResponse({"id": cid, "object": "chat.completion", "created": created, "model": AGENT_NAME,
                             "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                          "finish_reason": "stop"}]})

    q: "queue.Queue" = queue.Queue()

    def worker():
        def emit(e):
            write_audit(rid, e)
            q.put(("event", e))
        try:
            q.put(("answer", run_agent(history, ollama_chat, emit=emit)))
        except Exception as exc:
            logging.exception("agent failed")
            write_audit(rid, {"type": "error", "error": str(exc)})
            q.put(("answer", f"Agent error: {exc}"))

    threading.Thread(target=worker, daemon=True).start()

    def sse():
        yield chunk({"role": "assistant", "content": f"{TRACE_HEAD} · request `{rid}` · model `{MODEL}`\n>\n"})
        while True:
            kind, val = q.get()
            if kind == "event":
                line = format_event(val)
                if line:
                    yield chunk({"content": line + "\n"})
            else:
                yield chunk({"content": TRACE_END + val})
                break
        yield chunk({}, "stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
