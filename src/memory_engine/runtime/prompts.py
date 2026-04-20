from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


@dataclass(frozen=True)
class PromptTemplateDefinition:
    key: str
    version: str
    description: str
    system_prompt: str


PROMPT_TEMPLATES: dict[str, PromptTemplateDefinition] = {
    "memory.hybrid.ingest.v1": PromptTemplateDefinition(
        key="memory.hybrid.ingest.v1",
        version="2026-04-11",
        description="Hybrid ingestion prompt for normalized API event envelopes.",
        system_prompt=(
            "You are MemoryEngine's internal memory-worthiness assistant. "
            "Use only the provided normalized event payload and provided candidate indexes. "
            "Do not invent new memory types or candidate indexes. "
            "Respond with structured JSON only."
        ),
    ),
    "memory.hybrid.search.v1": PromptTemplateDefinition(
        key="memory.hybrid.search.v1",
        version="2026-04-11",
        description="Hybrid ingestion prompt tuned for ambiguous read and search behaviors.",
        system_prompt=(
            "You are MemoryEngine's internal assistant for ambiguous read and search events. "
            "Prefer conservative recommendations, use only the provided candidate indexes, "
            "and respond with structured JSON only."
        ),
    ),
}


def get_prompt_template(key: str) -> PromptTemplateDefinition:
    try:
        return PROMPT_TEMPLATES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt_template_key: {key}") from exc


def render_prompt_payload(
    *,
    template: PromptTemplateDefinition,
    event_context: dict[str, Any],
    prompt_payload: dict[str, Any],
    base_candidates: list[dict[str, Any]],
) -> list[dict[str, str]]:
    user_payload = {
        "instructions": {
            "task": "Choose a recommendation and candidate indexes for policy validation.",
            "allowed_candidate_indexes": [item["index"] for item in base_candidates],
            "base_candidates_must_not_be_invented": True,
        },
        "event_context": event_context,
        "prompt_payload": prompt_payload,
        "base_candidates": base_candidates,
    }
    return [
        {"role": "system", "content": template.system_prompt},
        {"role": "user", "content": json.dumps(user_payload, sort_keys=True, default=str)},
    ]
