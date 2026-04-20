from __future__ import annotations

from dataclasses import dataclass

from memory_engine.control.schemas import (
    APIOntologyDefinition,
    APIOntologyEntry,
    APIOntologyModule,
    APIWorkflowDefinition,
)


@dataclass(frozen=True)
class APIOntologyCompileIssue:
    path: str
    code: str
    message: str


@dataclass(frozen=True)
class CompiledAPIOntologyPackage:
    document_name: str
    modules: list[APIOntologyModule]
    workflows: list[APIWorkflowDefinition]
    entries: list[APIOntologyEntry]
    entries_by_id: dict[str, APIOntologyEntry]
    workflows_by_key: dict[str, APIWorkflowDefinition]
    workflow_by_entry_id: dict[str, APIWorkflowDefinition]
    related_api_ids_by_entry_id: dict[str, list[str]]
    match_index: dict[tuple[str, str, str, str], APIOntologyEntry]


def _legacy_modules(definition: APIOntologyDefinition) -> list[APIOntologyModule]:
    if definition.modules:
        return definition.modules
    if definition.entries:
        return [
            APIOntologyModule(
                module_key="legacy.default",
                title="Legacy API Ontology",
                description="Implicit module created from legacy entries[] authoring.",
                entries=definition.entries,
            )
        ]
    return []


def _materialize_modules(definition: APIOntologyDefinition) -> list[APIOntologyModule]:
    modules: list[APIOntologyModule] = []
    for module in _legacy_modules(definition):
        entries = [
            entry.model_copy(
                update={
                    "entry_id": entry.entry_id or entry.api_name,
                    "module_key": module.module_key,
                }
            )
            for entry in module.entries
        ]
        modules.append(module.model_copy(update={"entries": entries}))
    return modules


def collect_api_ontology_compile_issues(definition: APIOntologyDefinition) -> list[APIOntologyCompileIssue]:
    issues: list[APIOntologyCompileIssue] = []
    modules = _materialize_modules(definition)

    module_keys: set[str] = set()
    entry_ids: set[str] = set()
    api_names: set[str] = set()
    match_keys: dict[tuple[str, str, str, str], str] = {}
    entries_by_id: dict[str, APIOntologyEntry] = {}

    for module_index, module in enumerate(modules):
        if module.module_key in module_keys:
            issues.append(
                APIOntologyCompileIssue(
                    path=f"modules.{module_index}.module_key",
                    code="api_module.duplicate",
                    message=f"Duplicate module_key: {module.module_key}",
                )
            )
        module_keys.add(module.module_key)

        for entry_index, entry in enumerate(module.entries):
            path = f"modules.{module.module_key}.entries.{entry.entry_id or entry.api_name}"
            entry_id = entry.entry_id or entry.api_name
            if entry_id in entry_ids:
                issues.append(
                    APIOntologyCompileIssue(
                        path=f"{path}.entry_id",
                        code="api_entry.duplicate_id",
                        message=f"Duplicate entry_id: {entry_id}",
                    )
                )
            entry_ids.add(entry_id)
            if entry.api_name in api_names:
                issues.append(
                    APIOntologyCompileIssue(
                        path=f"{path}.api_name",
                        code="api_entry.duplicate_api_name",
                        message=f"Duplicate api_name: {entry.api_name}",
                    )
                )
            api_names.add(entry.api_name)
            match_key = (
                entry.api_name,
                entry.event_match.source_system,
                entry.event_match.http_method.upper(),
                entry.event_match.route_template,
            )
            if match_key in match_keys:
                issues.append(
                    APIOntologyCompileIssue(
                        path=f"{path}.event_match",
                        code="api_entry.ambiguous_match",
                        message=(
                            "Ambiguous compiled API match index for "
                            f"{entry.api_name} and {match_keys[match_key]}"
                        ),
                    )
                )
            else:
                match_keys[match_key] = path
            entries_by_id[entry_id] = entry

    workflow_keys: set[str] = set()
    workflow_by_entry_id: dict[str, str] = {}
    for workflow_index, workflow in enumerate(definition.workflows):
        workflow_path = f"workflows.{workflow.workflow_key}"
        if workflow.workflow_key in workflow_keys:
            issues.append(
                APIOntologyCompileIssue(
                    path=f"{workflow_path}.workflow_key",
                    code="workflow.duplicate",
                    message=f"Duplicate workflow_key: {workflow.workflow_key}",
                )
            )
        workflow_keys.add(workflow.workflow_key)
        if not workflow.participant_entry_ids:
            issues.append(
                APIOntologyCompileIssue(
                    path=f"{workflow_path}.participant_entry_ids",
                    code="workflow.empty",
                    message=f"Workflow {workflow.workflow_key} must include at least one participant entry id.",
                )
            )
        for participant_id in workflow.participant_entry_ids:
            if participant_id not in entries_by_id:
                issues.append(
                    APIOntologyCompileIssue(
                        path=f"{workflow_path}.participant_entry_ids",
                        code="workflow.entry_missing",
                        message=f"Workflow {workflow.workflow_key} references unknown entry_id: {participant_id}",
                    )
                )
                continue
            prior = workflow_by_entry_id.get(participant_id)
            if prior and prior != workflow.workflow_key:
                issues.append(
                    APIOntologyCompileIssue(
                        path=f"{workflow_path}.participant_entry_ids",
                        code="workflow.entry_reused",
                        message=(
                            f"Entry {participant_id} is assigned to multiple workflows: {prior}, "
                            f"{workflow.workflow_key}"
                        ),
                    )
                )
            workflow_by_entry_id.setdefault(participant_id, workflow.workflow_key)
        for edge_index, edge in enumerate(workflow.relationship_edges):
            for label, entry_id in (("from_entry_id", edge.from_entry_id), ("to_entry_id", edge.to_entry_id)):
                if entry_id not in entries_by_id:
                    issues.append(
                        APIOntologyCompileIssue(
                            path=f"{workflow_path}.relationship_edges.{edge_index}.{label}",
                            code="workflow.edge_unknown_entry",
                            message=f"Workflow {workflow.workflow_key} edge references unknown entry_id: {entry_id}",
                        )
                    )
                elif entry_id not in workflow.participant_entry_ids:
                    issues.append(
                        APIOntologyCompileIssue(
                            path=f"{workflow_path}.relationship_edges.{edge_index}.{label}",
                            code="workflow.edge_outside_participant_set",
                            message=(
                                f"Workflow {workflow.workflow_key} edge references entry_id outside "
                                f"participant_entry_ids: {entry_id}"
                            ),
                        )
                    )
        for rule_index, rule in enumerate(workflow.intent_rules):
            if not rule.observed_entry_ids:
                issues.append(
                    APIOntologyCompileIssue(
                        path=f"{workflow_path}.intent_rules.{rule_index}.observed_entry_ids",
                        code="workflow.intent_rule.empty",
                        message=f"Workflow {workflow.workflow_key} intent rules must match at least one observed entry id.",
                    )
                )
            for entry_id in rule.observed_entry_ids:
                if entry_id not in entries_by_id:
                    issues.append(
                        APIOntologyCompileIssue(
                            path=f"{workflow_path}.intent_rules.{rule_index}.observed_entry_ids",
                            code="workflow.intent_rule_unknown_entry",
                            message=f"Workflow {workflow.workflow_key} intent rule references unknown entry_id: {entry_id}",
                        )
                    )
                elif entry_id not in workflow.participant_entry_ids:
                    issues.append(
                        APIOntologyCompileIssue(
                            path=f"{workflow_path}.intent_rules.{rule_index}.observed_entry_ids",
                            code="workflow.intent_rule_outside_participant_set",
                            message=(
                                f"Workflow {workflow.workflow_key} intent rule references entry_id outside "
                                f"participant_entry_ids: {entry_id}"
                            ),
                        )
                    )
    return issues


