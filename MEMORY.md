# MEMORY.md

Durable decisions for this repo: what was chosen, what was rejected and why.

`AGENTS.md` says **how** the code is organised; this file says **why** it is that
way, so nobody re-opens a settled question or reverses a decision by accident.
Trust the code over both when they disagree, and update both when architecture
changes.

Conventions: one entry per decision, `D<n>`, with a status. Newest at the bottom.
When a decision is reversed, do not delete it — mark it `superseded by D<n>` and
add the new one. Rationale matters more than the choice.

---

## 2026-11-19 — Reviewer as a second app

### D1 · Two apps in one repo, sharing `core/`

**Status:** accepted.

The reviewer is a second entrypoint (`review.py` + `review/`) that imports
`core/`, not a node in the planner graph and not a separate repository.

Why: `core/` is already a de-facto library (engine, `ModelSpec`, prompt loader,
verdict parsing, cost). It is exactly the part that would have to be duplicated
or vendored in a second repo, and the part most likely to change (providers).
The planner graph stays linear and credential-free.

Consequences: one venv, shared tests, and a boundary that has to be enforced
(`review/` -> `core/` only). Reviewer-only concerns (git, docker, HTTP probing)
must stay out of the planner's requirements via lazy imports.

Revisit if the reviewer needs a server, UI, webhooks or its own license.

### D2 · Reviewer is a release gate, not a PR-diff reviewer

**Status:** accepted.

Output is `GO` / `CONDITIONAL` / `NO-GO` over a repo at a ref plus its release
artifacts. Diff-only review competes with mature tools and loses the release
context that makes the adversarial angle worth anything.

### D3 · The agents read the repo; the bundle becomes a brief

**Status:** accepted.

Chosen over evidence-only prompting. An agentic CLI explores far better than a
truncated bundle on a large repo, and it is what makes subscriptions worth using.

Consequences accepted: reproducibility is weaker, so every seat streams a tool
transcript, `repo_sha` is recorded, and prompts/evidence get hashes. The
deterministic collectors still exist — they now produce a *brief* (diff stat,
hotspots, commands, URLs, acceptance criteria), not the whole payload.

### D4 · Four fixed lenses, `frontend` conditional, `general` fast path

**Status:** accepted.

`security`, `reliability`, `correctness`, `cost_perf`, plus `general` (one pair)
for PRs, plus `frontend` only when `--url` is passed. `release_ops` was rejected
as a fifth fixed lens: its content folds into `reliability` and `security`
(container hygiene, config parity) without the extra model cost.

### D5 · The model proposes, the harness executes

**Status:** accepted.

Red emits a validated `ProbePlan` (endpoint, role, payload, assertions, request
budget). A deterministic runner performs the requests with hard caps. No model
gets a raw HTTP client for destructive tests: otherwise "test the rate limit"
becomes an outage or a flagged account.

Caps: 1 rps sustained, burst 20, 300 requests per run, concurrency 1, abort on
first 429 or >5% 5xx. Rate-limit tests only on endpoints flagged expensive or
sensitive (login, OTP, search, export, payment).

### D6 · Code first, then probe

**Status:** accepted.

The authorization matrix is derived from handlers and middleware first; only
cells expected to be `deny` are exercised. Blind fuzzing is out of scope:
without knowing who owns which object, a 200 proves nothing and a scan produces
noise. The prerequisite is seeded multi-tenant fixtures; without them the lens
reports a coverage gap, never a pass.

### D7 · Review the dockerized build, but only claim config parity

**Status:** accepted.

The lab runs the image/compose definition so behaviour matches production more
closely, and it opens a class of findings that code review alone misses (debug
flags, source maps, demo seeds, exposed ports, env schema drift, non-root,
resource limits).

Explicit limit: one container on a 2-core runner reproduces *configuration*, not
*topology*. Capacity and DoS conclusions are invalid there; such hypotheses are
tagged `needs staging` and can never justify a `NO-GO`.

### D8 · Docker lab and active probing run only in GitHub Actions

**Status:** accepted.

The ephemeral runner is the sandbox: it is destroyed after the run, so probing,
browser automation and arbitrary-repo execution have nowhere to leak. The
laptop never runs the reviewed repo's code.

Consequences: `local` profile can emit `GO (code-only)` at most; the gate carries
`scope: code-only | full` and a release check requires `full`. `--gh-dispatch`
and `--gh-run` are the bridge from the laptop.

Accepted cost: subscription auth in CI is the weak spot. Browser logins do not
fit headless runners. Expect API keys except where the vendor issues a long-lived
token (Claude Code `CLAUDE_CODE_OAUTH_TOKEN`). Capability parity is not promised;
degraded capability is recorded in `coverage`.

### D9 · The judge gets no tools

**Status:** accepted.

Red investigates, blue verifies, the judge classifies severity and status over
the transcript. A judge with repo access re-investigates, contradicts red and
inflates cost.

### D10 · The gate is deterministic

**Status:** accepted.

Models produce findings; `review/gate.py` decides: open `critical` -> NO-GO;
open `high` with `--fail-on high` -> NO-GO; mediums -> CONDITIONAL; otherwise GO.
An unverified lens with security in scope is CONDITIONAL at best (NO-GO with
`--strict`). This keeps the verdict testable and impossible to talk out of.

### D11 · Provider independence is a three-method contract

**Status:** accepted.

Required: `invoke(prompt) -> message(content, usage_metadata)`. Optional:
`with_structured_output(schema, include_raw=True)`; `core/structured.py` already
falls back to text -> JSON. No function calling, no assumed context window, no
model family name in prompts. Subscriptions arrive through the vendor's own
headless CLI (`claude_cli`, `codex_cli`, `gemini_cli`, `opencode_cli`,
`generic_cli`), because that is the sanctioned path and needs no API key.

