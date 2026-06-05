from app.agentic_rag.service import parse_query_plan


def test_parse_query_plan_accepts_json_object_and_clamps():
    queries, failed = parse_query_plan(
        '{"queries":[" HNSW tuning ","ef construction","HNSW tuning","extra"]}',
        question="What about HNSW?",
        max_queries=2,
        max_chars=80,
    )

    assert queries == ["HNSW tuning", "ef construction"]
    assert failed is False


def test_parse_query_plan_accepts_fenced_json_object():
    queries, failed = parse_query_plan(
        '```json\n{"queries":["hybrid retrieval","eval gating","citation validation"]}\n```',
        question="How do safety checks work?",
        max_queries=3,
        max_chars=80,
    )

    assert queries == ["hybrid retrieval", "eval gating", "citation validation"]
    assert failed is False


def test_parse_query_plan_falls_back_to_original_question():
    queries, failed = parse_query_plan(
        "not json",
        question="What about hybrid retrieval?",
        max_queries=4,
        max_chars=80,
    )

    assert "What about hybrid retrieval?" in queries
    assert failed is True
