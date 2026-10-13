# ECCHarnessTesting

A small local agentic loop, plus a study of the ECC harness it was planned with.

You chat with a Qwen model in a browser. When you ask a maths question, the model calls a calculator tool, gets the result back, and answers. Each step of that loop is shown in the chat and written to an audit log. Everything runs on one MacBook (Apple M5 Pro, 24 GB), and the Docker part is created from code.

## What is in here

| Path | What it is |
|---|---|
| `agent/` | The agent service: loop, calculator tool, audit trail, OpenAI-style API, Dockerfile, tests |
| `infra/` | OpenTofu/Terraform files that create the Docker network, volumes and containers |
| `scripts/` | `bootstrap.sh` (starts Ollama and pulls the model), `smoke.sh` (end-to-end check) |
| `Makefile` | `make up`, `down`, `test`, `smoke`, `logs`, `audit`, `webui-audit` |
| `docs/agentic-loop-plan.md` | The plan this was built from |
| `docs/local-agent-loop.html` | Diagram page (also published as an artifact: https://claude.ai/artifact/3MRZGm3HAJUiBRgCfeAde7, private to the owner) |
| `ECCHarnessExplainer.md` | Explainer for the ECC repo |
| `ECC/` | Shallow clone of https://github.com/affaan-m/ECC (v2.2.3). Git-ignored, not installed |
| `CLAUDE.md` | Project guide and running progress journal for Claude Code |

## How it works

```
Browser :3000 -> Open WebUI (Docker) -> agent :8000 (Docker) -> Ollama :11435 (macOS host, qwen3:4b)
                                          |  ^
                                tool_call |  | result
                                          v  |
                                       calculator()
```

1. **Open WebUI** is the chat front end. It sees the agent as an OpenAI-compatible model called `calc-agent`.
2. **The agent** owns the loop (`agent/loop.py`). It sends the conversation and the tool schema to the model. If the reply contains a tool call, it runs the tool, appends the result, and asks again. A reply with no tool call is the final answer. After 5 rounds it stops.
3. **The calculator** (`agent/tools.py`) parses the expression with a whitelist of arithmetic operations. It never uses `eval`, and errors are returned as text so the model can retry.
4. **Ollama runs on the host, not in Docker**, because Docker on macOS cannot use the Apple GPU. Containers reach it at `host.docker.internal:11435`. It is a second Ollama instance, so any Ollama already on port 11434 is left alone.
5. **OpenTofu** (`infra/`) creates the network, two volumes (Open WebUI data, audit log) and both containers. Open WebUI is pinned to `v0.12.0`.

### Audit log and visible loop

- **In the chat:** each answer starts with a quoted "Agent loop" block that fills in live: each model call, the tool the model chose and its arguments, the tool result, and timings. The block is stripped from history before the next turn, so the model never sees it.
- **Agent audit:** every request and loop event is appended to `/data/audit.jsonl` in a Docker volume. Read it with `make audit` (`N=50 make audit` for more) or `GET http://localhost:8000/audit`.
- **Open WebUI audit:** enabled with `AUDIT_LOG_LEVEL=REQUEST_RESPONSE`. Read it with `make webui-audit`. In testing it showed sign-in and sign-out requests. I did not confirm that chat requests appear in it, so the agent audit is the detailed record of what the loop did.

## Run it

Prerequisites: macOS with Docker (this setup uses Colima), Ollama and OpenTofu (`brew install opentofu`). The Docker socket path is set by the `docker_host` variable in `infra/variables.tf`; change it if you do not use Colima's default profile.

```bash
make up        # start Ollama on :11435, pull qwen3:4b, tofu apply
make smoke     # asks "What is 17 * 23 + 4?" and expects 395
make test      # 12 unit tests, no dependencies
make audit     # recent loop events
make down      # tofu destroy (volumes are removed too)
```

Then open http://localhost:3000 and pick `calc-agent`. Login is disabled (`WEBUI_AUTH=false`), which is fine for one user on localhost. The Ollama on :11435 does not restart after a reboot; run `make bootstrap` again.

Memory: about 2.6 GB for the model plus about 1 GB for the containers. Measured: agent 35 MiB, Open WebUI 915 MiB.

## Verified so far

- `make test`: 12 tests pass (calculator safety and errors, loop, step cap, error feedback, `<think>` stripping, event emission, trace stripping)
- `make smoke`: reply contains 395 and the log shows exactly one calculator call
- A chat sent through Open WebUI's API returned the right answer, and the agent log showed the tool call
- Streaming from the agent shows the loop steps live

Not verified: how the trace block looks in the browser UI. The Open WebUI audit log is also not confirmed to record chat requests.

## Known quirks

- Qwen3 leaks `<think>` text into replies even with thinking turned off, so `loop.clean()` strips it.
- With `WEBUI_AUTH=false`, API calls still need a token: `POST /api/v1/auths/signin` with `{"email":"admin@localhost","password":""}`.
- The Colima VM was not shrunk, because it also runs unrelated containers. Its 20 GiB is a ceiling, not memory in use.
- OpenTofu is used instead of Terraform because Homebrew no longer ships a `terraform` formula. The `.tf` files are the same.

## What of the ECC harness was used

ECC (https://github.com/affaan-m/ECC) is a Claude Code plugin bundling agents, skills, commands, hooks and rules. See `ECCHarnessExplainer.md` for what it contains.

**It was used as reference material only. It was not installed, and none of its agents, commands, hooks or rules ran.**

| ECC item | How it was used |
|---|---|
| `ECC/skills/docker-patterns` | Read for Docker Compose and container conventions, applied to the container setup (memory limits, healthchecks, pinned images, non-root user) |
| `ECC/skills/agent-harness-construction` | Read for tool design: a narrow schema-first tool, deterministic outputs, errors returned to the model, a capped loop |
| `ECC/AGENTS.md`, `CLAUDE.md`, `README.md`, `hooks/hooks.json`, `manifests/install-profiles.json` | Read to write `ECCHarnessExplainer.md` |

The project `CLAUDE.md` tells Claude Code to check `./ECC` for a usable skill, agent, command, hook or rule on every task. For this build nothing beyond the two skills above fit. Planning and the diagram used Claude Code's own artifact skills, not ECC's `planner` agent, `/plan` or `/tdd`. Tests were written alongside the code without ECC's `tdd-guide`.

To try ECC properly, run `npx ecc-universal@2.2.3 setup` and start with the `minimal` hook profile. Read `ECC/hooks/hooks.json` first, since its hooks run code on every tool call. Its session and memory hooks may overlap with the progress-journal hook in `~/.claude`.
