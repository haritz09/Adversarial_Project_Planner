from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import ValidationError

from core.json_utils import message_text, parse_json_object
from core.models import BaseVerdict

logger = logging.getLogger(__name__)

V = TypeVar("V", bound=BaseVerdict)

class VerdictParseError(RuntimeError):

    pass

def invoke_verdict(
    llm: Any, prompt: str, verdict_model: type[V]
) -> tuple[V, Any | None]:

    try:
        structured = llm.with_structured_output(verdict_model, include_raw=True)
        outcome = structured.invoke(prompt)
    except Exception as exc:
        logger.debug("Structured output unavailable (%s); using text fallback", exc)
    else:
        if isinstance(outcome, dict):
            parsed = outcome.get("parsed")
            raw = outcome.get("raw")
            if isinstance(parsed, verdict_model):
                return parsed, raw
            if parsed is not None:
                try:
                    return verdict_model.model_validate(parsed), raw
                except ValidationError:
                    pass
            if raw is not None:
                data = parse_json_object(message_text(raw))
                if data is not None:
                    try:
                        return verdict_model.model_validate(data), raw
                    except ValidationError:
                        pass
        elif isinstance(outcome, verdict_model):
            return outcome, None

    message = llm.invoke(prompt)
    text = message_text(message)
    data = parse_json_object(text)
    if data is None:
        raise VerdictParseError(f"Judge returned no JSON object: {text[:200]!r}")
    try:
        verdict = verdict_model.model_validate(data)
    except ValidationError as exc:
        raise VerdictParseError(f"Judge JSON did not match schema: {exc}") from exc
    return verdict, message