### D12 · No production target, no exceptions

**Status:** accepted.

Targets must resolve to loopback/private. Anything else needs
`--target-allow <host>` plus `--i-understand`. There is deliberately no flag that
reaches production: an adversarial agent with a subscription and a prod URL is an
incident waiting for a date.

### D13 · One CLI adapter, agents as configuration

**Status:** accepted. Supersedes the per-vendor preset list in D11.

`claude_cli`, `codex_cli`, `gemini_cli` and friends were five things to maintain,
five flag sets to break and five output envelopes to parse. All of them share one
shape: a command that reads a prompt and prints the final message on stdout.

So: exactly one `cli` provider (`core/cli/provider.py`) and a `models.toml` that
declares `command`, `args`, `prompt` transport, `timeout`, `env` and a `login`
hint. A new agent is a config block, never a class. Seats stay `provider:model`.

Key consequence: **do not ask CLIs for JSON envelopes.** Plain stdout plus
`parse_json_object` is enough, and it removes all per-vendor parsing. Usage/cost
from CLI seats is `None`; that is acceptable and already handled.

Also decided here: `--models` / `$MODELS_TOML` / `./models.toml`, loaded only in
entrypoints; an empty `env` value removes a variable (forces a subscription login
over a stray API key); `openai_compatible` covers any OpenAI-shaped endpoint with
no config file.

Cost accepted: no per-vendor niceties (JSON envelopes, exact token counts, MCP
flag translation). Those return later as opt-in fields on the same config block,
not as new adapters.

### D14 · The gate contract: severity decides, nothing else

**Status:** accepted.

- `fail_on` is the lowest blocking severity; `critical` always blocks because
  nothing is above it.
- Below the threshold, **high and medium** downgrade to CONDITIONAL. Low and info
  never do: if they did, every real review would be CONDITIONAL and the verdict
  would stop meaning anything.
- High/critical need evidence, `accepted_risk` needs a rationale. A finding
  without evidence is a guess and must not stop a release.
- No `blocker` flag on findings and no dedup across lenses: severity plus status
  is the whole contract, and two lenses independently spotting the same issue is
  honest, not noise.
- Unverified (`fallback`, `skipped`) or unprobed (security/frontend under
  `code-only`) is CONDITIONAL, NO-GO under `--strict`. Zero lenses is
  CONDITIONAL, never GO.
- The gate ignores the debate winner and scores.
- Finding ids are namespaced by the lens prefix (`sec-1`, `ops-2`) inside the
  gate, not trusted from the model.

Rejected: letting the model mark blockers, dedup by title, and `--strict`
escalating a medium finding.

### D15 · A lens is a `DebateConfig`, and review turns need their own template

**Status:** accepted.

- `build_lens_debate(lens, models)` is the whole adapter: one red/blue/judge
  triad per lens, `min_rounds=1`, `max_rounds=2`, `max_turn_chars=16k` so the
  judge sees the full argument, no `skip_when` and no `fallback_verdict` (an
  invented fallback finding would be a false verdict).
- `turn_opening` / `turn_response` are config fields with the planner's
  templates as defaults. The review points both at `review/turn.md`: the stack
  template caps a turn at 3-5 sentences, which is incompatible with listing
  findings with `path:line`.
- Red, blue and judge prompts are shared by all lenses; the focus taxonomy goes
  into the brief. Adding a lens is one `Lens` row.
- The brief carries repo path, revision, scope and focus, never file contents:
  the CLI agent reads the repository itself.
- Prompts are loaded inside the factory, not at module level, so importing the
  lens table (the gate does) never depends on prompt files.

Rejected: per-lens prompt files (six copies of the same three prompts), and
putting the sentence limit override in the role prompt.

---

## Rejected (do not re-propose without new information)

| Option | Why not |
| :--- | :--- |
| Reviewer as a planner node | The planner would demand a repo; the intake flow is wrong; CI needs a standalone fast path |
| Separate repository now | Duplicates the one thing that changes most (providers); split later if a UI/service/license appears |
| Probe-first, then read code | Cannot tell who owns what; a 200 is not IDOR without expected behaviour |
| Blind fuzzing / scanning | Noise, abuse exposure, no hypothesis to verify |
| Active probing on the laptop | Executes reviewed code locally, orphaned processes, no isolation |
| LLM synthesis of cross-lens findings (v1) | Deterministic dedup plus report grouping is enough; a model pass just adds cost and drift |
| Auto-post PR comments (v1) | Noise before the false-positive rate is known |
| Renaming the repo | Cosmetic; deferred until the split |
| Five fixed lenses | Extra cost for coverage that folds into existing lenses |

## Open questions

- **CI auth matrix per vendor:** confirm which CLIs accept a non-interactive
  token today, per installed version. Resolve with `--check-models` on a runner,
  not from documentation.
- **Who starts the app:** v1 assumes an already-running `--url`. `--serve` with
  healthcheck and teardown is v2.
- **Deployment manifests:** does the brief ingest helm/terraform so config drift
  between compose and real prod is visible? Not decided.
- **Remediation output:** `review.json` may feed a remediation plan later. Keep
  the apps decoupled until then.

## How to update this file

- One decision per entry, with the date and a status (`accepted`, `superseded
  by D<n>`).
- Record the rejected alternatives: they are the expensive knowledge.
- No secrets, no machine-specific paths, no transient todos — those belong in a
  session note, not here.