def compile_api_ontology_definition(definition: APIOntologyDefinition) -> CompiledAPIOntologyPackage:
    issues = collect_api_ontology_compile_issues(definition)
    if issues:
        first = issues[0]
        raise ValueError(f"{first.code}: {first.message}")

    modules = _materialize_modules(definition)
    entries = [entry for module in modules for entry in module.entries]
    entries_by_id = {entry.entry_id or entry.api_name: entry for entry in entries}
    workflows_by_key = {workflow.workflow_key: workflow for workflow in definition.workflows}
    workflow_by_entry_id = {
        participant_id: workflow
        for workflow in definition.workflows
        for participant_id in workflow.participant_entry_ids
    }
    related_api_ids_by_entry_id: dict[str, set[str]] = {entry_id: set() for entry_id in entries_by_id}
    for workflow in definition.workflows:
        for edge in workflow.relationship_edges:
            related_api_ids_by_entry_id.setdefault(edge.from_entry_id, set()).add(edge.to_entry_id)
            related_api_ids_by_entry_id.setdefault(edge.to_entry_id, set()).add(edge.from_entry_id)
    match_index = {
        (
            entry.api_name,
            entry.event_match.source_system,
            entry.event_match.http_method.upper(),
            entry.event_match.route_template,
        ): entry
        for entry in entries
    }
    return CompiledAPIOntologyPackage(
        document_name=definition.document_name,
        modules=modules,
        workflows=list(definition.workflows),
        entries=entries,
        entries_by_id=entries_by_id,
        workflows_by_key=workflows_by_key,
        workflow_by_entry_id=workflow_by_entry_id,
        related_api_ids_by_entry_id={
            entry_id: sorted(related_ids)
            for entry_id, related_ids in related_api_ids_by_entry_id.items()
            if related_ids
        },
        match_index=match_index,
    )
