from __future__ import annotations

from memory_engine.control.service import validate_definition


def test_validate_definition_flags_unknown_memory_reference() -> None:
    issues = validate_definition(
        "api_ontology",
        {
            "document_name": "API Ontology",
            "entries": [
                {
                    "api_name": "search.webSearch",
                    "enabled": True,
                    "capability_family": "SEARCH_READ",
                    "method_semantics": "READ",
                    "domain": "search",
                    "description": "Search",
                    "candidate_memory_types": ["interest.missing"],
                    "default_action": "OBSERVE",
                    "repeat_policy": "REQUIRED",
                    "sensitivity_hint": "S1_INTERNAL",
                    "source_trust": 30,
                    "extractors": ["topic_extractor"],
                    "relation_templates": [],
                    "dedup_strategy_hint": "TOPIC_SCORE",
                    "conflict_strategy_hint": "NO_DIRECT_CONFLICT",
                    "tenant_override_allowed": True,
                    "notes": "",
                }
            ],
        },
        reference_memory_types={"interest.topic"},
    )
    assert any(issue.code == "reference.integrity" for issue in issues)
