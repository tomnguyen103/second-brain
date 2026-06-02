"""Eval A/B config registry (ADR-0009). DB-free."""
from app.config import Settings
from app.eval.configs import CONFIGS, settings_for


def test_registry_has_ab_and_real_configs():
    assert {"baseline", "variant", "gemini"} <= set(CONFIGS)
    assert CONFIGS["baseline"].prompt_version == "rag-v1"
    assert CONFIGS["baseline"].llm_provider == "fake"
    assert CONFIGS["variant"].prompt_version == "rag-v2"
    assert CONFIGS["gemini"].llm_provider == "gemini"


def test_settings_for_applies_overrides():
    s = settings_for(CONFIGS["variant"], base=Settings(_env_file=None))
    assert s.llm_provider == "fake"
    assert s.prompt_version == "rag-v2"
    assert s.retrieval_top_k == 5


def test_default_ab_pair_is_single_variable():
    """baseline vs variant differ only by prompt_version (top_k fixed) — attributable A/B."""
    a, b = CONFIGS["baseline"], CONFIGS["variant"]
    assert a.top_k == b.top_k
    assert a.prompt_version != b.prompt_version


def test_settings_for_does_not_mutate_base():
    base = Settings(_env_file=None)
    before = base.prompt_version
    settings_for(CONFIGS["variant"], base=base)
    assert base.prompt_version == before   # model_copy returns a new instance
