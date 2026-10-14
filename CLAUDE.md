# ECCHarnessTesting

Sandbox for studying the ECC harness (https://github.com/affaan-m/ECC), cloned at `./ECC`.

## Always consult the ECC harness

Whenever a task is given, first read `ECCHarnessExplainer.md` and check whether an ECC
skill, hook, agent or command could be used for it. If one applies, use it (or follow its
definition) and say which one you used:

- Agents: `./ECC/agents/*.md` (e.g. planner, tdd-guide, code-reviewer, security-reviewer, `*-build-resolver`)
- Skills: `./ECC/skills/<name>/` (workflows and domain knowledge)
- Commands: `./ECC/commands/*.md` (e.g. /plan, /tdd, /code-review, /build-fix)
- Hooks: `./ECC/hooks/hooks.json` and `./ECC/scripts/hooks/` (check which would fire or help)
- Rules: `./ECC/rules/` for the relevant language

If nothing in ECC fits, proceed normally. ECC is only cloned, not installed, so read these
files from `./ECC` rather than expecting them to be loaded automatically.

<!-- PROGRESS:START -->
## Progress log

### Current state
Agentic loop is BUILT but currently STOPPED (to save memory; `make up` restarts it). `make up` = bootstrap (dedicated Ollama on host :11435, qwen3:4b) + `tofu apply` (network, volume, `agentloop-agent` :8000, `agentloop-openwebui` :3000). Verified: `make test` (9 unit tests), `make smoke` (395, 1 calculator call), and a chat through Open WebUI's API returning the right answer. Plan/diagram: `docs/agentic-loop-plan.md`, artifact https://claude.ai/artifact/3MRZGm3HAJUiBRgCfeAde7.

### Next steps
- [ ] Answer pending offer: add `.env` / `.env.example` to `.gitignore`, verify `git status` shows no tfstate before pushing
- [ ] Genericize the colima path in `infra/variables.tf`
- [ ] Check the live trace renders well in the browser chat (blockquote above each answer)
- [ ] Try it in the browser at http://localhost:3000 (model "calc-agent")
- [ ] Add a second tool / multi-step test cases; consider streaming real tokens
- [ ] Optionally install ECC with the `minimal` profile and test the hooks

### Gotchas / blockers
- ECC is not installed, only cloned. Nothing was run from it.

- Used OpenTofu (`tofu`), not Terraform: brew has no terraform formula. Same .tf files.
- Colima VM NOT shrunk: it hosts the user's other `dm_*` containers (dual-momentum). Existing Ollama on :11434 is untouched; ours is a separate `ollama serve` on :11435 (log /tmp/ollama-agentloop.log, not restarted on reboot: run `make bootstrap`).
- Qwen3 leaks `<think>` text into content even with think:false; `loop.clean()` strips it.
- Open WebUI with WEBUI_AUTH=false: API needs a token from POST /api/v1/auths/signin {email: admin@localhost, password: ""}.
- Machine: M5 Pro, 24 GB. Colima VM is allocated 20 GiB; `qwen3:14b` (9.3 GB) is already pulled but too big for the plan.

### Session history (newest first)
#### 2026-10-12 — Stop stack, README, secrets check before git upload
- Stack stopped to save memory (run `make up` to resume). Added a README mentioning the artifact URL.
- Secrets audit (no code changes): no real secrets. `OPENAI_API_KEY=local` in `infra/main.tf` is a dummy; WEBUI_AUTH is off; Open WebUI's secret key lives in the Docker volume.
- Pre-upload advice given: `.gitignore` already excludes tfstate, `.terraform/`, `*.tfvars` and `ECC/` (nested clone; use a submodule if wanted). `infra/variables.tf` has a personal `/Users/yunwesth/.colima/...` path to genericize. If a real key is added later, use `.env` (gitignored) plus a `sensitive` tofu variable.
- Offered to add `.env`/`.env.example` to `.gitignore`; user hadn't answered yet. Repo now has an "Initial Commit" on main.

#### 2026-10-12 — Audit log + visible loop
- `agent/trace.py` (JSONL audit at /data/audit.jsonl in volume `agentloop_audit`, live trace text, strip_trace for history), `loop.run_agent(emit=)` events, real SSE streaming in `app.py`, `GET /audit`
- Open WebUI `AUDIT_LOG_LEVEL=REQUEST_RESPONSE` (file /app/backend/data/audit.log)
- `make audit [N=30]`, `make webui-audit [N=5]`; 12 tests pass; verified stream shows steps live

#### 2026-10-12 — Build the agentic loop
- Added `agent/` (tools.py, loop.py, app.py, Dockerfile, tests), `infra/*.tf`, `scripts/{bootstrap,smoke}.sh`, `Makefile`, `.gitignore`
- brew install opentofu; ollama pull qwen3:4b; `tofu apply` created 6 resources; Open WebUI pinned v0.12.0
- Measured: agent 35 MiB, Open WebUI 915 MiB

#### 2026-10-12 — Plan local agentic loop
- Consulted ECC `docker-patterns` and `agent-harness-construction`
- Created `docs/agentic-loop-plan.md` and `docs/local-agent-loop.html` (published as artifact)
- Design: Terraform docker provider, Open WebUI -> own `agent` service (loop + calculator) -> Ollama on host with `qwen3:4b`

#### 2026-10-12 — Clone ECC and write explainer
- `git clone --depth 1` into `./ECC`; read CLAUDE.md, AGENTS.md, README.md, hooks/hooks.json, manifests/install-profiles.json
- Created `ECCHarnessExplainer.md`
<!-- PROGRESS:END -->
