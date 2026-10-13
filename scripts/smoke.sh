#!/usr/bin/env bash
set -euo pipefail
Q="${1:-What is 17 * 23 + 4?}"
OUT=$(curl -fs localhost:8000/v1/chat/completions -H 'content-type: application/json' \
  -d "{\"model\":\"calc-agent\",\"messages\":[{\"role\":\"user\",\"content\":\"$Q\"}]}")
echo "$OUT" | python3 -c "import sys,json;print(json.load(sys.stdin)['choices'][0]['message']['content'])"
echo "$OUT" | grep -q 395 && echo "PASS: 395 in reply" || { echo "FAIL"; exit 1; }
docker logs agentloop-agent 2>&1 | grep -c "tool=calculator" | xargs echo "calculator calls in log:"
