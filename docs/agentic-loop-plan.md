# Plan: Local Agentic Loop (IaC + Open WebUI + Qwen + Calculator Tool)

Status: plan only, nothing built yet.
Diagram: published as an artifact, "Local Agent Loop" (see the link in the session).

## 1. Goal

A small agent you can chat with in a browser. It runs entirely on this MacBook. When you ask a maths question, the model decides to call a `calculator` tool, gets the result back, and answers in words. The whole stack is created from code and can be torn down and rebuilt with one command.

Four requirements and where they land:

| # | Requirement | Choice |
|---|---|---|
| 1 | Infrastructure as code, includes Docker | Terraform (`kreuzwerker/docker` provider) creates the network, volumes, images and containers. Colima is the Docker runtime. |
| 2 | Open-source web | Open WebUI in Docker as the chat front end |
| 3 | Local model, small memory footprint | Ollama on the Mac host running `qwen3:4b` (about 2.6 GB at Q4) |
| 4 | Tool call, one calculator | A small `agent` container that owns the loop and a safe `calculator` function |

## 2. Machine facts (checked 2026-10-12)

- Apple M5 Pro, 24 GB unified memory
- `docker` 29.5.2, `colima` (profile `default`, running, VM allocated **20 GiB**, 12 CPUs), `ollama` all installed via Homebrew
- `terraform` / `tofu` not installed
- `qwen3:14b` (9.3 GB) is already pulled. It is too large for this goal, so use a smaller tag instead.

## 3. Architecture

```
Browser :3000
   |
Open WebUI (container)  --OpenAI API-->  agent (container, :8000)  --/api/chat-->  Ollama (macOS host, :11434, Metal GPU)
                                           |   ^
                                  tool call|   |result
                                           v   |
                                         calculator()
```

Key decisions:

1. **Ollama runs on the host, not in Docker.** Docker on macOS cannot reach the Apple GPU, so a containerized model would run on CPU only and be slow. Containers reach it at `http://host.docker.internal:11434`.
2. **The loop lives in our own `agent` service**, not inside Open WebUI. This makes the loop explicit and testable. Open WebUI sees the agent as an OpenAI-compatible model (`/v1/chat/completions`), so the browser UI works unchanged.
3. **Calculator is a plain function with a JSON schema**, evaluated by a restricted AST walker. It never calls `eval`.
4. **Terraform owns everything in Docker.** Ollama is installed and the model is pulled by a small bootstrap script, since Terraform is poor at managing host services.

## 4. The loop (inside `agent`)

```
messages = [system, ...history, user]
for step in 1..MAX_STEPS (default 5):
    reply = ollama.chat(model, messages, tools=[calculator_schema])
    if reply has no tool_calls:
        return reply.content              # final answer
    for call in reply.tool_calls:
        result = run_tool(call.name, call.arguments)   # errors become text, not crashes
        messages += [reply, {role: "tool", name, content: result}]
return "Stopped after MAX_STEPS without a final answer"
```

Guards: a step cap, a per-call timeout, unknown tool names return an error string to the model, and tool errors are fed back so the model can retry.

Calculator tool schema:

```json
{ "type": "function",
  "function": { "name": "calculator",
    "description": "Evaluate an arithmetic expression. Supports + - * / ** % and parentheses.",
    "parameters": { "type": "object",
      "properties": { "expression": { "type": "string" } },
      "required": ["expression"] } } }
```

## 5. Memory budget (24 GB machine)

| Piece | Approx. memory |
|---|---|
| `qwen3:4b` Q4 weights | 2.6 GB |
| KV cache at `num_ctx=4096` | about 0.5 GB |
| Colima VM actually used (Open WebUI plus agent) | about 1.5 GB |
| **Total** | **about 5 GB, roughly 20% of RAM** |

Settings that keep it small:
- `OLLAMA_MAX_LOADED_MODELS=1` and `OLLAMA_KEEP_ALIVE=5m` so the model unloads when idle
- `num_ctx: 4096` in the agent's Ollama options
- Lower the Colima VM from 20 GiB to 4 GiB: `colima stop && colima start --memory 4`. The 20 GiB is a ceiling and not used memory, but a smaller one prevents surprises.
- Fallback if it is still heavy: `qwen3:1.7b` (about 1.4 GB). Tool calling is less reliable at that size.

Why `qwen3:4b`: it supports native tool calling in Ollama and is the smallest Qwen size that handles a one-tool schema reliably. Qwen3 thinks by default. Send `think: false` (or `/no_think`) for the calculator flow to keep latency low.

