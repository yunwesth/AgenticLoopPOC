#!/usr/bin/env bash
# Starts a dedicated Ollama on :11435 reachable from Docker, and pulls the model.
# Leaves any existing Ollama on :11434 alone.
set -euo pipefail
MODEL="${MODEL:-qwen3:4b}"
PORT=11435
if curl -fs "http://127.0.0.1:$PORT/api/version" >/dev/null; then
  echo "ollama already up on :$PORT"
else
  OLLAMA_HOST="0.0.0.0:$PORT" OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_KEEP_ALIVE=5m \
    nohup ollama serve >/tmp/ollama-agentloop.log 2>&1 &
  for _ in $(seq 1 30); do curl -fs "http://127.0.0.1:$PORT/api/version" >/dev/null && break; sleep 1; done
fi
OLLAMA_HOST="127.0.0.1:$PORT" ollama pull "$MODEL"
echo "ready: $MODEL on :$PORT"
