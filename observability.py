from __future__ import annotations

import logging
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

@dataclass
class TraceSession:
    enabled: bool = False
    client: Any | None = None
    handler: Any | None = None
    trace_id: str | None = None
    session_id: str | None = None
    reason: str | None = None
    scores: list[dict[str, Any]] = field(default_factory=list)

    def metadata(self) -> dict[str, Any]:
        return {"langfuse_session_id": self.session_id} if self.session_id else {}

def _enabled_from_env(env: Mapping[str, str] | None = None) -> bool:
    env = env if env is not None else os.environ
    flag = (env.get("LANGFUSE_ENABLED") or "").strip().lower()
    if flag in {"0", "false", "no", "off"}:
        return False
    return bool(env.get("LANGFUSE_PUBLIC_KEY") and env.get("LANGFUSE_SECRET_KEY"))

def start_trace(
    name: str,
    session_id: str | None = None,
    *,
    enabled: bool | None = None,
    client_factory: Callable[[], Any] | None = None,
    handler_factory: Callable[..., Any] | None = None,
) -> TraceSession:
    if enabled is None:
        enabled = _enabled_from_env()
    if not enabled:
        return TraceSession(enabled=False, session_id=session_id, reason="disabled")

    try:
        if client_factory is None:
            from langfuse import Langfuse

            client_factory = Langfuse
        if handler_factory is None:
            from langfuse.langchain import CallbackHandler

            handler_factory = CallbackHandler

        client = client_factory()
        trace_id = client.create_trace_id()
        handler = handler_factory(trace_context={"trace_id": trace_id})
    except Exception as exc:
        logger.warning("Langfuse disabled: %s", exc)
        return TraceSession(enabled=False, session_id=session_id, reason=str(exc))

    return TraceSession(
        enabled=True,
        client=client,
        handler=handler,
        trace_id=trace_id,
        session_id=session_id,
    )

def score(
    session: TraceSession,
    name: str,
    value: float,
    comment: str | None = None,
    *,
    data_type: str | None = None,
) -> None:
    if not session.enabled or session.client is None:
        return
    if session.trace_id is None:
        logger.warning("Skipping score %r: no trace id", name)
        return
    try:
        payload: dict[str, Any] = {
            "trace_id": session.trace_id,
            "name": name,
            "value": float(value),
            "comment": comment,
        }
        if data_type:
            payload["data_type"] = data_type
        session.client.create_score(**payload)
        session.scores.append({"name": name, "value": float(value)})
    except Exception as exc:
        logger.warning("Failed to send score %r: %s", name, exc)

def finish(session: TraceSession) -> None:
    if not session.enabled or session.client is None:
        return
    try:
        session.client.flush()
    except Exception as exc:
        logger.warning("Langfuse flush failed: %s", exc)
