from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.models import DebateConfig, DebateModels, RoleSpec
from core.prompt_loader import load_prompt, render_prompt
from review.models import ReviewVerdict


@dataclass(frozen=True)
class Lens:
    """What one adversarial review looks at, and what it needs to run."""

    id: str
    prefix: str
    title: str
    focus: tuple[str, ...]
    probes: bool = False  # active probing / browser: `ci` profile only
    needs_target: bool = False


LENSES: tuple[Lens, ...] = (
    Lens(
        id="general",
        prefix="gen",
        title="General adversarial release review",
        focus=(
            "concrete, release-blocking defects in this repository, with `path:line` evidence",
            "cross-cutting failures the specialised lenses miss: broken flows, dangerous "
            "defaults, data loss",
        ),
    ),
    Lens(
        id="security",
        prefix="sec",
        title="Security: authentication, authorization, secrets",
        focus=(
            "authentication: sessions, tokens, password reset, MFA",
            "authorization and permissions: IDOR, tenant isolation, role checks",
            "secrets in code, config, logs and error responses",
            "input validation and injection: SQL, template, command, SSRF",
            "dependency and known-CVE exposure",
            "rate limits and abuse of sensitive endpoints (login, OTP, export)",
            "transport, headers, cookies, file uploads",
        ),
        probes=True,
    ),
    Lens(
        id="reliability",
        prefix="ops",
        title="Reliability and operations",
        focus=(
            "error handling and failure modes",
            "timeouts, retries, backoff, idempotency",
            "migrations, rollback and data loss",
            "healthchecks, graceful degradation, resource limits",
            "logs, metrics and traces",
            "config wiring and startup validation",
            "container hygiene: non-root, pinned base, no debug flags",
        ),
    ),
    Lens(
        id="correctness",
        prefix="cor",
        title="Correctness against the spec",
        focus=(
            "behaviour versus the stated requirements or plan",
            "edge cases, validation, empty and oversized inputs",
            "concurrency, races and transactional integrity",
            "silent failures and swallowed errors",
            "test coverage of the risky paths",
        ),
    ),
    Lens(
        id="cost_perf",
        prefix="perf",
        title="Performance and cost",
        focus=(
            "N+1 queries and query count per request",
            "missing indexes and full table scans",
            "unbounded queries, payloads and pagination",
            "synchronous work in the request path",
            "caching, invalidation, polling versus webhooks",
            "cold starts and per-request spend",
        ),
    ),
    Lens(
        id="frontend",
        prefix="ui",
        title="Frontend flows and accessibility",
        focus=(
            "console errors and failed requests on critical flows",
            "broken, empty and error states",
            "basic accessibility: labels, focus order, contrast",
        ),
        probes=True,
        needs_target=True,
    ),
)

BY_ID = {lens.id: lens for lens in LENSES}

PROBED_LENSES = frozenset(lens.id for lens in LENSES if lens.probes)

REVIEW_MAX_TURN_CHARS = 16_000
REVIEW_MAX_ROUNDS = 2
REVIEW_TURN_PROMPT = "review/turn.md"


def resolve_lens(value: str | Lens) -> Lens:
    if isinstance(value, Lens):
        return value
    try:
        return BY_ID[value]
    except KeyError:
        raise ValueError(
            f"unknown lens {value!r}; choose from {', '.join(BY_ID)}"
        ) from None


def build_brief(lens: Lens, data: Mapping[str, Any]) -> str:
    return render_prompt(
        "review/brief.md",
        repo=data.get("repo") or "the current working directory",
        ref=data.get("ref") or "unknown",
        scope=data.get("scope") or "code-only",
        lens_title=lens.title,
        focus="\n".join(f"- {item}" for item in lens.focus),
        prior=data.get("prior") or "none reported yet",
    )


def build_lens_debate(lens: str | Lens, models: DebateModels) -> DebateConfig:
    resolved = resolve_lens(lens)
    return DebateConfig(
        name=resolved.id,
        topic=resolved.title,
        role_a=RoleSpec(label="A", system_prompt=load_prompt("review/red.md")),
        role_b=RoleSpec(label="B", system_prompt=load_prompt("review/blue.md")),
        judge_rubric=load_prompt("review/judge.md"),
        verdict_model=ReviewVerdict,
        models=models,
        brief=lambda data: build_brief(resolved, data),
        min_rounds=1,
        max_rounds=REVIEW_MAX_ROUNDS,
        max_turn_chars=REVIEW_MAX_TURN_CHARS,
        turn_opening=REVIEW_TURN_PROMPT,
        turn_response=REVIEW_TURN_PROMPT,
    )