## 6. Repository layout (to create)

```
ECCHarnessTesting/
  docs/agentic-loop-plan.md        <- this file
  infra/
    main.tf            network, volumes, images, containers
    variables.tf       model name, ports, memory limits
    outputs.tf         URLs
    terraform.tfvars   local overrides (git-ignored)
  agent/
    Dockerfile
    app.py             FastAPI: /v1/chat/completions, /v1/models, /healthz
    loop.py            the loop above
    tools.py           calculator + registry
    tests/test_tools.py  test_loop.py
  scripts/
    bootstrap.sh       brew checks, ollama serve env, ollama pull qwen3:4b
    smoke.sh           curl the agent with "what is 17 * 23 + 4?"
  Makefile             up / down / smoke / logs
```

Terraform resources (`main.tf`):
- `docker_network.agentnet`
- `docker_volume.openwebui_data`
- `docker_image.agent` (builds `./agent`), `docker_image.openwebui` (pinned tag, never `latest`)
- `docker_container.agent`: env `OLLAMA_URL=http://host.docker.internal:11434`, `MODEL=qwen3:4b`, `host` mapping `host.docker.internal:host-gateway`, memory limit 512 MB, healthcheck on `/healthz`
- `docker_container.openwebui`: port `3000:8080`, env `OPENAI_API_BASE_URL=http://agent:8000/v1`, `OPENAI_API_KEY=local`, `ENABLE_OLLAMA_API=false`, `WEBUI_AUTH=false` for a single-user local setup, memory limit 1 GB, volume mount

## 7. Phases

| Phase | Work | Done when |
|---|---|---|
| 0. Prep | `brew install terraform`; shrink Colima to 4 GiB; `OLLAMA_*` env; `ollama pull qwen3:4b` | `ollama run qwen3:4b "hi"` answers, `terraform -v` works |
| 1. Tool + loop | `tools.py` with tests (precedence, divide by zero, rejects `__import__`), `loop.py` with a fake Ollama client | `pytest` green |
| 2. Agent service | FastAPI wrapper plus Dockerfile | `curl localhost:8000/v1/chat/completions` returns a correct answer to "17*23+4" (395) |
| 3. IaC | Terraform for network, volume, both containers | `terraform apply` brings the stack up from nothing; `destroy` then `apply` gives the same result |
| 4. UI | Open WebUI pointed at the agent | In the browser, a maths question shows the right answer, and the agent log shows one `calculator` call |
| 5. Harden | Step cap, timeouts, memory limits, `make smoke` | Smoke test passes; Activity Monitor shows total under about 6 GB |

## 8. Verification

- Unit: calculator accepts `2+3*4` (14), `2**10`, `(1+2)/4`; rejects names, attribute access, calls, and strings longer than 200 characters.
- Loop: with a scripted fake model, one tool call then a final answer produces two model turns; a model that never stops is cut off at `MAX_STEPS`.
- End to end: `scripts/smoke.sh` asks "What is 17 * 23 + 4?" and expects `395` in the reply, and the agent log contains exactly one `tool=calculator`.
- Rebuild: `make down && make up` leaves Open WebUI chat history intact (volume) and no orphan containers.

## 9. Risks and open questions

| Risk | Mitigation |
|---|---|
| Small model skips the tool or fumbles the arguments | System prompt says to always use `calculator` for arithmetic; the error text from bad calls goes back to the model; move to `qwen3:8b` (about 5 GB) if needed |
| `host.docker.internal` does not resolve under Colima | Add the `host-gateway` host entry (already planned); fallback is Colima's host address `192.168.5.2` |
| Ollama bound to localhost only | Set `OLLAMA_HOST=0.0.0.0:11434` for the Ollama process, and firewall to local use |
| Open WebUI image is large and updates fast | Pin the tag in `variables.tf` |
| Terraform state contains env values | Keep `*.tfstate` and `*.tfvars` in `.gitignore`; no real secrets are used here |

Open questions for you:
1. Terraform or OpenTofu? The plan assumes Terraform; the files work with either.
2. Should the loop live in our `agent` service (planned) or as an Open WebUI native Tool? The latter is less code but hides the loop.
3. Keep `WEBUI_AUTH=false`? It is fine on localhost for one user.

## 10. ECC items used

Consulted per the project `CLAUDE.md`: `skills/docker-patterns` (compose and container conventions), `skills/agent-harness-construction` (narrow schema-first tools, deterministic outputs, recovery on error, small action space), `agents/planner` format for the phase table. Not installed or run; read from `./ECC`.
