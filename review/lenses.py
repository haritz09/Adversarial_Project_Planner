from __future__ import annotations

from dataclasses import dataclass


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
            "the highest-impact, concrete reasons this release should not ship",
            "anything the specialised lenses would miss on this particular repo",
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
