from __future__ import annotations

from typing import Any

PRICES_USD_PER_MTOK: dict[str, tuple[float, float]] = {
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
}

def extract_usage(message: Any) -> tuple[int, int]:
    usage = getattr(message, "usage_metadata", None) or {}
    if usage:
        return int(usage.get("input_tokens") or 0), int(usage.get("output_tokens") or 0)

    metadata = getattr(message, "response_metadata", None) or {}
    for key in ("token_usage", "usage", "usage_metadata"):
        payload = metadata.get(key) or {}
        if payload:
            return (
                int(payload.get("prompt_tokens") or payload.get("input_tokens") or 0),
                int(payload.get("completion_tokens") or payload.get("output_tokens") or 0),
            )
    return 0, 0

def estimate_cost(
    model_name: str | None,
    input_tokens: int,
    output_tokens: int,
    prices: dict[str, tuple[float, float]] | None = None,
) -> float | None:
    if not model_name:
        return None
    table = prices if prices is not None else PRICES_USD_PER_MTOK
    price = table.get(model_name)
    if price is None:
        return None
    input_price, output_price = price
    return round(
        (input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price,
        8,
    )

def model_name_of(spec_or_model: Any) -> str | None:
    name = getattr(spec_or_model, "model", None)
    if isinstance(name, str):
        return name
    name = getattr(spec_or_model, "model_name", None)
    return name if isinstance(name, str) else None
