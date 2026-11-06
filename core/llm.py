from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from core.models import ModelLike


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str
    temperature: float = 0.0
    max_tokens: int | None = None

    @classmethod
    def parse(cls, value: str) -> ModelSpec:
        raw = (value or "").strip()
        if not raw:
            raise ValueError("Empty model spec")
        provider, _, model = raw.partition(":")
        if not provider or not model:
            raise ValueError(f"Expected 'provider:model', got {value!r}")
        return cls(provider=provider.strip(), model=model.strip())

ProviderFactory = Callable[[ModelSpec], object]

_PROVIDERS: dict[str, ProviderFactory] = {}

def register_provider(name: str) -> Callable[[ProviderFactory], ProviderFactory]:

    def decorator(factory: ProviderFactory) -> ProviderFactory:
        _PROVIDERS[name] = factory
        return factory

    return decorator

def available_providers() -> list[str]:
    return sorted(_PROVIDERS)

@register_provider("groq")
def _groq(spec: ModelSpec):
    from langchain_groq import ChatGroq

    return ChatGroq(
        model=spec.model,
        temperature=spec.temperature,
        max_tokens=spec.max_tokens,
    )

@register_provider("google_genai")
def _google_genai(spec: ModelSpec):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=spec.model,
        temperature=spec.temperature,
        max_output_tokens=spec.max_tokens,
    )

@register_provider("openai")
def _openai(spec: ModelSpec):
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=spec.model,
        temperature=spec.temperature,
        max_tokens=spec.max_tokens,
    )

@runtime_checkable
class ModelResolver(Protocol):
    def resolve(self, spec: ModelSpec):
        ...

class CachingResolver:

    def __init__(self, providers: Mapping[str, ProviderFactory] | None = None) -> None:
        self._providers = dict(providers or _PROVIDERS)
        self._cache: dict[ModelSpec, object] = {}

    def resolve(self, spec: ModelSpec):
        if spec not in self._cache:
            factory = self._providers.get(spec.provider)
            if factory is None:
                raise ValueError(
                    f"Unknown model provider {spec.provider!r}. "
                    f"Available: {', '.join(sorted(self._providers))}"
                )
            self._cache[spec] = factory(spec)
        return self._cache[spec]

_default_resolver = CachingResolver()

def resolve_model(model: ModelLike, resolver: ModelResolver | None = None):
    if isinstance(model, ModelSpec):
        return (resolver or _default_resolver).resolve(model)
    return model

@dataclass(frozen=True)
class PlannerModels:

    intake: ModelSpec
    debater_a: ModelSpec
    debater_b: ModelSpec
    judge: ModelSpec
    generator: ModelSpec

    @property
    def debate(self) -> tuple[ModelSpec, ModelSpec, ModelSpec]:
        return self.debater_a, self.debater_b, self.judge

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PlannerModels:
        env = env if env is not None else os.environ
        debater = env.get("PLANNER_MODEL_DEBATER", "groq:llama-3.1-8b-instant")

        def spec(key: str, default: str) -> ModelSpec:
            return ModelSpec.parse(env.get(key, default))

        return cls(
            intake=spec("PLANNER_MODEL_INTAKE", debater),
            debater_a=spec("PLANNER_MODEL_DEBATER_A", debater),
            debater_b=spec("PLANNER_MODEL_DEBATER_B", debater),
            judge=spec("PLANNER_MODEL_JUDGE", "groq:llama-3.3-70b-versatile"),
            generator=spec("PLANNER_MODEL_GENERATOR", "google_genai:gemini-2.5-flash"),
        )
