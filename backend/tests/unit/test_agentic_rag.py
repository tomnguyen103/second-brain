from app.agentic_rag.service import parse_query_plan


def test_parse_query_plan_accepts_json_object_and_clamps():
    queries, failed = parse_query_plan(
        '{"queries":[" HNSW tuning ","ef construction","HNSW tuning","extra"]}',
        question="What about HNSW?",
        max_queries=2,
        max_chars=80,
    )

    assert queries == ["What about HNSW?", "HNSW tuning"]
    assert failed is False


def test_parse_query_plan_accepts_fenced_json_object():
    queries, failed = parse_query_plan(
        '```json\n{"queries":["hybrid retrieval","eval gating","citation validation"]}\n```',
        question="How do safety checks work?",
        max_queries=3,
        max_chars=80,
    )

    assert queries == ["How do safety checks work?", "hybrid retrieval", "eval gating"]
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


def test_parse_query_plan_keeps_original_question_before_planner_paraphrases():
    queries, failed = parse_query_plan(
        '{"queries":["workflow pipeline definition","setup workflow pipeline"]}',
        question="what is workflow pipline and how to setup",
        max_queries=4,
        max_chars=80,
    )

    assert queries[0] == "what is workflow pipline and how to setup"
    assert queries[1:] == ["workflow pipeline definition", "setup workflow pipeline"]
    assert failed is False
