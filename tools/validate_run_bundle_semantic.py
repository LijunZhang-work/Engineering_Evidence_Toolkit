#!/usr/bin/env python3
"""Cross-object semantic validator for a complete RunBundle.

This module is built alongside the stable entry point and becomes active only
after its own tests pass. JSON Schema validates shape; this module validates
policy/profile bindings, references, artifacts, Provider qualification, scope,
authority, canaries, authorization, reports, and the final verdict.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("ERROR [DEPENDENCY] PyYAML is required.") from exc

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:  # pragma: no cover
    raise SystemExit("ERROR [DEPENDENCY] jsonschema is required.") from exc


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {
    "run_bundle": ROOT / "contracts/run-bundle.schema.json",
    "run_policy": ROOT / "contracts/run-policy.schema.json",
    "workspace_snapshot": ROOT / "contracts/workspace-snapshot.schema.json",
    "collaboration_snapshot": ROOT / "contracts/collaboration-snapshot.schema.json",
    "instance": ROOT / "contracts/instance-state.schema.json",
    "receipt": ROOT / "contracts/receipt.schema.json",
    "evidence": ROOT / "contracts/evidence-bundle.schema.json",
    "claim": ROOT / "contracts/claim.schema.json",
    "waiver": ROOT / "contracts/waiver.schema.json",
    "provider_adoption_decision": ROOT / "contracts/provider-adoption-decision.schema.json",
    "provider_source_receipt": ROOT / "contracts/provider-source-receipt.schema.json",
    "provider_qualification": ROOT / "contracts/provider-qualification.schema.json",
    "provider_qualification_artifact": ROOT / "contracts/provider-qualification-artifact.schema.json",
    "trusted_authority_registry": ROOT / "contracts/trusted-authority-registry.schema.json",
}
RECONCILIATION_DIMENSIONS = {
    "REVISION_PATCHSET", "TARGET", "TOOLCHAIN_FLAGS",
    "HEADERS_GENERATED_DEPENDENCIES", "FILE_SYMBOL_PATH", "DIFFERENCE_BASIS",
}
SCOPE_KEYS = ("repository_ids", "targets", "files", "symbols", "build_profile_ids")


def load_document(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle) if path.suffix.lower() == ".json" else yaml.safe_load(handle)


def canonical_content_id(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def file_content_id(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def decision_receipt_content_id(receipt: dict[str, Any]) -> str:
    payload = copy.deepcopy(receipt)
    payload.pop("content_id", None)
    return canonical_content_id(payload)


def _authority_pins_decision_receipt(
    authority: Any,
    receipt: Any,
    permission: str,
    pin_field: str,
    environment_scope: Any,
) -> bool:
    if not isinstance(authority, dict) or not isinstance(receipt, dict):
        return False
    declared_content_id = receipt.get("content_id")
    return bool(
        authority.get("status") == "ACTIVE"
        and authority.get("environment_scope") == environment_scope
        and permission in authority.get("permissions", [])
        and receipt.get("issued_by") == authority.get("issuer_id")
        and declared_content_id == decision_receipt_content_id(receipt)
        and declared_content_id in authority.get(pin_field, [])
    )


def bundle_content_id(bundle: dict[str, Any]) -> str:
    payload = copy.deepcopy(bundle)
    if isinstance(payload.get("instance"), dict):
        payload["instance"].pop("run_bundle_digest", None)
    return canonical_content_id(payload)


def _add(issues: list[str], code: str, message: str) -> None:
    issues.append(f"{code}: {message}")


def _schema_issues(label: str, value: Any, schema_path: Path) -> list[str]:
    schema = load_document(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    result: list[str] = []
    for error in sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        _add(result, f"SCHEMA_{label.upper()}", f"{location}: {error.message}")
    return result


def _index(values: Any, key: str, label: str, issues: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(values, list):
        return result
    for index, value in enumerate(values):
        if not isinstance(value, dict) or not isinstance(value.get(key), str):
            continue
        identifier = value[key]
        if identifier in result:
            _add(issues, "DUPLICATE_ID", f"{label}[{index}] duplicates {identifier}")
        else:
            result[identifier] = value
    return result


def _time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else None
    except ValueError:
        return None


def _normalise_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.replace("\\", "/")
    if raw.startswith("/") or ":" in raw.split("/")[0]:
        return None
    path = PurePosixPath(raw)
    return None if any(part in {"", ".", ".."} for part in path.parts) else path.as_posix()


def _artifact_file(location: Any, approved_roots: list[Path]) -> Path | None:
    if not isinstance(location, str) or not location.strip():
        return None
    supplied = Path(location)
    if supplied.is_absolute():
        candidate = supplied.resolve()
        return candidate if any(candidate == root or root in candidate.parents for root in approved_roots) else None
    normal = _normalise_path(location)
    if normal is None:
        return None
    candidates = [(root / normal).resolve() for root in approved_roots]
    safe = [candidate for candidate, root in zip(candidates, approved_roots) if candidate == root or root in candidate.parents]
    return next((candidate for candidate in safe if candidate.exists()), safe[0] if safe else None)


def _verify_file(
    value: Any,
    label: str,
    issues: list[str],
    cache: dict[tuple[str, str], bool],
    approved_roots: list[Path],
) -> bool:
    if not isinstance(value, dict):
        _add(issues, "ARTIFACT_INVALID", f"{label} is not an object")
        return False
    key = (str(value.get("location")), str(value.get("content_id")))
    if key in cache:
        return cache[key]
    path = _artifact_file(value.get("location"), approved_roots)
    if path is None:
        _add(issues, "ARTIFACT_PATH", f"{label} has unsafe/non-local location {value.get('location')!r}")
        cache[key] = False
        return False
    if not path.is_file():
        _add(issues, "ARTIFACT_MISSING", f"{label} does not exist: {value.get('location')}")
        cache[key] = False
        return False
    actual = file_content_id(path)
    if actual != value.get("content_id"):
        _add(issues, "ARTIFACT_DIGEST", f"{label} expected {value.get('content_id')}, actual {actual}")
        cache[key] = False
        return False
    if isinstance(value.get("size_bytes"), int) and value["size_bytes"] != path.stat().st_size:
        _add(issues, "ARTIFACT_SIZE", f"{label} has stale size_bytes")
        cache[key] = False
        return False
    cache[key] = True
    return True


def _effective(receipt: dict[str, Any]) -> bool:
    coverage = receipt.get("coverage_summary")
    return bool(
        receipt.get("receipt_type") == "EVIDENCE_CHECK"
        and receipt.get("execution_status") == "COMPLETED"
        and receipt.get("tool_qualification_status") in {"QUALIFIED", "QUALIFIED_WITH_LIMITS"}
        and receipt.get("effectiveness_status") == "EFFECTIVE_FOR_SCOPE"
        and receipt.get("inputs") and receipt.get("outputs")
        and isinstance(coverage, dict)
        and isinstance(coverage.get("expected_units"), int)
        and coverage["expected_units"] > 0
        and coverage.get("processed_units") == coverage["expected_units"]
        and coverage.get("failed_units") == 0
        and coverage.get("skipped_units") == 0
    )


def _artifact_key(value: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    return (value.get("content_id"), value.get("provenance_id"), value.get("location"), value.get("media_type"))


def _scope(value: Any) -> dict[str, set[str]]:
    if not isinstance(value, dict):
        return {key: set() for key in SCOPE_KEYS}
    return {
        key: {item for item in value.get(key, []) if isinstance(item, str)}
        if isinstance(value.get(key, []), list) else set()
        for key in SCOPE_KEYS
    }


def _scope_missing(claim: dict[str, Any], items: list[dict[str, Any]]) -> list[str]:
    required = _scope(claim.get("scope"))
    covered = {key: set() for key in SCOPE_KEYS}
    for item in items:
        for key, values in _scope(item.get("scope")).items():
            covered[key].update(values)
    return [f"{key}={sorted(values - covered[key])}" for key, values in required.items() if values - covered[key]]


def derive_custom_ceiling(policy: dict[str, Any]) -> tuple[str, str, list[str]]:
    req = policy.get("evidence_requirements", {})
    strategy = policy.get("provider_strategy", {})
    strict = (
        policy.get("enforcement") == "BLOCKING"
        and req.get("coverage_requirement") == "COMPLETE_DECLARED_SCOPE"
        and req.get("corroboration") == "REQUIRED_FOR_CRITICAL_CLAIMS"
        and req.get("minimum_independent_sources", 0) >= 2
        and req.get("high_risk_minimum_independent_sources", 0) >= 2
        and req.get("fresh_workspace_binding") is True
        and req.get("active_negative_canary") is True
    )
    if strict:
        return "FINAL_VERDICT", "ENFORCE", ["ACCEPT", "ACCEPT_WITH_RISK", "REJECT", "INCOMPLETE"]
    evidence = (
        policy.get("enforcement") in {"RISK_BASED", "BLOCKING"}
        and req.get("coverage_requirement") in {"DECLARED_SCOPE", "COMPLETE_DECLARED_SCOPE"}
        and req.get("fresh_workspace_binding") is True
        and req.get("minimum_independent_sources", 0) >= 1
    )
    return ("EVIDENCE_REPORT", "EVIDENCE", ["NO_VERDICT", "INCOMPLETE"]) if evidence else ("HINTS_ONLY", "EXPLORE", ["NO_VERDICT"])


def _task_cycle(tasks: dict[str, dict[str, Any]]) -> list[str] | None:
    active: set[str] = set()
    done: set[str] = set()

    def visit(task_id: str, chain: list[str]) -> list[str] | None:
        if task_id in active:
            return chain + [task_id]
        if task_id in done:
            return None
        active.add(task_id)
        for dependency in tasks[task_id].get("depends_on", []):
            if dependency in tasks:
                found = visit(dependency, chain + [task_id])
                if found:
                    return found
        active.remove(task_id)
        done.add(task_id)
        return None

    for task_id in tasks:
        found = visit(task_id, [])
        if found:
            return found
    return None


def _allowed(path: str, rules: list[str]) -> bool:
    for rule in rules:
        normal = _normalise_path(rule)
        if normal is None:
            continue
        if any(char in normal for char in "*?[") and fnmatch.fnmatchcase(path, normal):
            return True
        if path == normal or path.startswith(normal.rstrip("/") + "/"):
            return True
    return False


def report_facts(bundle: dict[str, Any]) -> dict[str, Any]:
    instance = bundle.get("instance", {})
    workspace = bundle.get("workspace_snapshot", {})
    limitations = set(workspace.get("limitations", [])) if isinstance(workspace, dict) else set()
    for section in ("evidence", "provider_qualifications"):
        for item in bundle.get(section, []):
            if isinstance(item, dict):
                limitations.update(item.get("limitations", []))
    claims = [
        {"claim_id": item.get("claim_id"), "status": item.get("claim_status"), "required": item.get("required_for_verdict")}
        for item in instance.get("claims", []) if isinstance(item, dict)
    ]
    gates = [
        {
            "gate_id": item.get("gate_id"),
            "status": item.get("gate_status"),
            "claim_refs": sorted(item.get("claim_refs", [])),
            "evidence_refs": sorted(item.get("evidence_refs", [])),
        }
        for item in instance.get("gates", []) if isinstance(item, dict)
    ]
    failures = [
        {"failure_id": item.get("failure_id"), "status": item.get("applicability_status"), "evidence_ref": item.get("evidence_ref")}
        for item in instance.get("external_failures", []) if isinstance(item, dict)
    ]
    return {
        "run_id": instance.get("run_id"),
        "workspace_snapshot_id": workspace.get("snapshot_id"),
        "final_verdict": instance.get("final_verdict"),
        "claims": sorted(claims, key=lambda item: str(item["claim_id"])),
        "gates": sorted(gates, key=lambda item: str(item["gate_id"])),
        "external_failures": sorted(failures, key=lambda item: str(item["failure_id"])),
        "limitations": sorted(item for item in limitations if isinstance(item, str)),
    }


def validate_run_bundle(
    bundle: Any,
    artifact_roots: list[Path] | None = None,
    *,
    authority_registry_path: Path | None = None,
    expected_authority_registry_content_id: str | None = None,
) -> list[str]:
    issues: list[str] = []
    file_cache: dict[tuple[str, str], bool] = {}
    approved_roots = [path.resolve() for path in (artifact_roots or [])]
    if ROOT.resolve() not in approved_roots:
        approved_roots.append(ROOT.resolve())
    registry_path = (authority_registry_path or (ROOT / "governance/TRUSTED_AUTHORITY_REGISTRY.yaml")).resolve()
    if not registry_path.is_file():
        _add(issues, "AUTHORITY_REGISTRY_SOURCE", f"registry file does not exist: {registry_path}")
    registry = load_document(registry_path) if registry_path.is_file() else {}
    issues.extend(_schema_issues("trusted_authority_registry", registry, SCHEMAS["trusted_authority_registry"]))
    authority_registry = _index(
        registry.get("authorities", []) if isinstance(registry, dict) else [],
        "authority_ref",
        "trusted_authority_registry.authorities",
        issues,
    )
    allowed_provider_source_schemes = set(
        registry.get("allowed_provider_source_schemes", []) if isinstance(registry, dict) else []
    )
    issues.extend(_schema_issues("run_bundle", bundle, SCHEMAS["run_bundle"]))
    if not isinstance(bundle, dict):
        return sorted(set(issues))
    trust_context = bundle.get("trust_context") if isinstance(bundle.get("trust_context"), dict) else {}
    registry_content_id = canonical_content_id(registry) if isinstance(registry, dict) else None
    if expected_authority_registry_content_id is None:
        _add(
            issues,
            "AUTHORITY_REGISTRY_TRUST_ANCHOR",
            "an out-of-band expected registry content_id is required; the Bundle and Registry cannot anchor each other",
        )
    elif expected_authority_registry_content_id != registry_content_id:
        _add(
            issues,
            "AUTHORITY_REGISTRY_TRUST_ANCHOR",
            f"external={expected_authority_registry_content_id}, actual={registry_content_id}",
        )
    if trust_context.get("authority_registry_content_id") != registry_content_id:
        _add(
            issues,
            "AUTHORITY_REGISTRY_BINDING",
            f"stored={trust_context.get('authority_registry_content_id')}, current={registry_content_id}",
        )
    bundle_environment_scope = trust_context.get("environment_scope")

    def authority_allows(authority_ref: Any, permission: str) -> bool:
        authority = authority_registry.get(authority_ref)
        return bool(
            isinstance(authority, dict)
            and authority.get("status") == "ACTIVE"
            and authority.get("environment_scope") == bundle_environment_scope
            and permission in authority.get("permissions", [])
        )

    def authority_pins_decision_receipt(receipt: Any, permission: str, pin_field: str) -> bool:
        if not isinstance(receipt, dict):
            return False
        decision = receipt.get("decision") if isinstance(receipt.get("decision"), dict) else {}
        authority = authority_registry.get(decision.get("authority_ref"))
        return _authority_pins_decision_receipt(
            authority,
            receipt,
            permission,
            pin_field,
            bundle_environment_scope,
        )

    for section, schema_name in {
        "run_policy": "run_policy",
        "workspace_snapshot": "workspace_snapshot",
        "baseline_workspace_snapshot": "workspace_snapshot",
        "collaboration_snapshot": "collaboration_snapshot",
        "instance": "instance",
    }.items():
        if section in bundle:
            issues.extend(_schema_issues(section, bundle[section], SCHEMAS[schema_name]))
    for section, schema_name in {
        "receipts": "receipt",
        "evidence": "evidence",
        "claims": "claim",
        "waivers": "waiver",
        "provider_adoption_decisions": "provider_adoption_decision",
        "provider_qualifications": "provider_qualification",
    }.items():
        if isinstance(bundle.get(section), list):
            for index, value in enumerate(bundle[section]):
                for issue in _schema_issues(schema_name, value, SCHEMAS[schema_name]):
                    issues.append(f"{issue} ({section}[{index}])")

    policy = bundle.get("run_policy")
    workspace = bundle.get("workspace_snapshot")
    instance = bundle.get("instance")
    if not isinstance(policy, dict) or not isinstance(workspace, dict) or not isinstance(instance, dict):
        return sorted(set(issues))

    receipts = _index(bundle.get("receipts"), "receipt_id", "receipts", issues)
    evidence = _index(bundle.get("evidence"), "evidence_id", "evidence", issues)
    claims = _index(bundle.get("claims"), "claim_id", "claims", issues)
    waivers = _index(bundle.get("waivers"), "waiver_id", "waivers", issues)
    decisions = _index(bundle.get("provider_adoption_decisions", []), "decision_id", "provider_adoption_decisions", issues)
    qualifications = _index(bundle.get("provider_qualifications", []), "qualification_id", "provider_qualifications", issues)
    reports = _index(bundle.get("reports", []), "report_id", "reports", issues)
    tasks = _index(instance.get("tasks"), "task_id", "instance.tasks", issues)
    gates = _index(instance.get("gates"), "gate_id", "instance.gates", issues)
    failures = _index(instance.get("external_failures"), "failure_id", "instance.external_failures", issues)
    summaries = _index(instance.get("claims"), "claim_id", "instance.claims", issues)
    run_id = instance.get("run_id")
    workspace_id = workspace.get("snapshot_id")
    workspace_content_id = workspace.get("content_id")
    verdict_time = _time(instance.get("updated_at"))

    # A named policy is byte-for-byte canonical after parsing. Any edit must use
    # CUSTOM and accept a rederived authority ceiling.
    binding = instance.get("assurance_policy") if isinstance(instance.get("assurance_policy"), dict) else {}
    for left, right in {"policy_id": "id", "version": "version", "preset": "preset", "outcome_authority": "outcome_authority"}.items():
        if binding.get(left) != policy.get(right):
            _add(issues, "POLICY_BINDING", f"instance.assurance_policy.{left} differs from run_policy.{right}")
    policy_digest = canonical_content_id(policy)
    if binding.get("policy_content_id") != policy_digest:
        _add(issues, "POLICY_BINDING", f"policy_content_id expected {policy_digest}")
    if instance.get("mode") != policy.get("mode"):
        _add(issues, "POLICY_BINDING", "instance.mode differs from run_policy.mode")
    if instance.get("final_verdict") not in policy.get("allowed_final_verdicts", []):
        _add(issues, "POLICY_VERDICT_CEILING", f"{policy.get('id')} does not allow {instance.get('final_verdict')}")
    if policy.get("preset") == "CUSTOM":
        actual = (policy.get("outcome_authority"), policy.get("mode"), policy.get("allowed_final_verdicts"))
        if actual != derive_custom_ceiling(policy):
            _add(issues, "CUSTOM_POLICY_OVERCLAIM", f"stored={actual!r}, derived={derive_custom_ceiling(policy)!r}")
        base_path = ROOT / "policies" / f"{str(policy.get('base_preset')).lower()}.yaml"
        if not base_path.is_file() or policy.get("base_policy_content_id") != canonical_content_id(load_document(base_path)):
            _add(issues, "CUSTOM_POLICY_BASE", "base_policy_content_id does not bind the canonical preset")
    else:
        policy_path = ROOT / "policies" / f"{policy.get('id')}.yaml"
        if not policy_path.is_file() or load_document(policy_path) != policy:
            _add(issues, "PRESET_POLICY_DRIFT", f"{policy.get('preset')} differs from its canonical policy")
    if instance.get("workspace_snapshot_id") != workspace_id:
        _add(issues, "WORKSPACE_BINDING", "instance references another Workspace Snapshot")

    # Workspace manifest and typed nested references.
    repositories = _index(workspace.get("repositories"), "repository_id", "workspace.repositories", issues)
    build_context = workspace.get("build_context") if isinstance(workspace.get("build_context"), dict) else {}
    build_profiles = _index(build_context.get("profiles"), "profile_id", "workspace.build_context.profiles", issues)
    if build_context.get("authoritative_profile_id") is not None and build_context.get("authoritative_profile_id") not in build_profiles:
        _add(issues, "WORKSPACE_PROFILE_REF", f"unknown authoritative profile {build_context.get('authoritative_profile_id')}")
    manifest = workspace.get("file_manifest") if isinstance(workspace.get("file_manifest"), dict) else {}
    file_entries: dict[tuple[Any, Any], dict[str, Any]] = {}
    for index, entry in enumerate(manifest.get("entries", []) if isinstance(manifest.get("entries"), list) else []):
        if not isinstance(entry, dict):
            continue
        key = (entry.get("repository_id"), entry.get("path"))
        if key in file_entries:
            _add(issues, "DUPLICATE_ID", f"workspace.file_manifest.entries[{index}] duplicates {key}")
        file_entries[key] = entry
        if entry.get("repository_id") not in repositories:
            _add(issues, "WORKSPACE_FILE_REPO_REF", f"file entry references {entry.get('repository_id')}")
        if _normalise_path(entry.get("path")) is None:
            _add(issues, "WORKSPACE_FILE_PATH", f"unsafe manifest path {entry.get('path')!r}")
    if manifest.get("expected_units") != len(file_entries):
        _add(issues, "WORKSPACE_FILE_MANIFEST", "expected_units differs from unique file entry count")
    manifest_payload = {"expected_units": manifest.get("expected_units"), "entries": manifest.get("entries", [])}
    if manifest.get("content_id") != canonical_content_id(manifest_payload):
        _add(issues, "WORKSPACE_FILE_MANIFEST", "content_id does not bind the canonical file manifest")

    # Optional Profile: if present, bind the exact contract and close the full
    # task/Gate set. An inactive design Profile cannot drive ENFORCE.
    profile_binding = instance.get("profile")
    profile_authoritative = False
    if isinstance(profile_binding, dict):
        profile_path = ROOT / "profiles" / str(profile_binding.get("profile_id")) / "PROFILE.yaml"
        if not profile_path.is_file():
            _add(issues, "PROFILE_BINDING", f"missing Profile {profile_binding.get('profile_id')}")
        else:
            profile = load_document(profile_path)
            profile_binding_exact = (
                profile.get("version") == profile_binding.get("version")
                and canonical_content_id(profile) == profile_binding.get("profile_content_id")
            )
            if not profile_binding_exact:
                _add(issues, "PROFILE_BINDING", "Profile version/content binding is stale")
            required_caps = profile.get("capabilities", {}).get("required", [])
            expected_ids = set()
            for capability_id in required_caps:
                path = ROOT / "capabilities" / str(capability_id) / "CAPABILITY.yaml"
                if path.is_file():
                    expected_ids.add(canonical_content_id(load_document(path)))
                else:
                    _add(issues, "PROFILE_CAPABILITY_BINDING", f"missing Capability {capability_id}")
            capabilities_exact = set(profile_binding.get("capability_contract_content_ids", [])) == expected_ids
            if not capabilities_exact:
                _add(issues, "PROFILE_CAPABILITY_BINDING", "Capability contract content-id set is stale/incomplete")
            task_caps = {task.get("capability_id") for task in tasks.values()}
            tasks_closed = set(required_caps).issubset(task_caps)
            if not tasks_closed:
                _add(issues, "PROFILE_TASK_CLOSURE", f"missing tasks {sorted(set(required_caps) - task_caps)}")
            gates_closed = set(profile.get("gates", [])).issubset(gates)
            if not gates_closed:
                _add(issues, "PROFILE_GATE_CLOSURE", f"missing Gates {sorted(set(profile.get('gates', [])) - set(gates))}")
            dimensions = profile.get("status_dimensions", {})
            active = (
                dimensions.get("implementation_status") == "IMPLEMENTED"
                and dimensions.get("validation_status") == "PASSED"
                and dimensions.get("qualification_status") == "QUALIFIED"
                and dimensions.get("activation_status") == "ACTIVE"
            )
            if policy.get("mode") == "ENFORCE" and instance.get("execution_status") == "COMPLETED" and not active:
                _add(issues, "PROFILE_NOT_ACTIVE", f"{profile.get('id')} is not implemented, validated, qualified and active")
            profile_authoritative = bool(
                profile_binding_exact and capabilities_exact and tasks_closed and gates_closed and active
            )

    # Collaboration Snapshot cannot be overwritten by an optimistic summary.
    collaboration_incomplete = False
    collaboration = bundle.get("collaboration_snapshot")
    if isinstance(collaboration, dict):
        if collaboration.get("workspace_snapshot_id") != workspace_id:
            _add(issues, "WORKSPACE_BINDING", "Collaboration Snapshot references another workspace")
        if instance.get("collaboration_snapshot_id") != collaboration.get("snapshot_id"):
            _add(issues, "COLLABORATION_BINDING", "instance collaboration reference is stale")
        if instance.get("collaboration_readiness") != collaboration.get("readiness"):
            _add(issues, "COLLABORATION_DRIFT", "instance readiness differs from Collaboration Snapshot")
        components = _index(collaboration.get("components"), "component_id", "collaboration.components", issues)
        for component_id, component in components.items():
            if component.get("repository_id") is not None and component.get("repository_id") not in repositories:
                _add(issues, "COLLABORATION_REPO_REF", f"{component_id} references unknown repository")
            if component.get("expected_in_snapshot") is True and component.get("code_availability") != "PRESENT":
                collaboration_incomplete = True
        collaboration_incomplete |= collaboration.get("readiness") != "ALL_EXPECTED_CODE_PRESENT"
    elif instance.get("collaboration_snapshot_id") is not None:
        _add(issues, "COLLABORATION_BINDING", "instance references a missing Collaboration Snapshot")

    # Adopt -> Adapt -> Build decision integrity.
    valid_decisions: set[str] = set()
    decision_selections: dict[str, dict[str, Any]] = {}
    all_fact_refs = set(receipts) | set(evidence)
    for decision_id, decision in decisions.items():
        candidates = _index(decision.get("candidates"), "candidate_id", f"{decision_id}.candidates", issues)
        action = decision.get("selected_action")
        selected_id = decision.get("selected_candidate_id")
        selected = candidates.get(selected_id)
        valid = True
        for candidate_id, candidate in candidates.items():
            source_scheme = urlsplit(str(candidate.get("source_identity", ""))).scheme.lower()
            if source_scheme not in allowed_provider_source_schemes:
                _add(
                    issues,
                    "PROVIDER_DECISION_SOURCE",
                    f"{decision_id}.{candidate_id} uses untrusted source scheme {source_scheme!r}",
                )
                valid = False
            source_ref = candidate.get("source_receipt")
            source_path = None
            if _verify_file(
                source_ref,
                f"{decision_id}.{candidate_id}.source_receipt",
                issues,
                file_cache,
                approved_roots,
            ):
                source_path = _artifact_file(source_ref.get("location"), approved_roots)
            source_receipt: Any = None
            if source_path is not None:
                try:
                    source_receipt = load_document(source_path)
                except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
                    _add(issues, "PROVIDER_SOURCE_RECEIPT", f"{decision_id}.{candidate_id} cannot parse source receipt: {exc}")
            if isinstance(source_receipt, dict):
                for issue in _schema_issues("provider_source_receipt", source_receipt, SCHEMAS["provider_source_receipt"]):
                    issues.append(f"{issue} ({decision_id}.{candidate_id})")
                authority = authority_registry.get(source_receipt.get("authority_ref"))
                source_bound = bool(
                    isinstance(authority, dict)
                    and authority.get("status") == "ACTIVE"
                    and authority.get("environment_scope") == bundle_environment_scope
                    and "PROVIDER_SOURCE_ATTESTATION" in authority.get("permissions", [])
                    and authority.get("issuer_id") == source_receipt.get("issued_by")
                    and decision.get("capability_id") == source_receipt.get("capability_id")
                    and candidate_id == source_receipt.get("provider_id")
                    and candidate.get("source_identity") == source_receipt.get("source_identity")
                    and candidate.get("immutable_revision") == source_receipt.get("resolved_revision")
                    and candidate.get("provider_artifact_content_id") == source_receipt.get("provider_artifact_content_id")
                    and source_ref.get("content_id") in authority.get("provider_source_receipt_content_ids", [])
                )
                license_ref = source_receipt.get("license", {}).get("artifact") if isinstance(source_receipt.get("license"), dict) else None
                license_bound = _verify_file(
                    license_ref,
                    f"{decision_id}.{candidate_id}.source_receipt.license",
                    issues,
                    file_cache,
                    approved_roots,
                )
                if not source_bound or not license_bound:
                    _add(issues, "PROVIDER_SOURCE_RECEIPT", f"{decision_id}.{candidate_id} source receipt is not authority-pinned and artifact-bound")
                    valid = False
            else:
                _add(issues, "PROVIDER_SOURCE_RECEIPT", f"{decision_id}.{candidate_id} lacks a parseable typed source receipt")
                valid = False
        if action in {"ADOPT", "ADAPT", "BUILD"}:
            if selected is None:
                _add(issues, "PROVIDER_DECISION_SELECTION", f"{decision_id} selected candidate is absent")
                valid = False
            else:
                if selected.get("disposition") != "SELECTED":
                    _add(issues, "PROVIDER_DECISION_SELECTION", f"{decision_id} selected candidate is REJECTED/DEFERRED")
                    valid = False
                if selected.get("license_status") != "ACCEPTABLE":
                    _add(issues, "PROVIDER_DECISION_LICENSE", f"{decision_id} selected license is not ACCEPTABLE")
                    valid = False
                immutable_revision = str(selected.get("immutable_revision", ""))
                provider_artifact_digest = str(selected.get("provider_artifact_content_id", "")).partition(":")[2]
                if (
                    not re.search(r"(?<![A-Fa-f0-9])[A-Fa-f0-9]{40,64}(?![A-Fa-f0-9])", immutable_revision)
                    or not provider_artifact_digest
                    or provider_artifact_digest.lower() not in immutable_revision.lower()
                ):
                    _add(issues, "PROVIDER_DECISION_REVISION", f"{decision_id} lacks a content-addressed immutable_revision")
                    valid = False
                expected_fit = {"ADOPT": "DIRECT", "ADAPT": "ADAPTER_REQUIRED"}.get(action)
                if expected_fit and selected.get("fit") != expected_fit:
                    _add(issues, "PROVIDER_DECISION_ORDER", f"{decision_id} {action} requires fit={expected_fit}")
                    valid = False
                if selected.get("decision_layer") != action:
                    _add(issues, "PROVIDER_DECISION_ORDER", f"{decision_id} selected candidate is not in the {action} layer")
                    valid = False
        expected_selected_count = 0 if action == "NO_SELECTION" else 1
        if sum(item.get("disposition") == "SELECTED" for item in candidates.values()) != expected_selected_count:
            _add(issues, "PROVIDER_DECISION_SELECTION", f"{decision_id} has contradictory dispositions")
            valid = False
        action_rank = {"ADOPT": 0, "ADAPT": 1, "BUILD": 2}
        if action in action_rank:
            earlier = [
                item
                for key, item in candidates.items()
                if key != selected_id
                and action_rank.get(item.get("decision_layer"), 99) < action_rank[action]
            ]
            invalid_earlier = [
                item.get("candidate_id")
                for item in earlier
                if item.get("disposition") != "REJECTED"
                or not isinstance(item.get("rejection_reason"), str)
                or not item.get("rejection_reason", "").strip()
                or not item.get("evidence_refs")
            ]
            if invalid_earlier:
                _add(
                    issues,
                    "PROVIDER_DECISION_ORDER",
                    f"{decision_id} {action} has earlier-layer candidates without evidenced rejection: {invalid_earlier}",
                )
                valid = False
        refs = list(decision.get("evidence_refs", []))
        for candidate in candidates.values():
            refs.extend(candidate.get("evidence_refs", []))
        missing_refs = sorted({ref for ref in refs if isinstance(ref, str) and ref not in all_fact_refs})
        if missing_refs:
            _add(issues, "PROVIDER_DECISION_EVIDENCE_REF", f"{decision_id} has unknown refs {missing_refs}")
            valid = False
        def relevant_provider_fact(ref: str, candidate: dict[str, Any] | None) -> bool:
            if not isinstance(candidate, dict):
                return False
            expected = (
                decision.get("capability_id"),
                candidate.get("candidate_id"),
                candidate.get("provider_artifact_content_id"),
            )
            receipt = receipts.get(ref)
            if isinstance(receipt, dict):
                provider = receipt.get("provider") if isinstance(receipt.get("provider"), dict) else {}
                return (
                    receipt.get("capability_id"),
                    provider.get("provider_id"),
                    provider.get("artifact_content_id"),
                ) == expected
            evidence_item = evidence.get(ref)
            if isinstance(evidence_item, dict):
                capability = evidence_item.get("capability") if isinstance(evidence_item.get("capability"), dict) else {}
                if (
                    capability.get("capability_id") != expected[0]
                    or capability.get("provider_id") != expected[1]
                ):
                    return False
                return any(relevant_provider_fact(receipt_ref, candidate) for receipt_ref in evidence_item.get("receipt_refs", []))
            return False

        for candidate_id, candidate in candidates.items():
            irrelevant = [
                ref for ref in candidate.get("evidence_refs", [])
                if isinstance(ref, str) and ref in all_fact_refs and not relevant_provider_fact(ref, candidate)
            ]
            if irrelevant:
                _add(
                    issues,
                    "PROVIDER_DECISION_EVIDENCE_RELEVANCE",
                    f"{decision_id}.{candidate_id} has unrelated evidence {irrelevant}",
                )
                valid = False
        decision_refs = [ref for ref in decision.get("evidence_refs", []) if isinstance(ref, str)]
        relevant_decision_refs = [ref for ref in decision_refs if relevant_provider_fact(ref, selected)]
        if action != "NO_SELECTION" and (not relevant_decision_refs or len(relevant_decision_refs) != len(decision_refs)):
            _add(
                issues,
                "PROVIDER_DECISION_EVIDENCE_RELEVANCE",
                f"{decision_id} decision evidence is missing or unrelated to the selected Provider artifact",
            )
            valid = False
        if action != "NO_SELECTION" and decision.get("gate_result") != "PASS":
            _add(issues, "PROVIDER_DECISION_GATE", f"{decision_id} selection has gate_result {decision.get('gate_result')}")
            valid = False
        if valid:
            valid_decisions.add(decision_id)
            if isinstance(selected, dict):
                decision_selections[decision_id] = selected

    # Provider qualification is an independent, expiring object, not a Receipt
    # enum. It binds the exact Provider artifact and a real qualification file.
    valid_qualifications: set[str] = set()
    qualification_details: dict[str, dict[str, Any]] = {}
    for qualification_id, qualification in qualifications.items():
        valid = True
        decision = decisions.get(qualification.get("decision_ref"))
        selected = decision_selections.get(qualification.get("decision_ref"))
        if qualification.get("decision_ref") not in valid_decisions or not isinstance(decision, dict):
            _add(issues, "QUALIFICATION_DECISION_REF", f"{qualification_id} lacks a valid adoption decision")
            valid = False
        elif (
            decision.get("capability_id") != qualification.get("capability_id")
            or decision.get("selected_candidate_id") != qualification.get("provider_id")
            or not isinstance(selected, dict)
            or selected.get("provider_artifact_content_id") != qualification.get("provider_artifact_content_id")
        ):
            _add(issues, "QUALIFICATION_DECISION_REF", f"{qualification_id} provider/capability/artifact differs from decision")
            valid = False
        if qualification.get("qualified_by") == qualification.get("provider_id"):
            _add(issues, "QUALIFICATION_SELF_ISSUED", f"{qualification_id} is self-issued")
            valid = False
        issued = _time(qualification.get("issued_at"))
        expires = _time(qualification.get("expires_at"))
        if issued is None or expires is None or issued >= expires or (verdict_time is not None and not (issued <= verdict_time < expires)):
            _add(issues, "QUALIFICATION_EXPIRED", f"{qualification_id} is invalid at verdict time")
            valid = False
        if qualification.get("status") != "QUALIFIED":
            _add(issues, "QUALIFICATION_STATUS", f"{qualification_id} is {qualification.get('status')}")
            valid = False
        authority = authority_registry.get(qualification.get("authority_ref"))
        if (
            not isinstance(authority, dict)
            or authority.get("status") != "ACTIVE"
            or authority.get("environment_scope") != bundle_environment_scope
            or "PROVIDER_QUALIFICATION" not in authority.get("permissions", [])
            or authority.get("issuer_id") != qualification.get("qualified_by")
            or qualification.get("authority_tier") not in authority.get("authority_tiers", [])
            or qualification.get("capability_id") not in authority.get("capability_ids", [])
        ):
            _add(issues, "QUALIFICATION_UNTRUSTED_AUTHORITY", f"{qualification_id} is not issued by an active scoped authority")
            valid = False
        trust_domains = _index(
            authority.get("trust_domains", []) if isinstance(authority, dict) else [],
            "trust_domain_id",
            f"{qualification_id}.authority.trust_domains",
            issues,
        )
        trust_domain = trust_domains.get(qualification.get("trust_domain_id"))
        if (
            not isinstance(trust_domain, dict)
            or qualification.get("provider_id") not in trust_domain.get("provider_ids", [])
            or qualification.get("provider_artifact_content_id") not in trust_domain.get("provider_artifact_content_ids", [])
        ):
            _add(issues, "QUALIFICATION_TRUST_DOMAIN", f"{qualification_id} Provider artifact is not pinned in its trust domain")
            valid = False
        artifact_ref = qualification.get("qualification_artifact")
        artifact_ok = _verify_file(
            artifact_ref,
            f"qualification {qualification_id}",
            issues,
            file_cache,
            approved_roots,
        )
        if not artifact_ok:
            valid = False
        else:
            artifact_path = _artifact_file(artifact_ref.get("location"), approved_roots) if isinstance(artifact_ref, dict) else None
            try:
                artifact_document = load_document(artifact_path) if artifact_path is not None else None
            except Exception as exc:
                artifact_document = None
                _add(issues, "QUALIFICATION_ARTIFACT_SEMANTICS", f"{qualification_id} cannot be parsed: {exc}")
            if isinstance(artifact_document, dict):
                artifact_schema_issues = _schema_issues(
                    "provider_qualification_artifact",
                    artifact_document,
                    SCHEMAS["provider_qualification_artifact"],
                )
                for issue in artifact_schema_issues:
                    issues.append(f"{issue} ({qualification_id})")
                if artifact_schema_issues:
                    valid = False
                expected_artifact = {
                    "qualification_id": qualification_id,
                    "authority_ref": qualification.get("authority_ref"),
                    "qualified_by": qualification.get("qualified_by"),
                    "authority_tier": qualification.get("authority_tier"),
                    "capability_id": qualification.get("capability_id"),
                    "provider_id": qualification.get("provider_id"),
                    "provider_version": qualification.get("provider_version"),
                    "provider_artifact_content_id": qualification.get("provider_artifact_content_id"),
                    "trust_domain_id": qualification.get("trust_domain_id"),
                    "decision_ref": qualification.get("decision_ref"),
                    "result": qualification.get("status"),
                }
                drift = sorted(key for key, value in expected_artifact.items() if artifact_document.get(key) != value)
                if drift:
                    _add(
                        issues,
                        "QUALIFICATION_ARTIFACT_SEMANTICS",
                        f"{qualification_id} artifact differs in {drift}",
                    )
                    valid = False
            else:
                _add(issues, "QUALIFICATION_ARTIFACT_SEMANTICS", f"{qualification_id} artifact is not an object")
                valid = False
        if valid:
            valid_qualifications.add(qualification_id)
            qualification_details[qualification_id] = {
                "authority_tier": qualification.get("authority_tier"),
                "trust_domain_id": qualification.get("trust_domain_id"),
                "provider_artifact_content_id": qualification.get("provider_artifact_content_id"),
            }

    # Runtime Receipts bind the current run/snapshot, independent qualification,
    # real local I/O, and active negative/control Canary artifacts.
    for receipt_id, receipt in receipts.items():
        if receipt.get("run_id") != run_id:
            _add(issues, "RUN_BINDING", f"{receipt_id} belongs to another run")
        if receipt.get("workspace_snapshot_id") is not None and receipt.get("workspace_snapshot_id") != workspace_id and receipt.get("receipt_type") != "AUTHORIZATION":
            _add(issues, "WORKSPACE_BINDING", f"{receipt_id} belongs to another workspace")
        if _time(receipt.get("started_at")) and _time(receipt.get("ended_at")) and _time(receipt.get("started_at")) > _time(receipt.get("ended_at")):
            _add(issues, "RECEIPT_TIME", f"{receipt_id} starts after it ends")
        if receipt.get("receipt_type") != "EVIDENCE_CHECK":
            continue
        if receipt.get("effectiveness_status") == "EFFECTIVE_FOR_SCOPE" and not _effective(receipt):
            _add(issues, "RECEIPT_FALSE_EFFECTIVE", f"{receipt_id} has empty/incomplete I/O coverage")
        provider = receipt.get("provider") if isinstance(receipt.get("provider"), dict) else {}
        qualification = qualifications.get(provider.get("qualification_ref"))
        if provider.get("qualification_ref") not in valid_qualifications or not isinstance(qualification, dict):
            _add(issues, "RECEIPT_QUALIFICATION_REF", f"{receipt_id} has no valid Provider Qualification")
        else:
            receipt_identity = (receipt.get("capability_id"), provider.get("provider_id"), provider.get("version"), provider.get("artifact_content_id"))
            qualification_identity = (
                qualification.get("capability_id"), qualification.get("provider_id"),
                qualification.get("provider_version"), qualification.get("provider_artifact_content_id"),
            )
            if receipt_identity != qualification_identity:
                _add(issues, "RECEIPT_QUALIFICATION_REF", f"{receipt_id} differs from its Qualification")
        if policy.get("mode") == "ENFORCE" and _effective(receipt):
            for collection in ("inputs", "outputs"):
                seen: set[tuple[Any, ...]] = set()
                for index, item in enumerate(receipt.get(collection, [])):
                    if not isinstance(item, dict):
                        continue
                    key = _artifact_key(item)
                    if key in seen:
                        _add(issues, "RECEIPT_DUPLICATE_ARTIFACT", f"{receipt_id}.{collection}[{index}] duplicates an artifact")
                    seen.add(key)
                    _verify_file(item, f"{receipt_id}.{collection}[{index}]", issues, file_cache, approved_roots)
            canary = receipt.get("canary")
            if isinstance(canary, dict):
                negatives = {item.get("content_id") for item in receipt.get("inputs", []) if isinstance(item, dict) and item.get("role") == "CANARY_NEGATIVE"}
                controls = {item.get("content_id") for item in receipt.get("inputs", []) if isinstance(item, dict) and item.get("role") == "CANARY_CONTROL"}
                results = {item.get("content_id") for item in receipt.get("outputs", []) if isinstance(item, dict) and item.get("role") == "CANARY_RESULT"}
                if (
                    canary.get("status") != "PASS"
                    or canary.get("negative_input_content_id") not in negatives
                    or canary.get("control_input_content_id") not in controls
                    or canary.get("result_artifact_content_id") not in results
                ):
                    _add(issues, "CANARY_INVALID", f"{receipt_id} Canary does not bind negative/control/result artifacts")

    # Task references and dependency DAG.
    for task_id, task in tasks.items():
        for dependency in task.get("depends_on", []):
            if dependency not in tasks:
                _add(issues, "TASK_DEPENDENCY_REF", f"{task_id} depends on unknown {dependency}")
        receipt_refs = task.get("receipt_refs", [])
        for ref in receipt_refs:
            if ref not in receipts or receipts[ref].get("capability_id") != task.get("capability_id"):
                _add(issues, "TASK_RECEIPT_REF", f"{task_id} has missing/mismatched Receipt {ref}")
        if task.get("execution_status") == "COMPLETED" and task.get("required_for_verdict") is True and not receipt_refs:
            _add(issues, "TASK_RECEIPT_REF", f"{task_id} completed without a Receipt")
    cycle = _task_cycle(tasks)
    if cycle:
        _add(issues, "TASK_DEPENDENCY_CYCLE", " -> ".join(cycle))
    wait = instance.get("wait_state") if isinstance(instance.get("wait_state"), dict) else {}
    for ref in wait.get("diagnostic_receipt_refs", []):
        if ref not in receipts:
            _add(issues, "WAIT_RECEIPT_REF", f"unknown diagnostic Receipt {ref}")
    for task_id in wait.get("continueable_task_ids", []):
        if task_id not in tasks:
            _add(issues, "WAIT_TASK_REF", f"unknown continueable Task {task_id}")

    # Evidence is proof only when its Provider/Capability, Receipt output,
    # current snapshot, qualification, named coverage and Canary all agree.
    requirements = policy.get("evidence_requirements", {})
    strict_proof: dict[str, bool] = {}
    evidence_lineages: dict[str, set[tuple[Any, ...]]] = {}
    evidence_authority_tiers: dict[str, set[str]] = {}
    for evidence_id, item in evidence.items():
        if item.get("claim_id") not in claims:
            _add(issues, "EVIDENCE_CLAIM_REF", f"{evidence_id} references unknown Claim")
        if item.get("workspace_snapshot_id") != workspace_id:
            _add(issues, "WORKSPACE_BINDING", f"{evidence_id} belongs to another workspace")
        if item.get("mode") != policy.get("mode"):
            _add(issues, "POLICY_BINDING", f"{evidence_id}.mode differs from policy")
        receipt_refs = item.get("receipt_refs", [])
        missing = [ref for ref in receipt_refs if ref not in receipts]
        if missing:
            _add(issues, "EVIDENCE_RECEIPT_REF", f"{evidence_id} missing Receipts {missing}")
        capability = item.get("capability") if isinstance(item.get("capability"), dict) else {}
        matching: list[tuple[str, dict[str, Any]]] = []
        for ref in receipt_refs:
            receipt = receipts.get(ref)
            provider = receipt.get("provider") if isinstance(receipt, dict) and isinstance(receipt.get("provider"), dict) else {}
            if isinstance(receipt, dict) and (
                receipt.get("capability_id") == capability.get("capability_id")
                and provider.get("provider_id") == capability.get("provider_id")
                and provider.get("version") == capability.get("provider_version")
                and receipt.get("workspace_snapshot_id") == workspace_id
                and _effective(receipt)
            ):
                matching.append((ref, receipt))
        if item.get("verification_status") == "verified" and not matching:
            _add(issues, "EVIDENCE_FALSE_VERIFIED", f"{evidence_id} has no matching effective Receipt")
        coverage = item.get("coverage") if isinstance(item.get("coverage"), dict) else {}
        if item.get("coverage_status") == "complete" and coverage.get("expected_units") != coverage.get("covered_units"):
            _add(issues, "EVIDENCE_FALSE_COMPLETE", f"{evidence_id} does not cover all expected units")
        scope_files = _scope(item.get("scope"))["files"]
        scope_repositories = _scope(item.get("scope"))["repository_ids"]
        expected_input_ids = {
            entry.get("content_id")
            for (repository_id, path), entry in file_entries.items()
            if path in scope_files and (not scope_repositories or repository_id in scope_repositories)
        }
        target_input_ids = {
            input_artifact.get("content_id")
            for _, receipt in matching
            for input_artifact in receipt.get("inputs", [])
            if isinstance(input_artifact, dict) and input_artifact.get("role") == "TARGET_INPUT"
        }
        inputs_ok = bool(expected_input_ids) and expected_input_ids.issubset(target_input_ids)
        if scope_files and not inputs_ok:
            _add(issues, "EVIDENCE_INPUT_BINDING", f"{evidence_id} did not inspect the frozen file content IDs in its scope")
        if item.get("coverage_status") == "complete" and scope_files and coverage.get("expected_units") != len(scope_files):
            _add(issues, "EVIDENCE_FALSE_COMPLETE", f"{evidence_id} count differs from named file scope")
        freshness = item.get("freshness_basis") if isinstance(item.get("freshness_basis"), dict) else {}
        matching_ids = {ref for ref, _ in matching}
        if item.get("freshness_status") == "fresh" and (
            freshness.get("workspace_content_id") != workspace_content_id
            or freshness.get("receipt_ref") not in matching_ids
        ):
            _add(issues, "EVIDENCE_FALSE_FRESH", f"{evidence_id} lacks current matching freshness basis")
        output_keys = {
            _artifact_key(output)
            for _, receipt in matching
            for output in receipt.get("outputs", [])
            if isinstance(output, dict)
        }
        artifacts_ok = True
        for index, artifact in enumerate(item.get("artifacts", [])):
            if not isinstance(artifact, dict) or _artifact_key(artifact) not in output_keys:
                _add(issues, "EVIDENCE_ARTIFACT_BINDING", f"{evidence_id}.artifacts[{index}] is not a matching Receipt output")
                artifacts_ok = False
            if not _verify_file(artifact, f"{evidence_id}.artifacts[{index}]", issues, file_cache, approved_roots):
                artifacts_ok = False
        derived_qualification_details = [
            qualification_details.get(receipt.get("provider", {}).get("qualification_ref"))
            for _, receipt in matching
            if isinstance(receipt.get("provider"), dict)
        ]
        derived_tiers = {
            details.get("authority_tier")
            for details in derived_qualification_details
            if isinstance(details, dict) and isinstance(details.get("authority_tier"), str)
        }
        evidence_authority_tiers[evidence_id] = derived_tiers
        authority_binding_ok = len(derived_tiers) == 1 and item.get("authority_tier") in derived_tiers
        if item.get("verification_status") == "verified" and not authority_binding_ok:
            _add(
                issues,
                "EVIDENCE_AUTHORITY_DERIVATION",
                f"{evidence_id} authority_tier is not uniquely derived from trusted Provider Qualification",
            )
        qualification_ok = bool(matching) and authority_binding_ok and all(
            isinstance(receipt.get("provider"), dict)
            and receipt["provider"].get("qualification_ref") in valid_qualifications
            and receipt.get("tool_qualification_status") == "QUALIFIED"
            for _, receipt in matching
        )
        canary_ok = any(isinstance(receipt.get("canary"), dict) and receipt["canary"].get("status") == "PASS" for _, receipt in matching)
        inference = item.get("derivation_method") == "model_inference" or item.get("assertion_source") in {"model", "comment"}
        proof = (
            item.get("direction") in {"SUPPORTS", "CONTEXT_ONLY"}
            and item.get("verification_status") == "verified"
            and item.get("freshness_status") == "fresh"
            and item.get("coverage_status") == "complete"
            and item.get("evidence_ceiling") == "PROOF_FOR_DECLARED_SCOPE"
            and bool(matching)
            and artifacts_ok
            and inputs_ok
            and qualification_ok
            and not inference
            and (not requirements.get("active_negative_canary") or canary_ok)
        )
        strict_proof[evidence_id] = proof
        lineages: set[tuple[Any, ...]] = set()
        for _, receipt in matching:
            provider = receipt.get("provider", {})
            qualification = qualification_details.get(provider.get("qualification_ref"), {})
            # Independence is a trust/execution property, not a label supplied
            # by Evidence. Two views, query methods, Capability wrappers, or
            # Receipt aliases from the same qualified trust domain remain one
            # lineage. A different derivation_method alone can never mint a
            # second source.
            lineages.add((qualification.get("trust_domain_id"),))
        evidence_lineages[evidence_id] = lineages
        if item.get("evidence_ceiling") == "PROOF_FOR_DECLARED_SCOPE" and policy.get("mode") == "ENFORCE" and not proof:
            _add(issues, "EVIDENCE_NOT_STRICT_PROOF", f"{evidence_id} lacks a fully bound Receipt/artifact/qualification/Canary chain")
        if policy.get("outcome_authority") == "HINTS_ONLY" and item.get("evidence_ceiling") != "HINT":
            _add(issues, "POLICY_EVIDENCE_CEILING", f"{evidence_id} exceeds HINTS_ONLY")

    # Claim/Evidence scope references resolve to the frozen file manifest,
    # repository set, targets and build profiles.
    known_targets = {profile.get("target") for profile in build_profiles.values() if isinstance(profile.get("target"), str)}
    for owner_id, owner in list(claims.items()) + list(evidence.items()):
        scope = _scope(owner.get("scope"))
        for repo_id in scope["repository_ids"]:
            if repo_id not in repositories:
                _add(issues, "SCOPE_REPOSITORY_REF", f"{owner_id} references unknown repository {repo_id}")
        for profile_id in scope["build_profile_ids"]:
            if profile_id not in build_profiles:
                _add(issues, "SCOPE_BUILD_PROFILE_REF", f"{owner_id} references unknown build profile {profile_id}")
        for target in scope["targets"]:
            if target not in known_targets:
                _add(issues, "SCOPE_TARGET_REF", f"{owner_id} references unknown target {target}")
        for file_path in scope["files"]:
            matches = [
                entry for (repo_id, path), entry in file_entries.items()
                if path == file_path and (not scope["repository_ids"] or repo_id in scope["repository_ids"])
            ]
            if not matches:
                _add(issues, "SCOPE_FILE_REF", f"{owner_id} file {file_path} is absent from frozen manifest")

    # Build context refs become typed after Receipt/Evidence indexes exist.
    for profile_id, profile in build_profiles.items():
        for ref in profile.get("receipt_refs", []):
            if ref not in receipts:
                _add(issues, "WORKSPACE_RECEIPT_REF", f"build profile {profile_id} references unknown Receipt {ref}")
    for ref in build_context.get("equivalence_evidence_refs", []):
        if ref not in evidence:
            _add(issues, "WORKSPACE_EVIDENCE_REF", f"build context references unknown Evidence {ref}")

    # Resolve user errors through a dedicated applicability Claim and all six
    # environment/scope dimensions. Local green alone is never sufficient.
    user_evidence = {identifier for identifier, item in evidence.items() if item.get("assertion_source") == "user_external"}
    represented: set[str] = set()
    resolved_user_evidence: set[str] = set()
    unresolved_external = False
    for failure_id, failure in failures.items():
        original_ref = failure.get("evidence_ref")
        represented.add(original_ref)
        original = evidence.get(original_ref)
        if not isinstance(original, dict) or original.get("assertion_source") != "user_external":
            _add(issues, "EXTERNAL_EVIDENCE_REF", f"{failure_id} does not reference user_external Evidence")
        if failure.get("applicability_status") != "DOES_NOT_APPLY":
            unresolved_external = True
            continue
        reconciliation_claim = claims.get(failure.get("reconciliation_claim_ref"))
        reconciliation_receipt = receipts.get(failure.get("reconciliation_receipt_ref"))
        refs = failure.get("reconciliation_evidence_refs", [])
        valid = True
        if (
            not isinstance(reconciliation_claim, dict)
            or reconciliation_claim.get("claim_type") != "EXTERNAL_ERROR_APPLICABILITY"
            or reconciliation_claim.get("claim_status") != "PROVEN"
            or reconciliation_claim.get("workspace_snapshot_id") != workspace_id
        ):
            _add(issues, "EXTERNAL_RECONCILIATION_CLAIM", f"{failure_id} lacks a proven current applicability Claim")
            valid = False
        if (
            not isinstance(reconciliation_receipt, dict)
            or reconciliation_receipt.get("capability_id") != "external-evidence"
            or reconciliation_receipt.get("workspace_snapshot_id") != workspace_id
            or not _effective(reconciliation_receipt)
        ):
            _add(issues, "EXTERNAL_RECONCILIATION_RECEIPT", f"{failure_id} lacks an effective external-evidence Receipt")
            valid = False
        if set(failure.get("reconciliation_dimensions", [])) != RECONCILIATION_DIMENSIONS:
            _add(issues, "EXTERNAL_RECONCILIATION_DIMENSIONS", f"{failure_id} omits required comparison dimensions")
            valid = False
        for ref in refs:
            item = evidence.get(ref)
            if (
                not isinstance(item, dict)
                or not isinstance(reconciliation_claim, dict)
                or item.get("claim_id") != reconciliation_claim.get("claim_id")
                or not strict_proof.get(ref, False)
                or failure.get("reconciliation_receipt_ref") not in item.get("receipt_refs", [])
            ):
                _add(issues, "EXTERNAL_RECONCILIATION_REF", f"{failure_id} has irrelevant/unqualified Evidence {ref}")
                valid = False
        if original_ref in refs:
            _add(issues, "EXTERNAL_RECONCILIATION_REF", f"{failure_id} reuses the failure as its exclusion proof")
            valid = False
        if valid:
            resolved_user_evidence.add(original_ref)
        else:
            unresolved_external = True
    omitted = user_evidence - represented
    if omitted:
        _add(issues, "EXTERNAL_EVIDENCE_HIDDEN", f"user Evidence absent from external_failures: {sorted(omitted)}")
        unresolved_external = True

    # Claim semantics are derived from the resolved Evidence/Receipt chain.
    refutations_by_claim: dict[str, set[str]] = {}
    for evidence_id, item in evidence.items():
        if item.get("direction") == "REFUTES" and isinstance(item.get("claim_id"), str):
            refutations_by_claim.setdefault(item["claim_id"], set()).add(evidence_id)
    for claim_id, claim in claims.items():
        if claim.get("workspace_snapshot_id") != workspace_id:
            _add(issues, "WORKSPACE_BINDING", f"{claim_id} belongs to another workspace")
        supporting = claim.get("supporting_evidence_refs", [])
        refuting = claim.get("refuting_evidence_refs", [])
        for ref in supporting:
            item = evidence.get(ref)
            if not isinstance(item, dict):
                _add(issues, "CLAIM_EVIDENCE_REF", f"{claim_id} missing supporting Evidence {ref}")
            elif item.get("claim_id") != claim_id or item.get("direction") != "SUPPORTS":
                _add(issues, "CLAIM_EVIDENCE_DIRECTION", f"{claim_id} support {ref} has wrong Claim/direction")
        for ref in refuting:
            item = evidence.get(ref)
            if not isinstance(item, dict):
                _add(issues, "CLAIM_EVIDENCE_REF", f"{claim_id} missing refuting Evidence {ref}")
            elif item.get("claim_id") != claim_id or item.get("direction") != "REFUTES":
                _add(issues, "CLAIM_EVIDENCE_DIRECTION", f"{claim_id} refutation {ref} has wrong Claim/direction")
        hidden = refutations_by_claim.get(claim_id, set()) - set(refuting) - resolved_user_evidence
        if hidden:
            _add(issues, "CLAIM_HIDDEN_REFUTATION", f"{claim_id} omits refutations {sorted(hidden)}")
        if claim.get("claim_status") == "NOT_APPLICABLE":
            basis = claim.get("applicability_basis") if isinstance(claim.get("applicability_basis"), dict) else {}
            refs = basis.get("evidence_refs", [])
            if not refs or any(
                not isinstance(evidence.get(ref), dict)
                or evidence[ref].get("claim_id") != claim_id
                or not strict_proof.get(ref, False)
                for ref in refs
            ):
                _add(issues, "CLAIM_INVALID_APPLICABILITY", f"{claim_id} lacks current qualified applicability proof")
            continue
        if claim.get("claim_status") != "PROVEN":
            continue
        if policy.get("outcome_authority") == "HINTS_ONLY":
            _add(issues, "POLICY_CLAIM_CEILING", f"{claim_id} cannot be PROVEN in HINTS_ONLY")
        support_items = [evidence[ref] for ref in supporting if ref in evidence]
        if policy.get("mode") == "ENFORCE":
            for ref in supporting:
                if not strict_proof.get(ref, False):
                    _add(issues, "CLAIM_UNQUALIFIED_PROOF", f"{claim_id} relies on non-proof {ref}")
        scope_missing = _scope_missing(claim, support_items)
        if scope_missing:
            _add(issues, "CLAIM_SCOPE_COVERAGE", f"{claim_id} missing {scope_missing}")
        required_tiers = set(claim.get("required_authority_tiers", []))
        actual_tiers = set().union(*(evidence_authority_tiers.get(ref, set()) for ref in supporting)) if supporting else set()
        if not required_tiers.issubset(actual_tiers):
            _add(issues, "CLAIM_AUTHORITY", f"{claim_id} missing tiers {sorted(required_tiers - actual_tiers)}")
        minimum = requirements.get("high_risk_minimum_independent_sources", 1) if claim.get("criticality") in {"HIGH", "CRITICAL"} else requirements.get("minimum_independent_sources", 1)
        lineages = set().union(*(evidence_lineages.get(ref, set()) for ref in supporting)) if supporting else set()
        if len(lineages) < minimum:
            _add(issues, "CLAIM_CORROBORATION", f"{claim_id} has {len(lineages)} independent execution lineage(s); requires {minimum}")

    # Instance Claim parity and Gate semantics.
    if set(summaries) != set(claims):
        _add(issues, "INSTANCE_CLAIM_PARITY", f"instance={sorted(summaries)}, bundle={sorted(claims)}")
    for claim_id, summary in summaries.items():
        claim = claims.get(claim_id)
        if isinstance(claim, dict) and (summary.get("claim_ref") != claim_id or summary.get("claim_status") != claim.get("claim_status")):
            _add(issues, "INSTANCE_CLAIM_DRIFT", f"{claim_id} summary differs from Claim")
    for gate_id, gate in gates.items():
        claim_refs = gate.get("claim_refs", [])
        evidence_refs = gate.get("evidence_refs", [])
        for ref in claim_refs:
            if ref not in claims:
                _add(issues, "GATE_CLAIM_REF", f"{gate_id} references unknown Claim {ref}")
        for ref in evidence_refs:
            if ref not in evidence:
                _add(issues, "GATE_EVIDENCE_REF", f"{gate_id} references unknown Evidence {ref}")
        if gate.get("gate_status") == "PASS":
            for ref in claim_refs:
                if claims.get(ref, {}).get("claim_status") != "PROVEN":
                    _add(issues, "GATE_FALSE_PASS", f"{gate_id} passes unresolved Claim {ref}")
            for ref in evidence_refs:
                item = evidence.get(ref)
                if isinstance(item, dict) and item.get("claim_id") not in claim_refs:
                    _add(issues, "GATE_IRRELEVANT_EVIDENCE", f"{gate_id} cites Evidence for another Claim")
                if policy.get("mode") == "ENFORCE" and not strict_proof.get(ref, False):
                    _add(issues, "GATE_FALSE_PASS", f"{gate_id} cites non-proof {ref}")
        if gate.get("gate_status") == "NOT_APPLICABLE":
            basis_ref = gate.get("applicability_basis_ref")
            if basis_ref not in claim_refs or claims.get(basis_ref, {}).get("claim_status") != "NOT_APPLICABLE":
                _add(issues, "GATE_INVALID_APPLICABILITY", f"{gate_id} basis is not a referenced N/A Claim")
        if gate.get("gate_status") == "WAIVED":
            waiver = waivers.get(gate.get("waiver_ref"))
            valid = isinstance(waiver, dict) and waiver.get("gate_id") == gate_id and waiver.get("status") == "ACTIVE"
            if valid:
                scope = waiver.get("scope", {})
                valid = (
                    scope.get("workspace_snapshot_id") == workspace_id
                    and gate_id in scope.get("gate_ids", [])
                    and set(claim_refs).issubset(set(scope.get("claim_ids", [])))
                )
                expires = _time(waiver.get("expires_at"))
                valid &= expires is None or verdict_time is None or expires > verdict_time
                approval = receipts.get(waiver.get("approval_receipt_ref"))
                decision = approval.get("decision") if isinstance(approval, dict) else None
                valid &= bool(
                    isinstance(approval, dict)
                    and approval.get("receipt_type") == "WAIVER"
                    and approval.get("execution_status") == "COMPLETED"
                    and isinstance(decision, dict)
                    and decision.get("decision") == "WAIVED"
                    and decision.get("subject") == gate_id
                    and decision.get("authority_ref") == waiver.get("authority_ref")
                    and gate_id in decision.get("scope", [])
                    and authority_pins_decision_receipt(approval, "WAIVER_APPROVAL", "waiver_receipt_content_ids")
                )
            if not valid:
                _add(issues, "GATE_INVALID_WAIVER", f"{gate_id} lacks a current scoped authority-consistent Waiver")

    # A Mutation is emitted after the bounded edit. A separate later
    # POST_MUTATION_VALIDATION Receipt points back to it and to effective
    # validation Receipts; the Mutation never references future objects.
    mutations = {identifier: receipt for identifier, receipt in receipts.items() if receipt.get("receipt_type") == "MUTATION"}
    post_mutation_receipts = {
        identifier: receipt
        for identifier, receipt in receipts.items()
        if receipt.get("receipt_type") == "POST_MUTATION_VALIDATION"
    }
    baseline = bundle.get("baseline_workspace_snapshot")
    baseline_file_entries: dict[tuple[Any, Any], dict[str, Any]] = {}
    if isinstance(baseline, dict):
        baseline_manifest = baseline.get("file_manifest") if isinstance(baseline.get("file_manifest"), dict) else {}
        for entry in baseline_manifest.get("entries", []) if isinstance(baseline_manifest.get("entries"), list) else []:
            if isinstance(entry, dict):
                baseline_file_entries[(entry.get("repository_id"), entry.get("path"))] = entry
        baseline_payload = {
            "expected_units": baseline_manifest.get("expected_units"),
            "entries": baseline_manifest.get("entries", []),
        }
        if baseline_manifest.get("content_id") != canonical_content_id(baseline_payload):
            _add(issues, "MUTATION_BASELINE", "baseline file manifest content_id is stale or forged")
    all_mutations_valid = True
    for receipt_id, receipt in mutations.items():
        mutation = receipt.get("mutation") if isinstance(receipt.get("mutation"), dict) else {}
        authorization = receipts.get(mutation.get("authorization_receipt_ref"))
        decision = authorization.get("decision") if isinstance(authorization, dict) else None
        edit = authorization.get("edit_authorization") if isinstance(authorization, dict) and isinstance(authorization.get("edit_authorization"), dict) else {}
        valid = True
        if not isinstance(baseline, dict):
            _add(issues, "MUTATION_BASELINE", f"{receipt_id} lacks baseline_workspace_snapshot")
            valid = False
        if (
            not isinstance(authorization, dict)
            or authorization.get("receipt_type") != "AUTHORIZATION"
            or authorization.get("execution_status") != "COMPLETED"
            or not isinstance(decision, dict)
            or decision.get("decision") not in {"GRANTED", "APPROVED"}
            or not authority_pins_decision_receipt(authorization, "MUTATION_AUTHORIZATION", "authorization_receipt_content_ids")
        ):
            _add(issues, "MUTATION_UNAUTHORIZED", f"{receipt_id} lacks a valid Authorization Receipt")
            valid = False
        if isinstance(baseline, dict) and (
            not isinstance(authorization, dict)
            or authorization.get("workspace_snapshot_id") != baseline.get("snapshot_id")
            or mutation.get("baseline_content_id") != baseline.get("content_id")
        ):
            _add(issues, "MUTATION_BASELINE", f"{receipt_id} does not bind authorized baseline")
            valid = False
        if receipt.get("workspace_snapshot_id") != workspace_id or mutation.get("result_content_id") != workspace_content_id:
            _add(issues, "MUTATION_RESULT", f"{receipt_id} does not bind current result snapshot")
            valid = False
        changed: list[str] = []
        for raw_path in mutation.get("changed_paths", []):
            normal = _normalise_path(raw_path)
            if normal is None:
                _add(issues, "MUTATION_PATH", f"{receipt_id} has unsafe path {raw_path!r}")
                valid = False
            else:
                changed.append(normal)
        actual_changed_paths = {
            str(key[1])
            for key in set(baseline_file_entries) | set(file_entries)
            if baseline_file_entries.get(key, {}).get("content_id") != file_entries.get(key, {}).get("content_id")
        }
        if not actual_changed_paths or set(changed) != actual_changed_paths:
            _add(
                issues,
                "MUTATION_CHANGED_PATH_DRIFT",
                f"{receipt_id} declares {sorted(set(changed))}, manifest diff is {sorted(actual_changed_paths)}",
            )
            valid = False
        diff_ref = mutation.get("diff_artifact")
        diff_path = None
        if isinstance(diff_ref, dict) and diff_ref.get("content_id") == mutation.get("diff_content_id"):
            if _verify_file(diff_ref, f"{receipt_id}.mutation.diff_artifact", issues, file_cache, approved_roots):
                diff_path = _artifact_file(diff_ref.get("location"), approved_roots)
        if diff_path is None:
            _add(issues, "MUTATION_DIFF_ARTIFACT", f"{receipt_id} lacks a verified diff artifact")
            valid = False
        else:
            diff_text = diff_path.read_text(encoding="utf-8", errors="replace").replace("\\", "/")
            if any(path not in diff_text for path in changed):
                _add(issues, "MUTATION_DIFF_ARTIFACT", f"{receipt_id} diff artifact does not name every changed path")
                valid = False
        allowed = edit.get("allowed_paths", []) if isinstance(edit.get("allowed_paths"), list) else []
        forbidden = edit.get("forbidden_paths", []) if isinstance(edit.get("forbidden_paths"), list) else []
        for path in changed:
            if not _allowed(path, allowed) or _allowed(path, forbidden):
                _add(issues, "MUTATION_SCOPE", f"{receipt_id} changed unauthorized path {path}")
                valid = False
        if len(set(changed)) > edit.get("maximum_changed_files", -1) or mutation.get("deleted_lines", 0) > edit.get("maximum_deleted_lines", -1):
            _add(issues, "MUTATION_BUDGET", f"{receipt_id} exceeds file/deletion budget")
            valid = False
        if not set(edit.get("repository_ids", [])).issubset(repositories):
            _add(issues, "MUTATION_SCOPE", f"{receipt_id} authorization references unknown repository")
            valid = False
        mutation_time = _time(receipt.get("created_at"))
        auth_expiry = _time(edit.get("expires_at"))
        if mutation_time is None or auth_expiry is None or mutation_time >= auth_expiry:
            _add(issues, "MUTATION_AUTHORIZATION_EXPIRED", f"{receipt_id} ran outside authorization window")
            valid = False
        linked_posts = [
            (post_id, post_receipt)
            for post_id, post_receipt in post_mutation_receipts.items()
            if isinstance(post_receipt.get("post_mutation_validation"), dict)
            and post_receipt["post_mutation_validation"].get("mutation_receipt_ref") == receipt_id
        ]
        if len(linked_posts) != 1:
            _add(issues, "MUTATION_NOT_REVALIDATED", f"{receipt_id} requires exactly one later POST_MUTATION_VALIDATION Receipt")
            valid = False
        for post_id, post_receipt in linked_posts:
            result = post_receipt.get("post_mutation_validation", {})
            post_time = _time(post_receipt.get("ended_at"))
            post_valid = bool(
                post_receipt.get("execution_status") == "COMPLETED"
                and post_receipt.get("workspace_snapshot_id") == workspace_id
                and post_receipt.get("capability_id") == receipt.get("capability_id")
                and result.get("result_content_id") == workspace_content_id
                and result.get("result_file_manifest_content_id") == manifest.get("content_id")
                and set(result.get("validated_paths", [])) == set(changed)
                and result.get("status") == "PASS"
                and mutation_time is not None
                and post_time is not None
                and post_time > mutation_time
            )
            for validation_ref in result.get("validation_receipt_refs", []):
                validation_receipt = receipts.get(validation_ref)
                validation_time = _time(validation_receipt.get("ended_at")) if isinstance(validation_receipt, dict) else None
                if (
                    not isinstance(validation_receipt, dict)
                    or validation_receipt.get("receipt_type") != "EVIDENCE_CHECK"
                    or not _effective(validation_receipt)
                    or validation_receipt.get("workspace_snapshot_id") != workspace_id
                    or mutation_time is None
                    or validation_time is None
                    or validation_time <= mutation_time
                ):
                    post_valid = False
                    continue
                current_changed_ids = {
                    entry.get("content_id")
                    for key, entry in file_entries.items()
                    if str(key[1]) in set(changed)
                }
                validation_input_ids = {
                    item.get("content_id")
                    for item in validation_receipt.get("inputs", [])
                    if isinstance(item, dict) and item.get("role") == "TARGET_INPUT"
                }
                if current_changed_ids and not current_changed_ids.issubset(validation_input_ids):
                    post_valid = False
            if not result.get("validation_receipt_refs"):
                post_valid = False
            if not post_valid:
                _add(issues, "MUTATION_NOT_REVALIDATED", f"{receipt_id} has stale, ineffective or mismatched {post_id}")
                valid = False
        all_mutations_valid &= valid
    derived_mutation = "NOT_APPLICABLE" if not mutations else "VALIDATED" if all_mutations_valid else "FAILED"
    if instance.get("mutation_validation_status") != derived_mutation:
        _add(issues, "MUTATION_STATUS_DRIFT", f"stored={instance.get('mutation_validation_status')}, derived={derived_mutation}")

    # Strict completion has exactly three immutable report views, all carrying
    # the same derived machine facts. The whole bundle is content-addressed too.
    facts = report_facts(bundle)
    fact_digest = canonical_content_id(facts)
    if policy.get("mode") == "ENFORCE" and instance.get("execution_status") == "COMPLETED":
        if bundle.get("report_fact_digest") != fact_digest:
            _add(issues, "REPORT_FACT_DIGEST", f"stored={bundle.get('report_fact_digest')}, derived={fact_digest}")
        if set(instance.get("report_refs", [])) != set(reports):
            _add(issues, "REPORT_REF_PARITY", "instance.report_refs differs from report manifests")
        audiences = {report.get("audience") for report in reports.values()}
        if len(reports) != 3 or audiences != {"MACHINE", "PROFESSIONAL", "NOVICE"}:
            _add(issues, "REPORT_VIEW_CLOSURE", "strict completion needs exactly machine/professional/novice reports")
        for report_id, report in reports.items():
            if report.get("fact_digest") != fact_digest:
                _add(issues, "REPORT_FACT_DIGEST", f"{report_id} binds another fact set")
            file_ok = _verify_file(report, f"report {report_id}", issues, file_cache, approved_roots)
            path = _artifact_file(report.get("location"), approved_roots)
            if file_ok and path is not None:
                try:
                    document = json.loads(path.read_text(encoding="utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    document = None
                if isinstance(document, dict):
                    if document.get("fact_digest") != fact_digest or document.get("facts") != facts:
                        _add(issues, "REPORT_CONTENT_DRIFT", f"{report_id} JSON facts differ from RunBundle")
                else:
                    text = path.read_text(encoding="utf-8", errors="replace")
                    tokens = [fact_digest, str(instance.get("final_verdict")), *claims, *gates, *facts["limitations"]]
                    omitted_tokens = [str(token) for token in tokens if str(token) not in text]
                    if omitted_tokens:
                        _add(issues, "REPORT_CONTENT_DRIFT", f"{report_id} omits shared fact tokens {omitted_tokens}")
        expected_bundle_digest = bundle_content_id(bundle)
        if instance.get("run_bundle_digest") != expected_bundle_digest:
            _add(issues, "RUN_BUNDLE_DIGEST", f"stored={instance.get('run_bundle_digest')}, derived={expected_bundle_digest}")

    # Deterministic verdict recomputation.
    required_claims = [item for item in summaries.values() if item.get("required_for_verdict") is True]
    required_tasks = [item for item in tasks.values() if item.get("required_for_verdict") is True]
    if not required_claims:
        _add(issues, "ZERO_REQUIRED_FACTS", "no Claim is required for verdict")
    if not required_tasks:
        _add(issues, "ZERO_REQUIRED_FACTS", "no Task is required for verdict")
    if policy.get("mode") == "ENFORCE" and instance.get("execution_status") == "COMPLETED":
        gate_statuses = [gate.get("gate_status") for gate in gates.values()]
        failed = "FAIL" in gate_statuses or any(item.get("claim_status") == "DISPROVEN" for item in required_claims)
        incomplete = (
            not profile_authoritative
            or unresolved_external
            or collaboration_incomplete
            or any(status in {"INCONCLUSIVE", "NOT_EVALUATED"} for status in gate_statuses)
            or any(item.get("claim_status") in {"NOT_PROVEN", "CONFLICTED", "UNKNOWN"} for item in required_claims)
            or any(item.get("execution_status") != "COMPLETED" for item in required_tasks)
        )
        expected_verdict = "REJECT" if failed else "INCOMPLETE" if incomplete else "ACCEPT_WITH_RISK" if "WAIVED" in gate_statuses else "ACCEPT"
        if instance.get("final_verdict") != expected_verdict:
            _add(issues, "VERDICT_MISMATCH", f"stored={instance.get('final_verdict')}, recomputed={expected_verdict}")
        if instance.get("final_verdict") in {"ACCEPT", "ACCEPT_WITH_RISK"} and not profile_authoritative:
            _add(issues, "STRICT_ACCEPT_WITHOUT_ACTIVE_PROFILE", "strict acceptance requires an exact active Profile binding")
        if instance.get("final_verdict") in {"ACCEPT", "ACCEPT_WITH_RISK"} and unresolved_external:
            _add(issues, "VERDICT_USER_ERROR_UNRESOLVED", "acceptance is forbidden while user error remains unresolved")

    return sorted(set(issues))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument(
        "--artifact-root",
        action="append",
        type=Path,
        default=[],
        help="Additional approved local root for absolute or relative artifact locations (repeatable).",
    )
    parser.add_argument(
        "--authority-registry",
        required=True,
        type=Path,
        help="Explicit Authority Registry path supplied by the trusted runtime/CI boundary.",
    )
    parser.add_argument(
        "--authority-registry-content-id",
        required=True,
        help="Out-of-band pinned canonical SHA-256 for the Authority Registry; never derive it from the Bundle or Registry in this invocation.",
    )
    args = parser.parse_args()
    try:
        bundle_root = args.bundle.resolve().parent
        issues = validate_run_bundle(
            load_document(args.bundle),
            artifact_roots=[bundle_root, *args.artifact_root],
            authority_registry_path=args.authority_registry,
            expected_authority_registry_content_id=args.authority_registry_content_id,
        )
    except Exception as exc:
        print(f"ERROR [VALIDATOR_FAILURE] {exc}")
        return 2
    print(f"RunBundle validation: {args.bundle}")
    for issue in issues:
        print(f"ERROR [{issue}]")
    if issues:
        print(f"RESULT: FAIL ({len(issues)} issue(s))")
        return 1
    print("RESULT: PASS: policy, profile, artifacts, evidence, reports and verdict agree.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
