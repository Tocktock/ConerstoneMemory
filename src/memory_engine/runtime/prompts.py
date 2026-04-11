from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplateDefinition:
    key: str
    version: str
    description: str


PROMPT_TEMPLATES: dict[str, PromptTemplateDefinition] = {
    "memory.hybrid.ingest.v1": PromptTemplateDefinition(
        key="memory.hybrid.ingest.v1",
        version="2026-04-11",
        description="Hybrid ingestion prompt for normalized API event envelopes.",
    ),
    "memory.hybrid.search.v1": PromptTemplateDefinition(
        key="memory.hybrid.search.v1",
        version="2026-04-11",
        description="Hybrid ingestion prompt tuned for ambiguous read and search behaviors.",
    ),
}


def get_prompt_template(key: str) -> PromptTemplateDefinition:
    try:
        return PROMPT_TEMPLATES[key]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt_template_key: {key}") from exc
