# ECC Harness Explainer

Explainer for [affaan-m/ECC](https://github.com/affaan-m/ECC) (v2.2.3, MIT), cloned to `./ECC`. Counts below come from the repo's own `AGENTS.md`/`README.md` and a directory listing.

## What it is in one paragraph

ECC is a **Claude Code plugin** (plugin slug `ecc@ecc`, npm `ecc-universal`). It is not an app or a library. It is a bundle of markdown prompts, JSON hook configs and Node scripts. Installed into your agent harness, it changes how the agent works. The README's loop is:

```
plan -> test -> implement -> review -> verify -> remember -> improve
```

Instead of re-explaining that process in every prompt, you install it once. The harness (Claude Code, and to a lesser degree Codex, Cursor, OpenCode, Gemini, etc.) then loads the right pieces automatically.

## What's inside

| Component | Dir | Count | What it is |
|---|---|---|---|
| **Agents** | `agents/` | 71 | Specialized subagents defined as markdown with YAML frontmatter (`name`, `description`, `tools`, `model`). Claude delegates to them. Examples: `planner`, `architect`, `tdd-guide`, `code-reviewer`, `security-reviewer`, `build-error-resolver`, `e2e-runner`, plus per-language reviewers and build-resolvers (Go, Rust, Python, TS, Java, Kotlin, Swift, C++, Django, FastAPI, React, Vue, ...). |
| **Skills** | `skills/` | 311 | Reusable workflow and domain-knowledge docs ("When to Use / How It Works / Examples"). Claude pulls them in when relevant, e.g. `continuous-learning-v2`, `gateguard`, `strategic-compact`, `autonomous-loops`, `api-design`, `backend-patterns`. |
| **Commands** | `commands/` | 97 | Slash commands such as `/plan`, `/tdd`, `/e2e`, `/code-review`, `/build-fix`, `/learn`, `/skill-create`, `/checkpoint`, `/evolve`. The README says these are legacy shims while ECC moves to a skills-first design. |
| **Hooks** | `hooks/hooks.json` + `scripts/hooks/` | ~25 entries | Event-driven automations (see below). This is what makes it a *harness* and not just prompts. |
| **Rules** | `rules/` | 23 sets | Always-loaded standards (security, coding style, testing), chosen by language: `common`, `typescript`, `python`, `golang`, `rust`, `java`, `swift`, `react`, and others. |
| **MCP configs** | `mcp-configs/` | 1 | Ready-made MCP server configurations. |
| **Contexts** | `contexts/` | 3 | Swappable context/mode prompts. |
| **Scripts** | `scripts/` | n/a | Cross-platform Node.js: installer (`install-apply.js`, `install-guided.js`), `doctor.js`, `harness-audit.js`, hook implementations, and others. |
| **Manifests** | `manifests/` | n/a | `install-profiles.json`, `install-modules.json`, and so on. These let you install a subset. Profiles: `minimal`, `core`, `developer`, `security`, `research`, `full`, `opencode`. |
| **AgentShield** | separate npm pkg `ecc-agentshield` | n/a | Scanner for prompts, hooks, MCP config, permissions and secrets in agent files. |
| **Docs/misc** | `docs/`, `the-*-guide.md`, `ecc2/`, `ecc_dashboard.py`, `pi/`, `docker/` | n/a | Translations, long/short/security guides, a Rust "ecc2" control-plane prototype and a dashboard. |

## How the harness works

### 1. Agent-first delegation
`AGENTS.md` and `CLAUDE.md` set the core principles: agent-first, test-driven (80%+ coverage), security-first, immutability, and plan before execute. They also set auto-delegation rules:

- Complex feature -> `planner`
- Code just written -> `code-reviewer`
- Bug fix or new feature -> `tdd-guide`
- Security-sensitive code -> `security-reviewer`
- Architecture decision -> `architect`
- Build failure -> the matching `*-build-resolver`

Independent work is meant to run as parallel agents.

### 2. Hooks (the runtime layer)
`hooks/hooks.json` wires scripts into Claude Code lifecycle events. Each hook is launched through `run-with-flags.js`, which gates it by **profile** (`minimal`, `standard`, `strict`). The same plugin can be light or heavy.

| Event | What ECC does (examples) |
|---|---|
| **PreToolUse** | `pre-bash-dispatcher`; `gateguard-fact-force` (makes the agent investigate before it edits); `config-protection` (blocks weakening lint/config files); `doc-file-warning`; `suggest-compact`; `mcp-health-check`; `governance-capture`; `observe` (records tool use for learning) |
| **UserPromptSubmit** | `hookify-runtime` (user-defined rule hooks) |
| **PreCompact** | `pre-compact`: saves state before context is compacted |
| **SessionStart** | `session-start-bootstrap`: restores prior-session context |
| **PostToolUse / Failure** | async/sync post-processing; MCP health tracking; skill-run tracking |
| **Stop** (each reply) | format and typecheck, `check-console-log`, `session-end` (summary), `evaluate-session`, `cost-tracker`, desktop notification |
| **SessionEnd** | session marker |

Hooks can block (exit code 2) or warn (stderr). The hook README warns against pasting the raw `hooks.json` into `settings.json`. Use the installer so paths get rewritten.

### 3. Memory and continuous learning
The memory-persistence hooks save session summaries and restore them next session. `continuous-learning-v2`, `/learn` and `/evolve` extract "instincts" (repeated patterns) from your sessions and turn them into reusable skills. The tagline is "Optimize the context window. Persist everything else."

### 4. Rules + prompt-defense baseline
`CLAUDE.md` includes a "Prompt Defense Baseline": don't change role, don't leak secrets, treat fetched or third-party content as untrusted, and so on. Language rule sets in `rules/` add always-on style, testing and security requirements.

### 5. Multi-harness support
Claude Code is primary. Native plugin paths exist for Codex and Qoder. Capability-limited adapters exist for Cursor, OpenCode, Gemini, Zed, Copilot, Antigravity and Qwen. See `hooks/codex-hooks.json`, `scripts/codex/`, `.opencode`-style builds, and `scripts/harness-adapter-compliance.js`.

## How you'd use it

```bash
npx ecc-universal@2.2.3 setup      # guided: scope (global/project) + hook profile
# or inside Claude Code: /plugin  -> install ecc@ecc
```

Then start a new Claude Code session and check `/plugin list`. After that, work normally or use commands like `/plan`, `/tdd`, `/code-review` and `/build-fix`. Hooks and rules apply automatically.
Requirements: Node 18+, Git, Claude Code 2.1+.
Run tests for the repo itself with `node tests/run-all.js`.

## Things worth knowing before installing

- **It is opinionated and heavy.** It adds many hooks that run on every tool call and every reply, including Stop hooks with long timeouts such as format/typecheck at up to 300s. Start with the `minimal` or `standard` profile, not `strict`.
- **Hooks execute code on your machine** and can block your tool calls. Read `hooks/hooks.json` and `scripts/hooks/` before enabling them. The README itself warns to install only from official sources, since unofficial mirrors may carry malware.
- **Don't stack installs.** The README says to pick either the guided setup or the native plugin commands, not both, and not a manual install on top of the plugin.
- **It overlaps with your own `~/.claude` setup.** Your global CLAUDE.md already uses a Stop/SessionEnd progress-journal hook. ECC's session-end, memory-persistence and `/learn` features do similar things, so they may duplicate or conflict.
- Project has commercial tiers (ECC Pro GitHub App for private repos) and sponsors, but the repo itself is MIT.

## Where to read next in `./ECC`

1. `README.md`: overview, install and platform matrix
2. `AGENTS.md` / `CLAUDE.md`: the agent rules the harness enforces
3. `hooks/README.md` and `hooks/hooks.json`: exactly what runs and when
4. `the-shortform-guide.md`, `the-longform-guide.md`, `the-security-guide.md`
5. `manifests/install-profiles.json`: what each install profile includes
