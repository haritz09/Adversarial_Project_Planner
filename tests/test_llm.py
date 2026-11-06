from __future__ import annotations

import pytest

from core.llm import CachingResolver, ModelSpec, PlannerModels


def test_spec_parses_provider_and_model_with_colons():
    spec = ModelSpec.parse("openrouter:meta-llama/llama-3:free")
    assert spec.provider == "openrouter"
    assert spec.model == "meta-llama/llama-3:free"

def test_spec_rejects_malformed_values():
    for value in ("", "groq", ":model"):
        with pytest.raises(ValueError):
            ModelSpec.parse(value)

def test_resolver_builds_each_model_once():
    calls = []

    def factory(spec):
        calls.append(spec)
        return object()

    resolver = CachingResolver(providers={"fake": factory})
    spec = ModelSpec.parse("fake:model")
    assert resolver.resolve(spec) is resolver.resolve(spec)
    assert calls == [spec]

def test_unknown_provider_fails_loudly():
    resolver = CachingResolver(providers={})
    with pytest.raises(ValueError, match="Unknown model provider"):
        resolver.resolve(ModelSpec.parse("nope:model"))

def test_models_are_configurable_from_env(monkeypatch):
    monkeypatch.setenv("PLANNER_MODEL_DEBATER", "groq:debater-model")
    monkeypatch.setenv("PLANNER_MODEL_JUDGE", "groq:judge-model")
    monkeypatch.setenv("PLANNER_MODEL_GENERATOR", "google_genai:gen-model")

    models = PlannerModels.from_env()

    assert models.debater_a.model == "debater-model"
    assert models.debater_b.model == "debater-model"
    assert models.judge.model == "judge-model"
    assert models.generator.model == "gen-model"
