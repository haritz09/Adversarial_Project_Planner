from __future__ import annotations

import observability


class FakeClient:
    def __init__(self) -> None:
        self.scores: list[dict] = []
        self.flushed = False

    def create_trace_id(self) -> str:
        return "trace-123"

    def create_score(self, **kwargs) -> None:
        self.scores.append(kwargs)

    def flush(self) -> None:
        self.flushed = True

def test_disabled_without_credentials():
    session = observability.start_trace("run")

    assert session.enabled is False
    assert session.handler is None
    assert observability.start_trace("run", session_id="run").metadata() == {
        "langfuse_session_id": "run"
    }

def test_scores_share_the_handler_trace_id():
    client = FakeClient()
    seen: dict = {}

    def handler_factory(trace_context):
        seen["trace_context"] = trace_context
        return object()

    session = observability.start_trace(
        "run",
        session_id="session-1",
        enabled=True,
        client_factory=lambda: client,
        handler_factory=handler_factory,
    )
    observability.score(session, "agent_a_score", 0.8, comment="winner A")
    observability.finish(session)

    assert session.trace_id == "trace-123"
    assert seen["trace_context"]["trace_id"] == "trace-123"
    assert client.scores == [
        {
            "trace_id": "trace-123",
            "name": "agent_a_score",
            "value": 0.8,
            "comment": "winner A",
        }
    ]
    assert client.flushed is True

def test_broken_client_disables_tracing_instead_of_crashing():
    def boom():
        raise RuntimeError("bad keys")

    session = observability.start_trace(
        "run", enabled=True, client_factory=boom, handler_factory=lambda **kwargs: None
    )

    assert session.enabled is False
    assert "bad keys" in session.reason
    observability.score(session, "ignored", 1.0)
