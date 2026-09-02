#!/usr/bin/env python3
"""Validate the static Engineering Evidence Toolkit specification bundle.

A zero exit code means that all required structural and semantic specification
checks passed. It never means that a capability is implemented, activated, or
that business code passed. PyYAML and jsonschema are mandatory: a missing schema
engine is a validation failure, not a limited pass.
"""

from __future__ import annotations

import argparse
import json
import hashlib
import importlib.util
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:
    print("ERROR [DEPENDENCY] PyYAML is required; obtain it only through the configured outer runtime boundary.")
    raise SystemExit(2)

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]


ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE_AUTHORITY_REGISTRY_CONTENT_ID = "sha256:3d9e58fc18eec4e479a573a2a4205f6cbe05c4dc396ce84afe5f1c372c7136eb"
ALLOWED_MODULE_STATES = {"DESIGNED", "SCAFFOLDED", "IMPLEMENTED", "VALIDATED", "ACTIVE"}
LEGACY_NAME_MARKERS = (
    "Code_Fact_Accelerator_v3.1",
    "Code_Fact_Accelerator_Post_v3.1",
    "Recovery_Review_v2.5",
)
SCHEMA_BINDINGS = {
    "toolkit": ROOT / "contracts/toolkit-manifest.schema.json",
    "capability": ROOT / "contracts/capability-manifest.schema.json",
    "profile": ROOT / "contracts/profile-manifest.schema.json",
    "lifecycle": ROOT / "contracts/lifecycle-manifest.schema.json",
    "harness_support_matrix": ROOT / "contracts/harness-support-matrix.schema.json",
    "harness_runtime_observation": ROOT / "contracts/harness-runtime-observation.schema.json",
    "run_policy": ROOT / "contracts/run-policy.schema.json",
    "cpp_candidate_selection": ROOT / "acceptance/cpp-target-selection/candidate-selection.schema.json",
    "cpp_real_validation": ROOT / "acceptance/cpp-target-selection/real-validation.schema.json",
}
COMMON_CAPABILITY_FIELDS = {
    "schema_version",
    "id",
    "name",
    "version",
    "status",
    "kind",
    "entrypoint",
    "inputs",
    "outputs",
    "side_effects",
    "failure_policy",
    "result_states",
    "evidence_ceiling",
}
COMMON_PROFILE_FIELDS = {
    "status",
    "status_dimensions",
    "schema_version",
    "kind",
    "id",
    "version",
    "title",
    "intent",
    "profile_is_optional",
    "runner_contract",
    "capability_internal_access",
    "direct_provider_access",
    "capabilities",
}
CANONICAL_RUNTIME_BOUNDARY = ROOT / "adapters/company-runtime-boundary/ADAPTER.yaml"
DISPERSED_ENVIRONMENT_POLICY_KEYS = {
    "default_network",
    "network_default",
    "runtime_package_install",
    "no_runtime_download_by_default",
}
PORTABILITY_TEXT_SUFFIXES = {
    ".cpp", ".h", ".html", ".json", ".md", ".ps1", ".py", ".toml", ".txt", ".yaml", ".yml"
}
WINDOWS_ABSOLUTE_PATH_LITERAL = re.compile(r"(?<![A-Za-z0-9+.-])[A-Za-z]:[\\/](?![\\/])")
POSIX_MACHINE_PATH_LITERAL = re.compile(r"(?<![:A-Za-z0-9])/(?:home|Users|tmp)/[A-Za-z0-9._-]+")
RELEASE_SEMVER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:[-+][0-9A-Za-z.-]+)?$")


class Findings:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, code: str, message: str) -> None:
        self.errors.append(f"ERROR [{code}] {message}")

    def warning(self, code: str, message: str) -> None:
        self.warnings.append(f"WARN  [{code}] {message}")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_yaml(path: Path, findings: Findings) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except Exception as exc:
        findings.error("YAML_PARSE", f"{rel(path)}: {exc}")
        return None


def load_json(path: Path, findings: Findings) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        findings.error("JSON_PARSE", f"{rel(path)}: {exc}")
        return None


def require_paths(findings: Findings) -> None:
    required = [
        "00_START_HERE.md",
        "TOOLKIT_MANIFEST.yaml",
        "CURRENT_STATE.yaml",
        "DIRECTORY_MAP.md",
        "governance",
        "governance/REPOSITORY_READER_AND_NAMING_POLICY.yaml",
        "governance/AUTOMATION_AND_HOOK_POLICY.md",
        "contracts",
        "capabilities",
        "adapters",
        "adapters/HARNESS_CAPABILITY_MATRIX.yaml",
        "acceptance/harness-validation/GLM_COMPATIBILITY_OBSERVATION.yaml",
        "acceptance/harness-validation/glm-final-observation.png",
        "lifecycle/README.md",
        "lifecycle/TOOLKIT_LIFECYCLE.yaml",
        "profiles",
        "composition",
        "dashboard/README.md",
        "dashboard/capability-progress.html",
        "acceptance",
        "migration",
        "roadmap",
        "runs/README.md",
        "tools/render_capability_dashboard.py",
        "tools/test_capability_dashboard.py",
        "tools/toolkit_doctor.py",
        "tools/test_toolkit_doctor.py",
        "tools/test_lifecycle_and_harness_contracts.py",
        "tools/validate_run_bundle.py",
        "tools/validate_run_bundle_semantic.py",
        "tools/test_run_bundle_validator.py",
        "tools/windows_precheck_mvp.py",
        "tools/test_windows_precheck_mvp.py",
        "tools/test_status_promotion.py",
        "tools/measure_cpp_candidate.py",
        "tools/test_measure_cpp_candidate.py",
        "tools/capture_git_worktree_state.py",
        "tools/test_capture_git_worktree_state.py",
        "tools/test_cpp_acceptance_records.py",
        "requirements-validation.txt",
        "policies/quick.yaml",
        "policies/balanced.yaml",
        "policies/strict.yaml",
        "acceptance/fixtures/run-bundles/valid-strict.yaml",
        "acceptance/fixtures/run-bundles/negative-cases.yaml",
        "acceptance/fixtures/windows-mvp",
        "capabilities/windows-static-precheck/contracts/target-manifest.schema.json",
        "capabilities/windows-static-precheck/contracts/target.example.yaml",
        "acceptance/cpp-target-selection/candidate-selection.schema.json",
        "acceptance/cpp-target-selection/CANDIDATE_SELECTION.yaml",
        "acceptance/cpp-target-selection/real-validation.schema.json",
        "acceptance/cpp-target-selection/REAL_VALIDATION.yaml",
    ]
    for relative in required:
        if not (ROOT / relative).exists():
            findings.error("MISSING_REQUIRED_PATH", relative)


def parse_all_structured_files(findings: Findings) -> None:
    for path in sorted(ROOT.rglob("*.json")):
        load_json(path, findings)
    for suffix in ("*.yaml", "*.yml"):
        for path in sorted(ROOT.rglob(suffix)):
            load_yaml(path, findings)


def schema_error_path(error: Any) -> str:
    return ".".join(str(part) for part in error.absolute_path) or "<root>"


def validate_with_jsonschema(
    instance_path: Path,
    schema_path: Path,
    findings: Findings,
) -> None:
    if Draft202012Validator is None or FormatChecker is None:
        return
    schema = load_json(schema_path, findings)
    instance = load_yaml(instance_path, findings)
    if not isinstance(schema, dict) or instance is None:
        return
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
    except Exception as exc:
        findings.error("INVALID_SCHEMA", f"{rel(schema_path)}: {exc}")
        return
    for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path)):
        findings.error(
            "SCHEMA_VALIDATION",
            f"{rel(instance_path)} at {schema_error_path(error)}: {error.message}",
        )


def validate_machine_contracts(findings: Findings) -> None:
    if Draft202012Validator is None or FormatChecker is None:
        findings.error(
            "SCHEMA_ENGINE_UNAVAILABLE",
            "jsonschema is required; install requirements-validation.txt in an approved isolated runtime.",
        )
        return
    schema_paths = list((ROOT / "contracts").glob("*.schema.json"))
    schema_paths.extend((ROOT / "capabilities").glob("*/contracts/*.schema.json"))
    schema_paths.extend((ROOT / "acceptance").glob("*/*.schema.json"))
    for schema_path in sorted(schema_paths):
        schema = load_json(schema_path, findings)
        if not isinstance(schema, dict):
            continue
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:
            findings.error("INVALID_SCHEMA", f"{rel(schema_path)}: {exc}")
    validate_with_jsonschema(ROOT / "TOOLKIT_MANIFEST.yaml", SCHEMA_BINDINGS["toolkit"], findings)
    for path in sorted((ROOT / "capabilities").glob("*/CAPABILITY.yaml")):
        validate_with_jsonschema(path, SCHEMA_BINDINGS["capability"], findings)
    for path in sorted((ROOT / "profiles").glob("*/PROFILE.yaml")):
        validate_with_jsonschema(path, SCHEMA_BINDINGS["profile"], findings)
    validate_with_jsonschema(
        ROOT / "lifecycle/TOOLKIT_LIFECYCLE.yaml",
        SCHEMA_BINDINGS["lifecycle"],
        findings,
    )
    validate_with_jsonschema(
        ROOT / "adapters/HARNESS_CAPABILITY_MATRIX.yaml",
        SCHEMA_BINDINGS["harness_support_matrix"],
        findings,
    )
    validate_with_jsonschema(
        ROOT / "acceptance/harness-validation/GLM_COMPATIBILITY_OBSERVATION.yaml",
        SCHEMA_BINDINGS["harness_runtime_observation"],
        findings,
    )
    validate_with_jsonschema(
        ROOT / "acceptance/cpp-target-selection/CANDIDATE_SELECTION.yaml",
        SCHEMA_BINDINGS["cpp_candidate_selection"],
        findings,
    )
    validate_with_jsonschema(
        ROOT / "acceptance/cpp-target-selection/REAL_VALIDATION.yaml",
        SCHEMA_BINDINGS["cpp_real_validation"],
        findings,
    )
    for path in sorted((ROOT / "policies").glob("*.yaml")):
        validate_with_jsonschema(path, SCHEMA_BINDINGS["run_policy"], findings)
    try:
        try:
            from tools.validate_run_bundle import load_document as load_run_bundle
            from tools.validate_run_bundle import validate_run_bundle
        except ModuleNotFoundError:
            from validate_run_bundle import load_document as load_run_bundle
            from validate_run_bundle import validate_run_bundle
        fixture_path = ROOT / "acceptance/fixtures/run-bundles/valid-strict.yaml"
        for issue in validate_run_bundle(
            load_run_bundle(fixture_path),
            authority_registry_path=ROOT / "governance/TRUSTED_AUTHORITY_REGISTRY.yaml",
            expected_authority_registry_content_id=ACCEPTANCE_AUTHORITY_REGISTRY_CONTENT_ID,
        ):
            findings.error("RUN_BUNDLE_FIXTURE", issue)
    except Exception as exc:
        findings.error("RUN_BUNDLE_VALIDATOR", str(exc))


def _canonical_id(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _cpp_environment_content_id(environment: Any) -> str:
    value = environment if isinstance(environment, dict) else {}
    keys = (
        "environment_scope", "os", "msvc", "msvc_version", "cmake", "cmake_version",
        "ninja", "ninja_version", "build_timing_status",
    )
    return _canonical_id({key: value.get(key) for key in keys})


def _portable_receipt_issue(
    value: Any,
    label: str,
    *,
    expected_type: str | None = None,
    expected_subject: str | None = None,
    expected_result: dict[str, Any] | None = None,
    expected_environment_scope: str | None = None,
    expected_environment_content_id: str | None = None,
) -> str | None:
    if not isinstance(value, dict):
        return f"{label} requires a content-addressed receipt"
    raw_path = value.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        return f"{label} receipt path is missing"
    supplied = Path(raw_path)
    if supplied.is_absolute() or ".." in supplied.parts:
        return f"{label} receipt path must be a safe repository-relative path"
    path = (ROOT / supplied).resolve()
    if ROOT.resolve() not in path.parents or not path.is_file():
        return f"{label} receipt does not resolve to a repository file"
    actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    if value.get("content_id") != actual:
        return f"{label} receipt content_id is stale or forged"
    if expected_type is None:
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".json" else yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
        return f"{label} is not a parseable typed C++ acceptance receipt: {exc}"
    if not isinstance(document, dict):
        return f"{label} is not a typed C++ acceptance receipt object"
    schema_path = ROOT / "acceptance/cpp-target-selection/cpp-acceptance-receipt.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema_errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
            key=lambda error: list(error.absolute_path),
        )
    except Exception as exc:
        return f"{label} typed receipt schema could not be evaluated: {exc}"
    if schema_errors:
        return f"{label} is not a valid typed C++ acceptance receipt: {schema_errors[0].message}"
    if document.get("receipt_type") != expected_type or document.get("subject_id") != expected_subject:
        return f"{label} typed receipt role/subject does not match {expected_type}/{expected_subject}"
    if (
        document.get("environment_scope") != expected_environment_scope
        or document.get("environment_content_id") != expected_environment_content_id
    ):
        return f"{label} typed receipt does not bind the selected environment context"

    def file_ref_issue(reference: Any, ref_label: str) -> str | None:
        if not isinstance(reference, dict):
            return f"{label} {ref_label} is not content-addressed"
        ref_path = reference.get("path")
        if not isinstance(ref_path, str) or not ref_path:
            return f"{label} {ref_label} path is missing"
        supplied_ref = Path(ref_path)
        resolved = (ROOT / supplied_ref).resolve()
        if supplied_ref.is_absolute() or ".." in supplied_ref.parts or ROOT.resolve() not in resolved.parents or not resolved.is_file():
            return f"{label} {ref_label} is not a safe repository file"
        ref_actual = "sha256:" + hashlib.sha256(resolved.read_bytes()).hexdigest()
        if reference.get("content_id") != ref_actual:
            return f"{label} {ref_label} content_id is stale or forged"
        return None

    for ref_label, reference in [("producer_tool", document.get("producer_tool"))]:
        issue = file_ref_issue(reference, ref_label)
        if issue:
            return issue
    for index, reference in enumerate(document.get("dependencies", [])):
        issue = file_ref_issue(reference, f"dependencies[{index}]")
        if issue:
            return issue
    for index, reference in enumerate(document.get("raw_artifacts", [])):
        issue = file_ref_issue(reference, f"raw_artifacts[{index}]")
        if issue:
            return issue
    attestation = document.get("attestation") if isinstance(document.get("attestation"), dict) else {}
    registry_path = ROOT / "governance/TRUSTED_AUTHORITY_REGISTRY.yaml"
    try:
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return f"{label} cannot load the trusted Authority Registry: {exc}"
    authorities = {
        item.get("authority_ref"): item
        for item in registry.get("authorities", [])
        if isinstance(registry, dict) and isinstance(item, dict)
    }
    authority = authorities.get(attestation.get("authority_ref"))
    if not (
        isinstance(authority, dict)
        and authority.get("status") == "ACTIVE"
        and authority.get("environment_scope") == document.get("environment_scope")
        and "CPP_ACCEPTANCE_ATTESTATION" in authority.get("permissions", [])
        and authority.get("issuer_id") == attestation.get("issued_by")
        and actual in authority.get("cpp_acceptance_receipt_content_ids", [])
    ):
        return f"{label} typed receipt is not pinned by an active scoped C++ acceptance Authority"
    result = document.get("result")
    if expected_result and (not isinstance(result, dict) or any(result.get(key) != expected for key, expected in expected_result.items())):
        return f"{label} typed receipt result does not match the selection record"
    return None


def cpp_candidate_selection_issues(data: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(data, dict):
        return ["candidate selection must be a mapping"]
    raw_candidates = data.get("candidates", [])
    candidates = [item for item in raw_candidates if isinstance(item, dict)] if isinstance(raw_candidates, list) else []
    measurement_tool = data.get("measurement_tool", {})
    if isinstance(measurement_tool, dict):
        measurement_path = ROOT / str(measurement_tool.get("path", ""))
        if measurement_path.is_file():
            actual_tool_id = "sha256:" + hashlib.sha256(measurement_path.read_bytes()).hexdigest()
            if measurement_tool.get("content_id") != actual_tool_id:
                issues.append("measurement tool content_id is stale or forged")
    ids = [item.get("candidate_id") for item in candidates]
    string_ids = [item for item in ids if isinstance(item, str)]
    duplicates = sorted({item for item in string_ids if string_ids.count(item) > 1})
    if duplicates:
        issues.append(f"duplicate candidate ids: {duplicates}")
    by_id = {item.get("candidate_id"): item for item in candidates if isinstance(item.get("candidate_id"), str)}
    selected_id = data.get("selected_candidate_id")
    selected = by_id.get(selected_id)
    if not isinstance(selected, dict):
        issues.append(f"selected candidate does not resolve: {selected_id!r}")
        return issues
    selected_disposition_ids = [
        item.get("candidate_id")
        for item in candidates
        if item.get("disposition") in {"PROVISIONALLY_SELECTED", "SELECTED"}
    ]
    if selected_disposition_ids != [selected_id]:
        issues.append(f"selected disposition mismatch: expected only {selected_id!r}, got {selected_disposition_ids}")

    criteria = data.get("selection_criteria", {})
    metrics = selected.get("metrics", {})
    if isinstance(criteria, dict) and isinstance(metrics, dict):
        for metric_name, criteria_key in (
            ("product_physical_loc", "product_physical_loc"),
            ("product_compilation_units", "product_compilation_units"),
        ):
            bounds = criteria.get(criteria_key, {})
            value = metrics.get(metric_name)
            if isinstance(bounds, dict):
                minimum = bounds.get("minimum")
                maximum = bounds.get("maximum")
                if isinstance(minimum, int) and isinstance(maximum, int):
                    if minimum > maximum:
                        issues.append(f"selection criteria {criteria_key} minimum exceeds maximum")
                    if isinstance(value, int) and not minimum <= value <= maximum:
                        issues.append(f"selected {metric_name}={value} is outside [{minimum}, {maximum}]")
        minimum_tests = criteria.get("minimum_test_cpp_files")
        test_files = metrics.get("test_cpp_files")
        if isinstance(minimum_tests, int) and isinstance(test_files, int) and test_files < minimum_tests:
            issues.append(f"selected test_cpp_files={test_files} is below {minimum_tests}")

    status = data.get("selection_status")
    gate = data.get("selection_gate_status")
    unresolved = data.get("unresolved_requirements", [])
    environment = data.get("environment", {})
    expected_environment_content_id = _cpp_environment_content_id(environment)
    if not isinstance(environment, dict) or environment.get("context_content_id") != expected_environment_content_id:
        issues.append("environment context_content_id is stale or forged")
    if status == "PROVISIONAL":
        if selected.get("disposition") != "PROVISIONALLY_SELECTED":
            issues.append("a PROVISIONAL selection requires PROVISIONALLY_SELECTED disposition")
        if gate != "INCONCLUSIVE":
            issues.append("a PROVISIONAL selection must have an INCONCLUSIVE selection gate")
        if not isinstance(unresolved, list) or not unresolved:
            issues.append("a PROVISIONAL selection must preserve unresolved requirements")
    if status == "FINAL":
        selection_receipt_issue = _portable_receipt_issue(
            data.get("selection_receipt"),
            "FINAL selection",
            expected_type="SELECTION",
            expected_subject=str(selected_id),
            expected_result={
                "candidate_id": selected_id,
                "commit": selected.get("commit"),
                "decision": "SELECTED",
                "gate_result": "PASS",
                "selection_criteria_content_id": _canonical_id(criteria),
            },
            expected_environment_scope=environment.get("environment_scope") if isinstance(environment, dict) else None,
            expected_environment_content_id=expected_environment_content_id,
        )
        if selection_receipt_issue:
            issues.append(selection_receipt_issue)
        if selected.get("disposition") != "SELECTED":
            issues.append("a FINAL selection requires SELECTED disposition")
        if gate != "PASS":
            issues.append("a FINAL selection requires a PASS selection gate")
        if unresolved:
            issues.append("a FINAL selection cannot retain unresolved requirements")
        if not isinstance(environment, dict) or any(
            environment.get(tool) != "AVAILABLE" for tool in ("msvc", "cmake", "ninja")
        ):
            issues.append("a FINAL selection requires MSVC, CMake and Ninja to be AVAILABLE")
        environment_receipt_issue = _portable_receipt_issue(
            environment.get("discovery_receipt") if isinstance(environment, dict) else None,
            "FINAL environment discovery",
            expected_type="ENVIRONMENT_DISCOVERY",
            expected_subject="windows-cpp-toolchain",
            expected_result={
                "msvc": {"status": "AVAILABLE", "version": environment.get("msvc_version")},
                "cmake": {"status": "AVAILABLE", "version": environment.get("cmake_version")},
                "ninja": {"status": "AVAILABLE", "version": environment.get("ninja_version")},
            },
            expected_environment_scope=environment.get("environment_scope") if isinstance(environment, dict) else None,
            expected_environment_content_id=expected_environment_content_id,
        )
        if environment_receipt_issue:
            issues.append(environment_receipt_issue)
        for candidate in candidates:
            measurement = candidate.get("build_measurement", {})
            if not isinstance(measurement, dict) or measurement.get("status") != "MEASURED":
                issues.append(f"FINAL requires measured build timing for {candidate.get('candidate_id')!r}")
                continue
            for field in ("clean_build_ms", "incremental_build_ms"):
                if not isinstance(measurement.get(field), int):
                    issues.append(f"FINAL requires integer {field} for {candidate.get('candidate_id')!r}")
            receipt_issue = _portable_receipt_issue(
                measurement.get("receipt"),
                f"FINAL build measurement for {candidate.get('candidate_id')!r}",
                expected_type="BUILD_MEASUREMENT",
                expected_subject=str(candidate.get("candidate_id")),
                expected_result={
                    "candidate_id": candidate.get("candidate_id"),
                    "commit": candidate.get("commit"),
                    "generator": measurement.get("generator"),
                    "configuration": measurement.get("configuration"),
                    "clean_build_ms": measurement.get("clean_build_ms"),
                    "incremental_build_ms": measurement.get("incremental_build_ms"),
                    "test_status": measurement.get("test_status"),
                },
                expected_environment_scope=environment.get("environment_scope") if isinstance(environment, dict) else None,
                expected_environment_content_id=expected_environment_content_id,
            )
            if receipt_issue:
                issues.append(receipt_issue)
        selected_measurement = selected.get("build_measurement", {})
        if not isinstance(selected_measurement, dict) or selected_measurement.get("test_status") != "PASSED":
            issues.append("a FINAL selected candidate requires PASSED tests")
    return issues


def cpp_real_validation_issues(
    record: Any,
    selection: Any,
    *,
    external_evidence_root: Path | None = None,
    require_external_evidence: bool = False,
) -> list[str]:
    issues: list[str] = []
    if not isinstance(record, dict) or not isinstance(selection, dict):
        return ["real validation record and candidate selection must be mappings"]
    candidates = {
        item.get("candidate_id"): item
        for item in selection.get("candidates", [])
        if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)
    }
    target = record.get("target", {})
    selected_id = selection.get("selected_candidate_id")
    selected = candidates.get(selected_id)
    if not isinstance(target, dict) or not isinstance(selected, dict):
        issues.append("real validation target cannot be matched to the selected candidate")
    else:
        for key in ("candidate_id", "origin", "branch", "commit", "license_id"):
            expected = selected_id if key == "candidate_id" else selected.get(key)
            if target.get(key) != expected:
                issues.append(f"real validation target {key}={target.get(key)!r}; expected {expected!r}")
    storage = record.get("evidence_storage", {})
    locator = storage.get("runtime_locator", {}) if isinstance(storage, dict) else {}
    if (
        not isinstance(storage, dict)
        or storage.get("kind") != "EXTERNAL_CONTENT_ADDRESSED"
        or storage.get("path_semantics") != "RELATIVE_TO_RUNTIME_ROOT"
        or storage.get("record_portable") is not True
        or storage.get("artifacts_portable") is not False
        or storage.get("source_worktrees_mutated") is not True
    ):
        issues.append("real validation evidence storage must be portable metadata with external content-addressed artifacts")
    if isinstance(storage, dict) and "root" in storage:
        issues.append("real validation record must not embed a machine-specific evidence root")
    if (
        not isinstance(locator, dict)
        or locator.get("mode") != "RUNTIME_BOUND"
        or locator.get("cli_option") != "--cpp-evidence-root"
        or locator.get("environment_variable") != "EET_CPP_EVIDENCE_ROOT"
        or locator.get("required_for_artifact_reverification") is not True
    ):
        issues.append("real validation evidence root must use the canonical runtime binding contract")
    if record.get("qualification_effect") != "NONE":
        issues.append("partial static validation cannot grant qualification")
    environment = record.get("environment", {})
    if isinstance(environment, dict):
        if any(environment.get(tool) != "NOT_AVAILABLE" for tool in ("msvc", "cmake", "ninja")):
            issues.append("this PARTIAL_STATIC_SUBSET record must preserve the observed unavailable toolchain")
        if environment.get("formal_build_status") != "BLOCKED_BY_ENVIRONMENT":
            issues.append("this partial static record cannot claim a formal build result")
    generator = record.get("generator_tool", {})
    if not isinstance(generator, dict) or generator.get("provenance_status") != "NOT_CAPTURED" or generator.get("artifact_content_id") is not None:
        issues.append("generator provenance must remain explicitly NOT_CAPTURED for this historical run")

    expected = {
        "01-missing-paren": ("ACC-STRUCT-002", "F1_STRUCTURAL_CHANGE_SAFETY", "FAIL", "PASS", "DETECTED_AND_STATICALLY_RECHECKED", "ISOLATED_GIT_WORKTREE", True, "SATISFIED_WITHIN_STATIC_MVP", "PASS_STATIC_ONLY"),
        "02-truncated-tail": ("ACC-STRUCT-003", "F1_STRUCTURAL_CHANGE_SAFETY", "FAIL", "PASS", "DETECTED_AND_STATICALLY_RECHECKED", "ISOLATED_GIT_WORKTREE", True, "SATISFIED_WITHIN_STATIC_MVP", "PASS_STATIC_ONLY"),
        "03-missing-include": ("ACC-BUILD-002", "F2_BUILD_TARGET_AND_DEPENDENCY", "INCONCLUSIVE", "INCONCLUSIVE", "STATIC_BLIND_SPOT_RESTORED_BY_DIFF_ONLY", "ISOLATED_GIT_WORKTREE", True, "NOT_SATISFIED", "INCONCLUSIVE"),
        "04-source-not-in-target": ("ACC-BUILD-001", "F2_BUILD_TARGET_AND_DEPENDENCY", "FAIL", "INCONCLUSIVE", "MANUAL_MANIFEST_GAP_DETECTED_AND_STATICALLY_RECHECKED", "ISOLATED_GIT_WORKTREE", True, "NOT_SATISFIED", "INCONCLUSIVE"),
        "05-external-compiler-error": ("ACC-EXT-001", "F5_EXTERNAL_EVIDENCE_RECONCILIATION", "INCONCLUSIVE", "INCONCLUSIVE", "EXTERNAL_FIXTURE_RETAINED_UNRESOLVED", "ACCEPTANCE_FIXTURE", False, "NOT_SATISFIED", "INCONCLUSIVE"),
    }
    evidence_root: Path | None = None
    if external_evidence_root is not None:
        candidate_root = external_evidence_root.expanduser()
        if not candidate_root.is_absolute():
            issues.append("runtime external evidence root must be an absolute path")
        elif not candidate_root.is_dir():
            issues.append("runtime external evidence root is unavailable; hashes and report semantics cannot be reverified")
        else:
            evidence_root = candidate_root.resolve()
    elif require_external_evidence:
        issues.append(
            "runtime external evidence root is required for artifact reverification; "
            "provide --cpp-evidence-root or EET_CPP_EVIDENCE_ROOT"
        )

    def verify_external_artifact(reference: Any, label: str) -> Path | None:
        if not isinstance(reference, dict) or evidence_root is None:
            return None
        raw_path = reference.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            issues.append(f"{label} has no path")
            return None
        supplied = Path(raw_path)
        if supplied.is_absolute() or ".." in supplied.parts:
            issues.append(f"{label} escapes the declared evidence root")
            return None
        path = (evidence_root / supplied).resolve()
        if evidence_root not in path.parents or not path.is_file():
            issues.append(f"{label} is missing below the declared evidence root")
            return None
        actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
        if reference.get("content_id") != actual:
            issues.append(f"{label} content_id is stale or forged")
            return None
        return path
    raw_scenarios = record.get("scenarios", [])
    scenarios = [item for item in raw_scenarios if isinstance(item, dict)] if isinstance(raw_scenarios, list) else []
    scenario_ids = [item.get("scenario_id") for item in scenarios]
    string_ids = [item for item in scenario_ids if isinstance(item, str)]
    duplicates = sorted({item for item in string_ids if string_ids.count(item) > 1})
    if duplicates:
        issues.append(f"duplicate real validation scenario ids: {duplicates}")
    if set(string_ids) != set(expected):
        issues.append(f"real validation scenario set mismatch: {sorted(string_ids)}")
    for scenario in scenarios:
        scenario_id = scenario.get("scenario_id")
        rule = expected.get(scenario_id)
        if rule is None:
            continue
        case, gate_id, before_status, after_status, outcome, source, fixed_expected, case_coverage, case_result = rule
        if scenario.get("acceptance_case") != case:
            issues.append(f"{scenario_id} must bind {case}")
        if scenario.get("outcome") != outcome:
            issues.append(f"{scenario_id} outcome must be {outcome}")
        if scenario.get("evidence_source") != source:
            issues.append(f"{scenario_id} evidence source must be {source}")
        if scenario.get("case_coverage") != case_coverage or scenario.get("case_result") != case_result:
            issues.append(f"{scenario_id} case coverage/result overstates the static evidence")
        has_fixed = scenario.get("fixed_observation_content_id") is not None
        if has_fixed != fixed_expected:
            issues.append(f"{scenario_id} fixed observation presence is inconsistent")
        defect_observation_path = verify_external_artifact(
            scenario.get("defect_observation_file"),
            f"{scenario_id} defect observation",
        )
        fixed_observation_path = verify_external_artifact(
            scenario.get("fixed_observation_file"),
            f"{scenario_id} fixed observation",
        ) if has_fixed else None
        if evidence_root is not None:
            for observation_path, expected_content_id, phase in (
                (defect_observation_path, scenario.get("defect_observation_content_id"), "defect"),
                (fixed_observation_path, scenario.get("fixed_observation_content_id"), "fixed"),
            ):
                if observation_path is None:
                    if phase == "defect" or has_fixed:
                        issues.append(f"{scenario_id} {phase} observation cannot be verified")
                    continue
                try:
                    observation = json.loads(observation_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    observation = None
                if not isinstance(observation, dict) or observation.get("observation_content_id") != expected_content_id:
                    issues.append(f"{scenario_id} {phase} observation content object does not match its declared ID")
        before = scenario.get("before", {})
        after = scenario.get("after", {})
        before_gates = before.get("gates", {}) if isinstance(before, dict) else {}
        after_gates = after.get("gates", {}) if isinstance(after, dict) else {}
        if not isinstance(before_gates, dict) or before_gates.get(gate_id) != before_status:
            issues.append(f"{scenario_id} before {gate_id} must be {before_status}")
        if not isinstance(after_gates, dict) or after_gates.get(gate_id) != after_status:
            issues.append(f"{scenario_id} after {gate_id} must be {after_status}")
        if scenario.get("formal_build_status") != "BLOCKED_BY_ENVIRONMENT":
            issues.append(f"{scenario_id} cannot claim a formal build result in this environment")
        if evidence_root is not None:
            for phase, report in (("before", before), ("after", after)):
                if not isinstance(report, dict):
                    continue
                artifact_files = report.get("artifact_files", {})
                if not isinstance(artifact_files, dict):
                    issues.append(f"{scenario_id} {phase} report artifact manifest is missing")
                    continue
                machine_ref = artifact_files.get("machine")
                if isinstance(machine_ref, dict) and machine_ref.get("content_id") != report.get("machine_report_content_id"):
                    issues.append(f"{scenario_id} {phase} machine report ID differs from its file manifest")
                machine_path = verify_external_artifact(machine_ref, f"{scenario_id} {phase} machine report")
                professional_path = verify_external_artifact(
                    artifact_files.get("professional"), f"{scenario_id} {phase} professional report"
                )
                plain_path = verify_external_artifact(
                    artifact_files.get("plain_language"), f"{scenario_id} {phase} plain-language report"
                )
                try:
                    machine = json.loads(machine_path.read_text(encoding="utf-8")) if machine_path is not None else None
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    machine = None
                if not isinstance(machine, dict):
                    issues.append(f"{scenario_id} {phase} machine report cannot be parsed")
                    continue
                machine_gates = {
                    item.get("gate_id"): item.get("gate_status")
                    for item in machine.get("gates", [])
                    if isinstance(item, dict)
                }
                machine_codes = [
                    item.get("code") for item in machine.get("findings", []) if isinstance(item, dict)
                ]
                workspace_snapshot = machine.get("workspace_snapshot", {})
                target_manifest = workspace_snapshot.get("target_manifest", {}) if isinstance(workspace_snapshot, dict) else {}
                if (
                    machine.get("fact_set_hash") != report.get("fact_set_hash")
                    or machine_gates != report.get("gates")
                    or machine_codes != report.get("finding_codes")
                    or target_manifest.get("content_id") != report.get("target_manifest_content_id")
                    or workspace_snapshot.get("workspace_content_id") != report.get("workspace_content_id")
                ):
                    issues.append(f"{scenario_id} {phase} machine report semantics differ from REAL_VALIDATION")
                for human_path, audience in ((professional_path, "professional"), (plain_path, "plain-language")):
                    if human_path is not None and report.get("fact_set_hash") not in human_path.read_text(encoding="utf-8", errors="replace"):
                        issues.append(f"{scenario_id} {phase} {audience} report does not bind the shared fact set")
        if scenario_id == "05-external-compiler-error":
            before_codes = before.get("finding_codes", []) if isinstance(before, dict) else []
            after_codes = after.get("finding_codes", []) if isinstance(after, dict) else []
            if "USER_ERROR_UNRESOLVED" not in before_codes or "USER_ERROR_UNRESOLVED" not in after_codes:
                issues.append("external compiler-error fixture must remain unresolved before and after")
            if before.get("fact_set_hash") != after.get("fact_set_hash"):
                issues.append("unmodified external-error fixture should preserve the same fact set")
    return issues


def validate_cpp_acceptance_records(
    findings: Findings,
    *,
    external_evidence_root: Path | None = None,
    require_external_evidence: bool = False,
) -> None:
    selection = load_yaml(ROOT / "acceptance/cpp-target-selection/CANDIDATE_SELECTION.yaml", findings)
    record = load_yaml(ROOT / "acceptance/cpp-target-selection/REAL_VALIDATION.yaml", findings)
    for issue in cpp_candidate_selection_issues(selection):
        findings.error("CPP_CANDIDATE_SELECTION", issue)
    for issue in cpp_real_validation_issues(
        record,
        selection,
        external_evidence_root=external_evidence_root,
        require_external_evidence=require_external_evidence,
    ):
        findings.error("CPP_REAL_VALIDATION", issue)


def manifest_entries(manifest: dict[str, Any], collection: str) -> list[dict[str, Any]]:
    entries = manifest.get(collection, [])
    return entries if isinstance(entries, list) else []


def validate_status_dimensions(
    data: dict[str, Any],
    item_id: str,
    findings: Findings,
    *,
    required: bool,
    observed_at_ceiling: datetime | None = None,
) -> None:
    status = data.get("status")
    if status not in ALLOWED_MODULE_STATES:
        findings.error("SPEC_STATUS", f"{item_id} has invalid high-level status {status!r}")
    dimensions = data.get("status_dimensions")
    if dimensions is None and not required:
        return
    if not isinstance(dimensions, dict):
        findings.error("STATUS_DIMENSIONS", f"{item_id} must separate specification/implementation/validation/activation status")
        return
    allowed = {
        "specification_status": {"DRAFT", "DESIGNED", "REVIEWED", "BASELINED"},
        "implementation_status": {"NOT_IMPLEMENTED", "PARTIAL", "IMPLEMENTED"},
        "validation_status": {"NOT_RUN", "PARTIAL", "PASSED", "FAILED", "STALE"},
        "qualification_status": {"NOT_ASSESSED", "UNQUALIFIED", "QUALIFIED_WITH_LIMITS", "QUALIFIED"},
        "activation_status": {"INACTIVE", "ACTIVE", "SUSPENDED", "RETIRED"},
    }
    for field, values in allowed.items():
        if dimensions.get(field) not in values:
            findings.error(
                "STATUS_DIMENSIONS",
                f"{item_id}.{field}={dimensions.get(field)!r}; allowed={sorted(values)}",
            )

    status_evidence = data.get("status_evidence", {})
    if not isinstance(status_evidence, dict):
        findings.error("STATUS_EVIDENCE", f"{item_id}.status_evidence must be a mapping")
        status_evidence = {}
    authority_registry_path = ROOT / "governance/TRUSTED_AUTHORITY_REGISTRY.yaml"
    try:
        authority_registry_document = yaml.safe_load(authority_registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        authority_registry_document = {}
    trusted_status_authorities = {
        authority.get("authority_ref"): authority
        for authority in authority_registry_document.get("authorities", [])
        if isinstance(authority_registry_document, dict)
        and isinstance(authority, dict)
        and isinstance(authority.get("authority_ref"), str)
    }
    promotions = (
        ("implementation_status", {"PARTIAL", "IMPLEMENTED"}, "implementation"),
        ("validation_status", {"PARTIAL", "PASSED", "FAILED", "STALE"}, "validation"),
        (
            "qualification_status",
            {"UNQUALIFIED", "QUALIFIED_WITH_LIMITS", "QUALIFIED"},
            "qualification",
        ),
        ("activation_status", {"ACTIVE", "SUSPENDED", "RETIRED"}, "activation"),
    )
    expected_kind = {
        ("implementation", "PARTIAL"): "IMPLEMENTATION_ARTIFACT",
        ("implementation", "IMPLEMENTED"): "IMPLEMENTATION_RECEIPT",
        ("validation", "PARTIAL"): "TEST_RECEIPT",
        ("validation", "PASSED"): "TEST_RECEIPT",
        ("validation", "FAILED"): "TEST_RECEIPT",
        ("validation", "STALE"): "TEST_RECEIPT",
        ("qualification", "UNQUALIFIED"): "QUALIFICATION_RECEIPT",
        ("qualification", "QUALIFIED_WITH_LIMITS"): "QUALIFICATION_RECEIPT",
        ("qualification", "QUALIFIED"): "QUALIFICATION_RECEIPT",
        ("activation", "ACTIVE"): "ACTIVATION_RECEIPT",
        ("activation", "SUSPENDED"): "ACTIVATION_RECEIPT",
        ("activation", "RETIRED"): "ACTIVATION_RECEIPT",
    }
    observation_ceiling = observed_at_ceiling or datetime.now(timezone.utc)
    if observation_ceiling.tzinfo is None:
        observation_ceiling = observation_ceiling.replace(tzinfo=timezone.utc)
    else:
        observation_ceiling = observation_ceiling.astimezone(timezone.utc)

    def verify_observed_at(value: Any, label: str) -> None:
        if not isinstance(value, str) or not value:
            findings.error("STATUS_EVIDENCE_TIME", f"{label} has no observed_at timestamp")
            return
        try:
            observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            findings.error("STATUS_EVIDENCE_TIME", f"{label} has invalid observed_at={value!r}")
            return
        if observed.tzinfo is None:
            findings.error("STATUS_EVIDENCE_TIME", f"{label} observed_at must include a timezone")
            return
        if observed.astimezone(timezone.utc) > observation_ceiling + timedelta(minutes=5):
            findings.error(
                "STATUS_EVIDENCE_FUTURE",
                f"{label} observed_at={value!r} is later than the validation clock plus five-minute skew",
            )

    def verify_dependency(reference: Any, label: str) -> Path | None:
        if not isinstance(reference, dict):
            findings.error("STATUS_EVIDENCE_REF", f"{label} must be a typed content-addressed object")
            return None
        path_text = reference.get("path")
        if not isinstance(path_text, str) or not path_text:
            findings.error("STATUS_EVIDENCE_REF", f"{label} has no repository-relative path")
            return None
        supplied = Path(path_text)
        candidate = (ROOT / supplied).resolve()
        if supplied.is_absolute() or ".." in supplied.parts or (candidate != ROOT.resolve() and ROOT.resolve() not in candidate.parents):
            findings.error("STATUS_EVIDENCE_REF", f"{label} escapes toolkit root: {path_text}")
            return None
        if not candidate.is_file():
            findings.error("STATUS_EVIDENCE_REF", f"{label} missing evidence: {path_text}")
            return None
        actual = "sha256:" + hashlib.sha256(candidate.read_bytes()).hexdigest()
        if reference.get("content_id") != actual:
            findings.error("STATUS_EVIDENCE_DIGEST", f"{label} has stale or forged content_id")
            return None
        return candidate

    def verify_status_receipt(reference: dict[str, Any], path: Path, axis: str, result: str) -> None:
        try:
            document = json.loads(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".json" else yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, yaml.YAMLError) as exc:
            findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id}.{axis} receipt cannot be parsed: {exc}")
            return
        if not isinstance(document, dict):
            findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id}.{axis} receipt is not an object")
            return
        common = (
            document.get("schema_version") == "1.0.0"
            and document.get("kind") == "StatusEvidenceReceipt"
            and document.get("subject_id") == item_id
            and document.get("status_axis") == axis
            and document.get("evidence_kind") == reference.get("evidence_kind")
            and document.get("result") == result
            and document.get("observed_at") == reference.get("observed_at")
        )
        if not common:
            findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id}.{axis} receipt identity/result does not match the manifest")
        dependencies = document.get("dependencies")
        if not isinstance(dependencies, list) or not dependencies:
            findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id}.{axis} receipt has no content-addressed dependencies")
        else:
            for index, dependency in enumerate(dependencies):
                verify_dependency(dependency, f"{item_id}.{axis}.dependencies[{index}]")
        if reference.get("evidence_kind") == "TEST_RECEIPT":
            checks = document.get("checks") if isinstance(document.get("checks"), dict) else {}
            passed = checks.get("passed")
            total = checks.get("total")
            command = document.get("command")
            valid_test_shape = (
                isinstance(command, list)
                and bool(command)
                and all(isinstance(part, str) and part for part in command)
                and isinstance(passed, int)
                and isinstance(total, int)
                and total > 0
                and 0 <= passed <= total
            )
            if not valid_test_shape:
                findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id}.{axis} Test Receipt lacks command/check counts")
            if result == "PASSED" and (
                document.get("scope") != "FULL_DECLARED"
                or document.get("exit_code") != 0
                or passed != total
            ):
                findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id}.{axis}=PASSED requires a full successful Test Receipt")
            if result == "PARTIAL" and document.get("scope") != "FOCUSED_SUBSET":
                findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id}.{axis}=PARTIAL requires scope=FOCUSED_SUBSET")
        elif reference.get("evidence_kind") == "IMPLEMENTATION_RECEIPT":
            if document.get("scope") != "FULL_DECLARED" or document.get("decision") != "IMPLEMENTED":
                findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id} IMPLEMENTED lacks a full Implementation Receipt")
        elif reference.get("evidence_kind") == "QUALIFICATION_RECEIPT":
            authority = trusted_status_authorities.get(document.get("authority_ref"))
            trusted = bool(
                isinstance(authority, dict)
                and authority.get("status") == "ACTIVE"
                and "STATUS_QUALIFICATION" in authority.get("permissions", [])
                and item_id in authority.get("status_subject_ids", [])
                and reference.get("content_id") in authority.get("status_receipt_content_ids", [])
                and document.get("issued_by") == authority.get("issuer_id")
            )
            if not trusted or document.get("decision") != result:
                findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id} qualification lacks an authority-bound decision")
        elif reference.get("evidence_kind") == "ACTIVATION_RECEIPT":
            authority = trusted_status_authorities.get(document.get("authority_ref"))
            trusted = bool(
                isinstance(authority, dict)
                and authority.get("status") == "ACTIVE"
                and "STATUS_ACTIVATION" in authority.get("permissions", [])
                and item_id in authority.get("status_subject_ids", [])
                and reference.get("content_id") in authority.get("status_receipt_content_ids", [])
                and document.get("issued_by") == authority.get("issuer_id")
            )
            if not trusted or document.get("decision") != result:
                findings.error("STATUS_EVIDENCE_RECEIPT", f"{item_id} activation lacks an authority-bound decision")

    for dimension, promoted_values, evidence_field in promotions:
        dimension_value = dimensions.get(dimension)
        if dimension_value in promoted_values:
            refs = status_evidence.get(evidence_field)
            if not isinstance(refs, list) or not refs or not all(isinstance(ref, dict) for ref in refs):
                findings.error(
                    "STATUS_PROMOTION_WITHOUT_EVIDENCE",
                    f"{item_id}.{dimension}={dimension_value!r} requires typed status_evidence.{evidence_field}",
                )
                continue
            for index, ref in enumerate(refs):
                verify_observed_at(ref.get("observed_at"), f"{item_id}.{evidence_field}[{index}]")
                expected = expected_kind.get((evidence_field, str(dimension_value)))
                if (
                    ref.get("subject_id") != item_id
                    or ref.get("status_axis") != evidence_field
                    or ref.get("result") != dimension_value
                    or ref.get("evidence_kind") != expected
                ):
                    findings.error(
                        "STATUS_EVIDENCE_TYPE",
                        f"{item_id}.{evidence_field}[{index}] does not match axis/result/kind {expected}",
                    )
                candidate = verify_dependency(ref, f"{item_id}.{evidence_field}[{index}]")
                if candidate is not None and ref.get("evidence_kind") != "IMPLEMENTATION_ARTIFACT":
                    verify_status_receipt(ref, candidate, evidence_field, str(dimension_value))

    implementation = dimensions.get("implementation_status")
    validation = dimensions.get("validation_status")
    qualification = dimensions.get("qualification_status")
    activation = dimensions.get("activation_status")
    if validation != "NOT_RUN" and implementation == "NOT_IMPLEMENTED":
        findings.error("STATUS_ORDER", f"{item_id} cannot validate before implementation")
    if validation == "PASSED" and implementation != "IMPLEMENTED":
        findings.error("STATUS_ORDER", f"{item_id} PASSED requires IMPLEMENTED")
    if qualification != "NOT_ASSESSED" and validation != "PASSED":
        findings.error("STATUS_ORDER", f"{item_id} qualification requires PASSED validation")
    if activation in {"ACTIVE", "SUSPENDED", "RETIRED"} and qualification != "QUALIFIED":
        findings.error("STATUS_ORDER", f"{item_id} {activation} requires QUALIFIED")

    if activation == "ACTIVE":
        derived_status = "ACTIVE"
    elif validation == "PASSED":
        derived_status = "VALIDATED"
    elif implementation == "IMPLEMENTED":
        derived_status = "IMPLEMENTED"
    elif implementation == "PARTIAL" or validation == "PARTIAL":
        derived_status = "SCAFFOLDED"
    else:
        derived_status = "DESIGNED"
    if status != derived_status:
        findings.error("STATUS_ROLLUP", f"{item_id} stored={status!r} derived={derived_status!r}")


def profile_capability_refs(data: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    capabilities = data.get("capabilities", {})
    if not isinstance(capabilities, dict):
        return refs
    required = capabilities.get("required", [])
    if isinstance(required, list):
        refs.update(value for value in required if isinstance(value, str))
    conditional = capabilities.get("conditional", [])
    if isinstance(conditional, list):
        for item in conditional:
            if isinstance(item, dict) and isinstance(item.get("capability"), str):
                refs.add(item["capability"])
    return refs


def runbook_capability_refs(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "invoke" and isinstance(value, str):
                yield value
            elif key in {"invokes", "conditional_invokes"} and isinstance(value, list):
                yield from (item for item in value if isinstance(item, str))
            else:
                yield from runbook_capability_refs(value)
    elif isinstance(node, list):
        for item in node:
            yield from runbook_capability_refs(item)


def mapping_key_paths(node: Any, prefix: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            yield key_text, path
            yield from mapping_key_paths(value, path)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from mapping_key_paths(item, f"{prefix}[{index}]")


def validate_manifest(findings: Findings) -> None:
    path = ROOT / "TOOLKIT_MANIFEST.yaml"
    manifest = load_yaml(path, findings)
    if not isinstance(manifest, dict):
        findings.error("MANIFEST_SHAPE", "TOOLKIT_MANIFEST.yaml must be a mapping")
        return

    required_root_fields = {
        "api_version", "kind", "metadata", "status_dimensions", "status_evidence", "architecture",
        "entrypoint", "state_file", "shared_contracts", "capabilities", "profiles",
        "adapters", "harness_support_matrix", "lifecycle", "runtime_boundaries",
        "canonical_policy", "canonical_projection_policy", "assurance_policies",
    }
    missing_root = required_root_fields - set(manifest)
    if missing_root:
        findings.error("MANIFEST_FIELDS", f"missing fields: {sorted(missing_root)}")

    declared_contracts = manifest.get("shared_contracts", [])
    actual_contracts = {
        rel(path).replace("\\", "/")
        for path in (ROOT / "contracts").glob("*.schema.json")
    }
    if not isinstance(declared_contracts, list) or set(declared_contracts) != actual_contracts:
        findings.error(
            "SHARED_CONTRACT_PARITY",
            f"declared_only={sorted(set(declared_contracts or []) - actual_contracts)} "
            f"unregistered={sorted(actual_contracts - set(declared_contracts or []))}",
        )
    policy_paths = manifest.get("assurance_policies", [])
    if not isinstance(policy_paths, list):
        findings.error("ASSURANCE_POLICY_REFS", "assurance_policies must be a list")
    else:
        expected_policy_paths = {
            "policies/quick.yaml",
            "policies/balanced.yaml",
            "policies/strict.yaml",
        }
        if set(policy_paths) != expected_policy_paths:
            findings.error(
                "ASSURANCE_POLICY_REFS",
                f"expected={sorted(expected_policy_paths)} actual={sorted(policy_paths)}",
            )
        for policy_path in policy_paths:
            if not (ROOT / policy_path).is_file():
                findings.error("ASSURANCE_POLICY_REFS", f"missing {policy_path}")

    metadata = manifest.get("metadata", {})
    if not isinstance(metadata, dict):
        findings.error("MANIFEST_METADATA", "metadata must be a mapping")
    else:
        validate_status_dimensions(
            {
                "status": metadata.get("status"),
                "status_dimensions": manifest.get("status_dimensions"),
                "status_evidence": manifest.get("status_evidence"),
            },
            str(metadata.get("id", "toolkit")),
            findings,
            required=True,
        )

    architecture = manifest.get("architecture", {})
    expected_architecture = {
        "style": "COMPOSABLE_CAPABILITIES",
        "default_profile": None,
        "standalone_invocation_enabled": True,
        "profile_required_for_capability_use": False,
        "provider_direct_access_by_profile": False,
        "capability_private_state_sharing": False,
    }
    if not isinstance(architecture, dict):
        findings.error("ARCHITECTURE_POLICY", "architecture must be a mapping")
    else:
        for field, expected in expected_architecture.items():
            actual = architecture.get(field)
            if actual != expected:
                findings.error("ARCHITECTURE_POLICY", f"architecture.{field}={actual!r}; expected {expected!r}")

    projection_policy = manifest.get("canonical_projection_policy", {})
    expected_projection_policy = {
        "capability_source": "capabilities",
        "adapter_projection_is_derivative": True,
        "manual_divergent_copy_forbidden": True,
        "release_parity_check_required": True,
    }
    if not isinstance(projection_policy, dict):
        findings.error("PROJECTION_POLICY", "canonical_projection_policy must be a mapping")
    else:
        for field, expected in expected_projection_policy.items():
            if projection_policy.get(field) != expected:
                findings.error(
                    "PROJECTION_POLICY",
                    f"canonical_projection_policy.{field}={projection_policy.get(field)!r}; expected {expected!r}",
                )

    lifecycle = manifest.get("lifecycle", {})
    if not isinstance(lifecycle, dict) or lifecycle.get("id") != "toolkit-lifecycle" or lifecycle.get("path") != "lifecycle":
        findings.error("LIFECYCLE_REF", "manifest lifecycle must reference toolkit-lifecycle at lifecycle/")
    if manifest.get("harness_support_matrix") != "adapters/HARNESS_CAPABILITY_MATRIX.yaml":
        findings.error("HARNESS_MATRIX_REF", "manifest must reference adapters/HARNESS_CAPABILITY_MATRIX.yaml")

    descriptor_markers = {
        "capabilities": "CAPABILITY.yaml",
        "profiles": "PROFILE.yaml",
        "adapters": "ADAPTER.yaml",
    }
    declared_ids: dict[str, set[str]] = {key: set() for key in descriptor_markers}
    for collection, marker in descriptor_markers.items():
        for entry in manifest_entries(manifest, collection):
            if not isinstance(entry, dict):
                findings.error("MANIFEST_ENTRY", f"{collection} contains a non-mapping entry")
                continue
            item_id = entry.get("id")
            relative = entry.get("path")
            if not isinstance(item_id, str) or not isinstance(relative, str):
                findings.error("MANIFEST_ENTRY", f"{collection} entry lacks string id/path: {entry!r}")
                continue
            if item_id in declared_ids[collection]:
                findings.error("DUPLICATE_ID", f"duplicate {collection} id: {item_id}")
            declared_ids[collection].add(item_id)
            item_root = ROOT / relative
            descriptor = item_root / marker
            if not item_root.is_dir():
                findings.error("MISSING_MODULE", f"{item_id}: {relative}")
                continue
            if not descriptor.exists():
                findings.error("MISSING_DESCRIPTOR", rel(descriptor))
                continue
            data = load_yaml(descriptor, findings)
            if not isinstance(data, dict):
                continue
            if data.get("id") != item_id:
                findings.error("ID_MISMATCH", f"manifest id {item_id!r} != {rel(descriptor)} id {data.get('id')!r}")
            state = data.get("status")
            if state and state not in ALLOWED_MODULE_STATES:
                findings.error("UNKNOWN_MODULE_STATE", f"{item_id}: {state}")
            if collection == "capabilities":
                missing = COMMON_CAPABILITY_FIELDS - set(data)
                if missing:
                    findings.error("CAPABILITY_FIELDS", f"{item_id} missing fields: {sorted(missing)}")
                if data.get("schema_version") != 1 or data.get("kind") != "independent_capability":
                    findings.error("CAPABILITY_FORMAT", f"{item_id} must use schema_version: 1 and kind: independent_capability")
                validate_status_dimensions(data, item_id, findings, required=True)
                entrypoint = data.get("entrypoint", {})
                if not isinstance(entrypoint, dict) or entrypoint.get("callable_without_profile") is not True:
                    findings.error("NOT_STANDALONE", f"{item_id} must be callable without a profile")
            elif collection == "profiles":
                missing = COMMON_PROFILE_FIELDS - set(data)
                if missing:
                    findings.error("PROFILE_FIELDS", f"{item_id} missing fields: {sorted(missing)}")
                if data.get("schema_version") != "1.0.0" or data.get("kind") != "ToolkitProfile":
                    findings.error("PROFILE_FORMAT", f"{item_id} must use schema_version: 1.0.0 and kind: ToolkitProfile")
                validate_status_dimensions(data, item_id, findings, required=True)
                if data.get("capability_internal_access") != "forbidden":
                    findings.error("PROFILE_PRIVATE_ACCESS", f"{item_id} must set capability_internal_access: forbidden")
                if data.get("direct_provider_access") != "forbidden":
                    findings.error("PROFILE_PROVIDER_ACCESS", f"{item_id} must set direct_provider_access: forbidden")
                if item_id in {"recovery-review", "safe-ai-edit"}:
                    policy_ref = data.get("repository_reader_policy")
                    expected_policy = "../../governance/REPOSITORY_READER_AND_NAMING_POLICY.yaml"
                    if policy_ref != expected_policy:
                        findings.error(
                            "REPOSITORY_READER_POLICY_REF",
                            f"{item_id}.repository_reader_policy={policy_ref!r}; expected {expected_policy!r}",
                        )

    discovered_capability_ids = {
        path.parent.name for path in (ROOT / "capabilities").glob("*/CAPABILITY.yaml")
    }
    if discovered_capability_ids != declared_ids["capabilities"]:
        findings.error(
            "CAPABILITY_MANIFEST_PARITY",
            f"declared_only={sorted(declared_ids['capabilities'] - discovered_capability_ids)}; "
            f"descriptor_only={sorted(discovered_capability_ids - declared_ids['capabilities'])}",
        )

    capability_ids = declared_ids["capabilities"]
    for entry in manifest_entries(manifest, "profiles"):
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            continue
        profile_root = ROOT / entry["path"]
        profile_data = load_yaml(profile_root / "PROFILE.yaml", findings)
        if isinstance(profile_data, dict):
            unknown = profile_capability_refs(profile_data) - capability_ids
            for capability_id in sorted(unknown):
                findings.error("UNKNOWN_PROFILE_CAPABILITY", f"{entry.get('id')}: {capability_id}")
        runbook_path = profile_root / "RUNBOOK.yaml"
        if runbook_path.exists():
            runbook = load_yaml(runbook_path, findings)
            unknown = set(runbook_capability_refs(runbook)) - capability_ids
            for capability_id in sorted(unknown):
                findings.error("UNKNOWN_RUNBOOK_CAPABILITY", f"{entry.get('id')}: {capability_id}")


def validate_canonical_runtime_vocabulary(findings: Findings) -> None:
    gate_values = ["PASS", "FAIL", "INCONCLUSIVE", "NOT_APPLICABLE", "WAIVED", "NOT_EVALUATED"]
    verdict_values = ["ACCEPT", "ACCEPT_WITH_RISK", "REJECT", "INCOMPLETE", "NO_VERDICT"]
    execution_values = [
        "NOT_STARTED",
        "BOOTSTRAPPING",
        "READY",
        "RUNNING",
        "WAITING_HUMAN",
        "BLOCKED",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]
    runner = load_yaml(ROOT / "composition/PROFILE_RUNNER_CONTRACT.yaml", findings)
    if isinstance(runner, dict):
        gate_evaluation = runner.get("gate_evaluation", {})
        verdict_evaluation = runner.get("verdict_evaluation", {})
        if not isinstance(gate_evaluation, dict) or gate_evaluation.get("result_values") != gate_values:
            findings.error("RUNTIME_VOCABULARY", "Profile Runner gate values differ from the canonical list")
        if not isinstance(verdict_evaluation, dict) or verdict_evaluation.get("result_values") != verdict_values:
            findings.error("RUNTIME_VOCABULARY", "Profile Runner verdict values differ from the canonical list")
        if runner.get("runtime_states") != execution_values:
            findings.error("RUNTIME_VOCABULARY", "Profile Runner runtime states differ from the canonical list")

    instance_schema = load_json(ROOT / "contracts/instance-state.schema.json", findings)
    if isinstance(instance_schema, dict):
        properties = instance_schema.get("properties", {})
        defs = instance_schema.get("$defs", {})
        instance_execution = properties.get("execution_status", {}).get("enum", [])
        instance_verdicts = properties.get("final_verdict", {}).get("enum", [])
        gate_schema = defs.get("gate_state", {}).get("properties", {}).get("gate_status", {})
        task_schema = defs.get("task_state", {}).get("properties", {}).get("execution_status", {})
        if instance_execution != execution_values or task_schema.get("enum") != execution_values:
            findings.error("RUNTIME_VOCABULARY", "Instance execution states differ from the canonical list")
        if instance_verdicts != verdict_values:
            findings.error("RUNTIME_VOCABULARY", "Instance verdict values differ from the canonical list")
        if gate_schema.get("enum") != gate_values:
            findings.error("RUNTIME_VOCABULARY", "Instance gate values differ from the canonical list")

    for path in sorted((ROOT / "profiles").glob("*/PROFILE.yaml")):
        profile = load_yaml(path, findings)
        if not isinstance(profile, dict):
            continue
        if "gate_result_values" in profile and profile.get("gate_result_values") != gate_values:
            findings.error("RUNTIME_VOCABULARY", f"{rel(path)} has divergent gate values")
        if "final_verdicts" in profile and profile.get("final_verdicts") != verdict_values:
            findings.error("RUNTIME_VOCABULARY", f"{rel(path)} has divergent verdict values")


def validate_code_fact_consistency(findings: Findings) -> None:
    path = ROOT / "capabilities/code-fact/CAPABILITY.yaml"
    data = load_yaml(path, findings)
    if not isinstance(data, dict):
        return
    result_states = data.get("result_states")
    failure_semantics = data.get("failure_semantics", {})
    allowed = failure_semantics.get("allowed_statuses") if isinstance(failure_semantics, dict) else None
    if result_states != allowed:
        findings.error("CODE_FACT_RESULT_DRIFT", "result_states must exactly match failure_semantics.allowed_statuses")
    modes = data.get("modes", {})
    if not isinstance(modes, dict) or set(modes) != {"EXPLORE", "EVIDENCE", "ENFORCE"}:
        findings.error("CODE_FACT_MODES", "Code Fact must declare EXPLORE, EVIDENCE, and ENFORCE modes")


def validate_restored_provider_requirements(findings: Findings) -> None:
    registry_path = ROOT / "capabilities/code-fact/CAPABILITY_PROVIDER_REGISTRY.yaml"
    registry = load_yaml(registry_path, findings)
    if isinstance(registry, dict):
        provider_ids = {
            item.get("provider_id")
            for item in registry.get("providers", [])
            if isinstance(item, dict)
        }
        required = {"zg", "ast-grep", "codegraph", "beh"}
        if not required.issubset(provider_ids):
            findings.error(
                "PROVIDER_REQUIREMENT_DRIFT",
                f"missing provider requirements: {sorted(required - provider_ids)}",
            )
        codegraph = next(
            (
                item
                for item in registry.get("providers", [])
                if isinstance(item, dict) and item.get("provider_id") == "codegraph"
            ),
            {},
        )
        if codegraph.get("canonical_source") != "UNRESOLVED_AMBIGUOUS_NAME":
            findings.error(
                "CODEGRAPH_IDENTITY",
                "CodeGraph must remain unresolved until one canonical source and immutable revision are selected",
            )
    for required_path in (
        "capabilities/code-fact/providers/SELECTION_STRATEGY.yaml",
        "capabilities/code-fact/providers/BEH_PROVIDER_CONTRACT.yaml",
        "contracts/provider-adoption-decision.schema.json",
    ):
        if not (ROOT / required_path).is_file():
            findings.error("PROVIDER_REQUIREMENT_DRIFT", f"missing {required_path}")

    benchmark_path = ROOT / "capabilities/code-fact/benchmark/BENCHMARK_AND_ADJUDICATION.md"
    benchmark_text = benchmark_path.read_text(encoding="utf-8") if benchmark_path.exists() else ""
    benchmark_markers = (
        "exact model ID",
        "canonical prompt content hashes",
        "agent orchestration strategy",
        "complete allowed tool surface",
        "trial count, random seed",
    )
    for marker in benchmark_markers:
        if marker not in benchmark_text:
            findings.error("BENCHMARK_CONTROL_DRIFT", f"missing control variable marker: {marker}")

    requirements = load_yaml(ROOT / "migration/NEW_REQUIREMENTS_AFTER_FREEZE.yaml", findings)
    if isinstance(requirements, dict):
        ids = {
            item.get("id")
            for item in requirements.get("requirements", [])
            if isinstance(item, dict)
        }
        expected_new = {f"EET-NEW-{number:03d}" for number in range(27, 39)}
        if not expected_new.issubset(ids):
            findings.error(
                "NEW_REQUIREMENT_DRIFT",
                f"missing={sorted(expected_new - ids)}",
            )


def validate_outer_runtime_boundary(findings: Findings) -> None:
    manifest = load_yaml(ROOT / "TOOLKIT_MANIFEST.yaml", findings)
    if not isinstance(manifest, dict):
        return
    runtime_boundaries = manifest.get("runtime_boundaries", {})
    expected_ref = "adapters/company-runtime-boundary/ADAPTER.yaml"
    if not isinstance(runtime_boundaries, dict) or runtime_boundaries.get("outer_execution_boundary") != expected_ref:
        findings.error("OUTER_BOUNDARY_REF", f"runtime_boundaries.outer_execution_boundary must be {expected_ref!r}")

    boundary = load_yaml(CANONICAL_RUNTIME_BOUNDARY, findings)
    if not isinstance(boundary, dict):
        findings.error("OUTER_BOUNDARY", f"{rel(CANONICAL_RUNTIME_BOUNDARY)} must be a mapping")
    elif boundary.get("id") != "company-runtime-boundary" or boundary.get("canonical_policy_owner") is not True:
        findings.error("OUTER_BOUNDARY", "company-runtime-boundary must declare canonical_policy_owner: true")

    for path in sorted(ROOT.rglob("*.yaml")):
        if path == CANONICAL_RUNTIME_BOUNDARY:
            continue
        data = load_yaml(path, findings)
        for key, key_path in mapping_key_paths(data):
            if key in DISPERSED_ENVIRONMENT_POLICY_KEYS:
                findings.error(
                    "DISPERSED_ENVIRONMENT_POLICY",
                    f"{rel(path)} at {key_path}: environment policy belongs only to {rel(CANONICAL_RUNTIME_BOUNDARY)}",
                )


def validate_experience_memory(findings: Findings) -> None:
    required_paths = [
        ROOT / "capabilities/experience-memory/CAPABILITY.yaml",
        ROOT / "capabilities/experience-memory/SPEC.md",
        ROOT / "capabilities/experience-memory/PROVIDER_CANDIDATES.yaml",
        ROOT / "capabilities/experience-memory/MVP_GUIDE.md",
        ROOT / "capabilities/third-party-supply-chain/ENVIRONMENT_ASSET_INVENTORY_TEMPLATE.md",
    ]
    for path in required_paths:
        if not path.exists():
            findings.error("MEMORY_REQUIRED_PATH", rel(path))

    capability_path = ROOT / "capabilities/experience-memory/CAPABILITY.yaml"
    data = load_yaml(capability_path, findings)
    if not isinstance(data, dict):
        return
    invariants = data.get("invariants", [])
    invariant_text = " ".join(value for value in invariants if isinstance(value, str))
    required_fragments = ("never upgrades evidence authority", "reverified", "supersede", "scope")
    for fragment in required_fragments:
        if fragment.lower() not in invariant_text.lower():
            findings.error("MEMORY_INVARIANT", f"experience-memory is missing invariant fragment: {fragment!r}")
    if data.get("evidence_ceiling") is None:
        findings.error("MEMORY_EVIDENCE_CEILING", "experience-memory must declare an evidence ceiling")

    registry_path = ROOT / "capabilities/experience-memory/PROVIDER_CANDIDATES.yaml"
    registry = load_yaml(registry_path, findings)
    if isinstance(registry, dict):
        serialized = repr(registry)
        if "'status': 'ACTIVE'" in serialized or "'verification_status': 'PASSED'" in serialized:
            findings.error("MEMORY_FALSE_ACTIVATION", "Memory provider registry may not claim ACTIVE or PASSED before MVP execution")


def validate_lifecycle_manifest(findings: Findings) -> None:
    path = ROOT / "lifecycle/TOOLKIT_LIFECYCLE.yaml"
    data = load_yaml(path, findings)
    if not isinstance(data, dict):
        findings.error("LIFECYCLE_MANIFEST", f"{rel(path)} must be a mapping")
        return
    operations = data.get("operations", [])
    if not isinstance(operations, list):
        findings.error("LIFECYCLE_OPERATIONS", "lifecycle operations must be a list")
        return
    by_id = {
        item.get("id"): item
        for item in operations
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    expected_ids = {"inventory", "plan", "apply", "doctor", "repair", "uninstall"}
    if set(by_id) != expected_ids or len(operations) != len(expected_ids):
        findings.error(
            "LIFECYCLE_OPERATION_PARITY",
            f"expected={sorted(expected_ids)} actual={sorted(by_id)} count={len(operations)}",
        )
        return
    doctor = by_id["doctor"]
    expected_doctor_command = ["python", "tools/toolkit_doctor.py", "--json"]
    if doctor.get("implementation_status") != "IMPLEMENTED":
        findings.error("DOCTOR_STATUS", "doctor implementation must remain visible as IMPLEMENTED")
    if doctor.get("validation_status") != "PASSED":
        findings.error("DOCTOR_STATUS", "doctor focused tests must remain PASSED or the lifecycle state must be downgraded")
    if doctor.get("side_effect") != "READ_ONLY" or doctor.get("command") != expected_doctor_command:
        findings.error("DOCTOR_CONTRACT", f"doctor must be read-only and use {expected_doctor_command!r}")
    for operation_id, operation in by_id.items():
        implementation_status = operation.get("implementation_status")
        validation_status = operation.get("validation_status")
        evidence_refs = operation.get("evidence_refs", [])
        if implementation_status == "IMPLEMENTED":
            if not operation.get("command") or not evidence_refs:
                findings.error(
                    "LIFECYCLE_PROMOTION_WITHOUT_EVIDENCE",
                    f"{operation_id} IMPLEMENTED requires command and evidence_refs",
                )
        if validation_status in {"PASSED", "FAILED", "STALE"} and not evidence_refs:
            findings.error(
                "LIFECYCLE_PROMOTION_WITHOUT_EVIDENCE",
                f"{operation_id} {validation_status} requires evidence_refs",
            )
        if validation_status == "PASSED" and implementation_status != "IMPLEMENTED":
            findings.error(
                "LIFECYCLE_STATUS_ORDER",
                f"{operation_id} cannot be PASSED before implementation",
            )
        for evidence_ref in evidence_refs if isinstance(evidence_refs, list) else []:
            evidence_path = (ROOT / evidence_ref).resolve()
            try:
                evidence_path.relative_to(ROOT.resolve())
            except ValueError:
                findings.error(
                    "LIFECYCLE_EVIDENCE_REF",
                    f"{operation_id} evidence escapes toolkit root: {evidence_ref}",
                )
                continue
            if not evidence_path.exists():
                findings.error(
                    "LIFECYCLE_EVIDENCE_REF",
                    f"{operation_id} missing {evidence_ref}",
                )
        if operation_id in {"apply", "repair", "uninstall"} and operation.get("dry_run_required") is not True:
            findings.error("LIFECYCLE_DRY_RUN", f"{operation_id} must require dry-run")


def validate_harness_support_matrix(findings: Findings) -> None:
    manifest = load_yaml(ROOT / "TOOLKIT_MANIFEST.yaml", findings)
    matrix_path = ROOT / "adapters/HARNESS_CAPABILITY_MATRIX.yaml"
    matrix = load_yaml(matrix_path, findings)
    if not isinstance(manifest, dict) or not isinstance(matrix, dict):
        return
    capability_ids = {
        item.get("id")
        for item in manifest_entries(manifest, "capabilities")
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    adapter_ids = {
        item.get("id")
        for item in manifest_entries(manifest, "adapters")
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    harnesses = matrix.get("harnesses", [])
    if not isinstance(harnesses, list):
        findings.error("HARNESS_MATRIX", "harnesses must be a list")
        return
    seen_adapters: set[str] = set()
    for harness in harnesses:
        if not isinstance(harness, dict):
            findings.error("HARNESS_MATRIX", "harness entry must be a mapping")
            continue
        adapter_id = harness.get("adapter_id")
        if not isinstance(adapter_id, str) or adapter_id not in adapter_ids:
            findings.error("HARNESS_ADAPTER_REF", f"unknown harness adapter: {adapter_id!r}")
            continue
        if adapter_id in seen_adapters:
            findings.error("HARNESS_ADAPTER_DUPLICATE", adapter_id)
        seen_adapters.add(adapter_id)
        runtime_status = harness.get("runtime_validation_status")
        runtime_evidence = harness.get("runtime_evidence", [])
        runtime_limitations = harness.get("runtime_limitations", [])
        if runtime_status != "NOT_RUN":
            if not isinstance(runtime_evidence, list) or not runtime_evidence:
                findings.error(
                    "HARNESS_RUNTIME_EVIDENCE",
                    f"{adapter_id} runtime status {runtime_status!r} requires content-addressed evidence",
                )
            if not isinstance(runtime_limitations, list) or not runtime_limitations:
                findings.error(
                    "HARNESS_RUNTIME_EVIDENCE",
                    f"{adapter_id} runtime status {runtime_status!r} requires explicit limitations",
                )
        if isinstance(runtime_evidence, list):
            for index, reference in enumerate(runtime_evidence):
                label = f"{adapter_id}.runtime_evidence[{index}]"
                if not isinstance(reference, dict):
                    findings.error("HARNESS_RUNTIME_EVIDENCE", f"{label} must be a content-addressed object")
                    continue
                path_text = reference.get("path")
                if not isinstance(path_text, str) or not path_text:
                    findings.error("HARNESS_RUNTIME_EVIDENCE", f"{label} has no path")
                    continue
                supplied = Path(path_text)
                evidence_path = (ROOT / supplied).resolve()
                try:
                    evidence_path.relative_to(ROOT.resolve())
                except ValueError:
                    findings.error("HARNESS_RUNTIME_EVIDENCE", f"{label} escapes toolkit root: {path_text}")
                    continue
                if supplied.is_absolute() or ".." in supplied.parts or not evidence_path.is_file():
                    findings.error("HARNESS_RUNTIME_EVIDENCE", f"{label} missing or unsafe evidence: {path_text}")
                    continue
                actual = "sha256:" + hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                if reference.get("content_id") != actual:
                    findings.error("HARNESS_RUNTIME_EVIDENCE", f"{label} has a stale or forged content_id")
        entries = harness.get("capabilities", [])
        if not isinstance(entries, list):
            findings.error("HARNESS_CAPABILITIES", f"{adapter_id} capabilities must be a list")
            continue
        entry_by_id: dict[str, dict[str, Any]] = {}
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("capability_id"), str):
                findings.error("HARNESS_CAPABILITY_ENTRY", f"{adapter_id} contains an invalid capability entry")
                continue
            capability_id = entry["capability_id"]
            if capability_id in entry_by_id:
                findings.error("HARNESS_CAPABILITY_DUPLICATE", f"{adapter_id}: {capability_id}")
            entry_by_id[capability_id] = entry
            integration_status = entry.get("integration_status")
            validation_status = entry.get("validation_status")
            evidence_refs = entry.get("evidence_refs", [])
            if integration_status == "VERIFIED" or validation_status == "PASSED":
                if integration_status != "VERIFIED" or validation_status != "PASSED" or not evidence_refs:
                    findings.error(
                        "HARNESS_FALSE_VERIFICATION",
                        f"{adapter_id}:{capability_id} VERIFIED requires PASSED validation and evidence refs",
                    )
            if isinstance(evidence_refs, list):
                for evidence_ref in evidence_refs:
                    if not isinstance(evidence_ref, str) or not evidence_ref:
                        continue
                    path_text = evidence_ref.split("#", 1)[0]
                    evidence_path = (ROOT / path_text).resolve()
                    try:
                        evidence_path.relative_to(ROOT.resolve())
                    except ValueError:
                        findings.error(
                            "HARNESS_EVIDENCE_REF",
                            f"{adapter_id}:{capability_id} evidence escapes toolkit root: {evidence_ref}",
                        )
                        continue
                    if not path_text or not evidence_path.exists():
                        findings.error(
                            "HARNESS_EVIDENCE_REF",
                            f"{adapter_id}:{capability_id} missing evidence: {evidence_ref}",
                        )
        if set(entry_by_id) != capability_ids:
            findings.error(
                "HARNESS_CAPABILITY_PARITY",
                f"{adapter_id} missing={sorted(capability_ids - set(entry_by_id))} "
                f"unknown={sorted(set(entry_by_id) - capability_ids)}",
            )

        adapter_path = ROOT / f"adapters/{adapter_id}/ADAPTER.yaml"
        adapter = load_yaml(adapter_path, findings)
        if isinstance(adapter, dict):
            skill_entrypoint = adapter.get("project_skill_entrypoint")
            if not isinstance(skill_entrypoint, dict):
                findings.error("HARNESS_SKILL_ENTRYPOINT", f"{adapter_id} must declare project_skill_entrypoint")
            else:
                skill_ref = skill_entrypoint.get("path")
                skill_path = (ROOT / str(skill_ref)).resolve() if isinstance(skill_ref, str) else None
                if skill_path is None:
                    findings.error("HARNESS_SKILL_ENTRYPOINT", f"{adapter_id} skill path is missing")
                else:
                    try:
                        skill_path.relative_to(ROOT.resolve())
                    except ValueError:
                        findings.error("HARNESS_SKILL_ENTRYPOINT", f"{adapter_id} skill escapes toolkit root: {skill_ref}")
                        skill_path = None
                if skill_path is not None and not skill_path.is_file():
                    findings.error("HARNESS_SKILL_ENTRYPOINT", f"{adapter_id} missing project skill: {skill_ref}")
                elif skill_path is not None:
                    skill_text = skill_path.read_text(encoding="utf-8")
                    required_glm_markers = {
                        "EET_GLM_ROLE=FINAL_COMPATIBILITY_OBSERVER",
                        "EET_GLM_MUST_RUN_AFTER=TOOLKIT_MULTI_ANGLE_REVIEW",
                        "EET_GLM_REVIEW_AUTHORITY=NONE",
                        "EET_GLM_CLAIM_AUTHORITY=NONE",
                        "EET_GLM_GATE_AUTHORITY=NONE",
                        "EET_GLM_QUALIFICATION_AUTHORITY=NONE",
                        "EET_GLM_LIFECYCLE_PROMOTION_AUTHORITY=NONE",
                    }
                    missing_glm_markers = sorted(marker for marker in required_glm_markers if skill_text.count(marker) != 1)
                    if missing_glm_markers:
                        findings.error(
                            "HARNESS_GLM_SKILL_BOUNDARY",
                            f"{skill_ref} is not machine-locked to the no-authority GLM observer boundary: {missing_glm_markers}",
                        )
                    if not skill_text.startswith("---\n") or "\n---\n" not in skill_text[4:]:
                        findings.error("HARNESS_SKILL_FRONTMATTER", f"{skill_ref} must have YAML frontmatter")
                    else:
                        frontmatter_text = skill_text.split("\n---\n", 1)[0][4:]
                        try:
                            frontmatter = yaml.safe_load(frontmatter_text)
                        except yaml.YAMLError as exc:
                            findings.error("HARNESS_SKILL_FRONTMATTER", f"{skill_ref}: {exc}")
                            frontmatter = None
                        if not isinstance(frontmatter, dict):
                            findings.error("HARNESS_SKILL_FRONTMATTER", f"{skill_ref} frontmatter must be a mapping")
                        else:
                            frontmatter_errors = []
                            skill_name = frontmatter.get("name")
                            if skill_name != "engineering-evidence-toolkit":
                                frontmatter_errors.append("name must be engineering-evidence-toolkit")
                            if not isinstance(frontmatter.get("description"), str) or not frontmatter["description"].strip():
                                frontmatter_errors.append("description must be a non-empty string")
                            if not isinstance(frontmatter.get("whenToUse"), str) or not frontmatter["whenToUse"].strip():
                                frontmatter_errors.append("whenToUse must be a non-empty string")
                            for field in ("disable-model-invocation", "user-invocable"):
                                if type(frontmatter.get(field)) is not bool:
                                    frontmatter_errors.append(f"{field} must be a boolean")
                            if skill_path.parent.name != skill_name:
                                frontmatter_errors.append(
                                    f"skill directory {skill_path.parent.name!r} must equal frontmatter name {skill_name!r}"
                                )
                            if frontmatter_errors:
                                findings.error(
                                    "HARNESS_SKILL_FRONTMATTER",
                                    f"{skill_ref}: {'; '.join(frontmatter_errors)}",
                                )
                if (
                    skill_entrypoint.get("discovery_source") != "project-dsh"
                    or skill_entrypoint.get("discovery_rank") != 100
                    or skill_entrypoint.get("file_status") != "PRESENT"
                ):
                    findings.error("HARNESS_SKILL_ENTRYPOINT", f"{adapter_id} project skill discovery metadata drifted")
            expected_glm_observer = {
                "model": "GLM",
                "role": "FINAL_COMPATIBILITY_OBSERVER",
                "must_run_after": "TOOLKIT_MULTI_ANGLE_REVIEW",
                "claim_authority": "NONE",
                "gate_authority": "NONE",
                "qualification_authority": "NONE",
                "lifecycle_promotion_authority": "NONE",
            }
            if adapter.get("glm_compatibility_observer") != expected_glm_observer:
                findings.error(
                    "HARNESS_GLM_BOUNDARY",
                    f"{adapter_id} must keep GLM as the final compatibility observer with no evidence or promotion authority",
                )
            designed_refs = {
                item.get("capability_id")
                for item in adapter.get("supported_capabilities", [])
                if isinstance(item, dict) and isinstance(item.get("capability_id"), str)
            }
            matrix_designed = {
                capability_id
                for capability_id, entry in entry_by_id.items()
                if entry.get("integration_status") in {"DESIGNED", "VERIFIED"}
            }
            if designed_refs != matrix_designed:
                findings.error(
                    "HARNESS_ADAPTER_MATRIX_DRIFT",
                    f"{adapter_id} adapter={sorted(designed_refs)} matrix={sorted(matrix_designed)}",
                )


def validate_capability_progress_dashboard(findings: Findings) -> None:
    dashboard_path = ROOT / "dashboard/capability-progress.html"
    renderer_path = ROOT / "tools/render_capability_dashboard.py"
    if not dashboard_path.exists() or not renderer_path.exists():
        return
    try:
        html = dashboard_path.read_text(encoding="utf-8")
    except Exception as exc:
        findings.error("DASHBOARD_READ", f"{rel(dashboard_path)}: {exc}")
        return

    if re.search(r"<(?:script|link)[^>]+(?:src|href)=[\"']https?://", html, re.IGNORECASE):
        findings.error("DASHBOARD_EXTERNAL_DEPENDENCY", "capability dashboard must remain a zero-network single file")
    match = re.search(
        r'<script id="capabilityData" type="application/json">(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        findings.error("DASHBOARD_DATA", "capability dashboard is missing embedded capabilityData")
        return
    try:
        snapshot = json.loads(match.group(1))
    except Exception as exc:
        findings.error("DASHBOARD_DATA", f"embedded capabilityData is invalid JSON: {exc}")
        return

    capabilities = snapshot.get("capabilities", []) if isinstance(snapshot, dict) else []
    if not isinstance(capabilities, list):
        findings.error("DASHBOARD_DATA", "embedded capabilities must be a list")
        return
    manifest = load_yaml(ROOT / "TOOLKIT_MANIFEST.yaml", findings)
    expected_ids = {
        item.get("id")
        for item in manifest.get("capabilities", [])
        if isinstance(manifest, dict) and isinstance(item, dict)
    } if isinstance(manifest, dict) else set()
    actual_ids = {item.get("id") for item in capabilities if isinstance(item, dict)}
    if actual_ids != expected_ids:
        findings.error(
            "DASHBOARD_CAPABILITY_PARITY",
            f"expected={sorted(expected_ids)} actual={sorted(actual_ids)}",
        )

    formula = snapshot.get("formula", []) if isinstance(snapshot, dict) else []
    if not isinstance(formula, list) or sum(item.get("weight", 0) for item in formula if isinstance(item, dict)) != 100:
        findings.error("DASHBOARD_FORMULA", "progress formula weights must total 100")
    weight_by_key = {
        item.get("key"): item.get("weight")
        for item in formula
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    expected_stage_keys = {"specification", "implementation", "validation", "qualification", "activation"}
    if set(weight_by_key) != expected_stage_keys:
        findings.error("DASHBOARD_FORMULA", f"progress formula axes must be {sorted(expected_stage_keys)}")

    computed_summary = {"complete": 0, "in_progress": 0, "not_started": 0, "unknown": 0}
    for item in capabilities:
        if not isinstance(item, dict):
            continue
        score = item.get("score")
        category = item.get("category")
        stages = item.get("stages", [])
        stage_by_key = {
            stage.get("key"): stage
            for stage in stages
            if isinstance(stage, dict) and isinstance(stage.get("key"), str)
        }
        if set(stage_by_key) != expected_stage_keys:
            findings.error("DASHBOARD_STAGE_PARITY", f"{item.get('id')} does not contain exactly five evidence axes")
            continue
        stage_scores = [stage_by_key[key].get("score") for key in expected_stage_keys]
        known_score = int(round(sum(
            weight_by_key.get(key, 0) * stage_by_key[key].get("score", 0) / 100
            for key in expected_stage_keys
            if stage_by_key[key].get("score") is not None
        )))
        has_unknown = any(value is None for value in stage_scores)
        expected_category = (
            "unknown" if has_unknown else
            "complete" if known_score == 100 else
            "not-started" if known_score == 0 else
            "in-progress"
        )
        if score != known_score:
            findings.error("DASHBOARD_SCORE_DRIFT", f"{item.get('id')} score={score!r}; recomputed={known_score}")
        if category != expected_category:
            code = "DASHBOARD_FALSE_GREEN" if category == "complete" else "DASHBOARD_FALSE_RED" if category == "not-started" else "DASHBOARD_CATEGORY_DRIFT"
            findings.error(code, f"{item.get('id')} category={category!r}; expected={expected_category!r}")
        if category == "complete" and any(value != 100 for value in stage_scores):
            findings.error("DASHBOARD_FALSE_GREEN", f"{item.get('id')} is green without five completed evidence axes")
        if category == "not-started" and any(value != 0 for value in stage_scores):
            findings.error("DASHBOARD_FALSE_RED", f"{item.get('id')} is red without five zero evidence axes")
        if has_unknown and category != "unknown":
            findings.error("DASHBOARD_UNKNOWN_AS_PRECISE", f"{item.get('id')} hides an unknown stage in {category!r}")
        summary_key = expected_category.replace("-", "_")
        if summary_key in computed_summary:
            computed_summary[summary_key] += 1

    embedded_summary = snapshot.get("summary", {}) if isinstance(snapshot, dict) else {}
    for key, expected_count in computed_summary.items():
        if embedded_summary.get(key) != expected_count:
            findings.error("DASHBOARD_SUMMARY_DRIFT", f"summary.{key}={embedded_summary.get(key)!r}; expected={expected_count}")

    static_body = html.split('<script id="capabilityData"', 1)[0]
    missing_static_cards = sorted(
        capability_id for capability_id in expected_ids
        if f'data-id="{capability_id}"' not in static_body
    )
    if missing_static_cards:
        findings.error("DASHBOARD_STATIC_FALLBACK", f"static first view is missing cards: {missing_static_cards}")

    try:
        module_spec = importlib.util.spec_from_file_location("eet_dashboard_renderer", renderer_path)
        if module_spec is None or module_spec.loader is None:
            raise RuntimeError("could not create module spec")
        renderer = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(renderer)
        fresh_snapshot = renderer.build_snapshot()
    except Exception as exc:
        findings.error("DASHBOARD_RENDERER", f"renderer could not recompute snapshot: {exc}")
        return
    if not renderer.snapshots_match(snapshot, fresh_snapshot):
        findings.error(
            "DASHBOARD_STALE_OR_TAMPERED",
            "embedded capability data differs from a complete fresh recomputation; rerender it",
        )


def validate_rule_ids(findings: Findings) -> None:
    rule_pattern = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
    for path in ROOT.rglob("RULE_CATALOG.yaml"):
        data = load_yaml(path, findings)
        if not isinstance(data, dict):
            continue
        seen: set[str] = set()
        for rule in data.get("rules", []):
            if not isinstance(rule, dict):
                findings.error("RULE_SHAPE", f"{rel(path)} contains a non-mapping rule")
                continue
            rule_id = rule.get("id")
            if not isinstance(rule_id, str) or not rule_pattern.match(rule_id):
                findings.error("RULE_ID", f"{rel(path)} invalid id: {rule_id!r}")
            elif rule_id in seen:
                findings.error("DUPLICATE_RULE_ID", f"{rel(path)}: {rule_id}")
            else:
                seen.add(rule_id)
            domain = rule.get("domain")
            if domain == "behavior" and isinstance(rule_id, str) and "-BEHAVIOR-" not in rule_id:
                findings.error(
                    "AMBIGUOUS_BEHAVIOR_ABBREVIATION",
                    f"{rel(path)}: generic behavior rule {rule_id!r} must spell BEHAVIOR in full; "
                    "BEH is reserved for the named BEH product/tool domain",
                )


def validate_repository_reader_policy(findings: Findings) -> None:
    path = ROOT / "governance/REPOSITORY_READER_AND_NAMING_POLICY.yaml"
    data = load_yaml(path, findings)
    if not isinstance(data, dict):
        findings.error("REPOSITORY_READER_POLICY", f"{rel(path)} must be a mapping")
        return
    expected_rule_ids = {
        "EET-NAMING-BEHAVIOR-001",
        "EET-REPOSITORY-READER-001",
        "EET-REPOSITORY-READER-002",
        "EET-REPOSITORY-READER-003",
        "EET-REPOSITORY-READER-004",
    }
    actual_rule_ids: set[str] = set()
    for collection in ("naming_rules", "repository_reader_rules"):
        rules = data.get(collection, [])
        if not isinstance(rules, list):
            findings.error("REPOSITORY_READER_POLICY", f"{rel(path)}.{collection} must be a list")
            continue
        for rule in rules:
            if isinstance(rule, dict) and isinstance(rule.get("id"), str):
                actual_rule_ids.add(rule["id"])
    if actual_rule_ids != expected_rule_ids:
        findings.error(
            "REPOSITORY_READER_POLICY",
            f"{rel(path)} rule ids differ: expected={sorted(expected_rule_ids)} actual={sorted(actual_rule_ids)}",
        )
    required_check = data.get("required_check", {})
    if not isinstance(required_check, dict) or required_check.get("id") != "REPOSITORY_READER_CHECK":
        findings.error("REPOSITORY_READER_POLICY", f"{rel(path)} must define REPOSITORY_READER_CHECK")
    if not isinstance(required_check, dict) or required_check.get("unknown_effect") is None:
        findings.error("REPOSITORY_READER_POLICY", f"{rel(path)} must fail closed on UNKNOWN")


def release_version_issue(label: str, value: Any, formal_release_authorized: bool) -> str | None:
    if not isinstance(value, str) or RELEASE_SEMVER_PATTERN.fullmatch(value) is None:
        return f"{label} must use semantic version text"
    major = int(value.split(".", 1)[0])
    if not formal_release_authorized and major >= 1:
        return f"{label}={value} reaches the reserved formal-release range without explicit user authorization"
    return None


def toolkit_owned_release_versions(root: Path) -> list[tuple[str, Any]]:
    entries: list[tuple[str, Any]] = []
    seen: set[tuple[Path, tuple[str, ...]]] = set()

    def add_yaml(path: Path, keys: tuple[str, ...]) -> None:
        identity = (path, keys)
        if identity in seen or not path.is_file():
            return
        seen.add(identity)
        try:
            value: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            value = None
        for key in keys:
            value = value.get(key) if isinstance(value, dict) else None
        entries.append((f"{path.relative_to(root).as_posix()}:{'.'.join(keys)}", value))

    add_yaml(root / "TOOLKIT_MANIFEST.yaml", ("metadata", "version"))
    add_yaml(root / "CURRENT_STATE.yaml", ("toolkit_version",))
    add_yaml(root / "lifecycle/TOOLKIT_LIFECYCLE.yaml", ("version",))
    add_yaml(root / "adapters/HARNESS_CAPABILITY_MATRIX.yaml", ("version",))
    add_yaml(root / "governance/TRUSTED_AUTHORITY_REGISTRY.yaml", ("version",))
    add_yaml(root / "governance/REPOSITORY_READER_AND_NAMING_POLICY.yaml", ("version",))
    add_yaml(root / "capabilities/code-fact/CAPABILITY_PROVIDER_REGISTRY.yaml", ("registry_version",))
    add_yaml(root / "capabilities/experience-memory/PROVIDER_CANDIDATES.yaml", ("registry_version",))
    for pattern in (
        "capabilities/*/CAPABILITY.yaml",
        "profiles/*/PROFILE.yaml",
        "adapters/*/ADAPTER.yaml",
        "policies/*.yaml",
    ):
        for path in sorted(root.glob(pattern)):
            add_yaml(path, ("version",))

    for relative in (
        "acceptance/TOOLKIT_ACCEPTANCE_PLAN.md",
        "composition/INSTANCE_BUNDLE.md",
        "profiles/README.md",
        "profiles/recovery-review/README.md",
        "runs/README.md",
    ):
        path = root / relative
        if not path.is_file():
            continue
        match = re.search(r"(?m)^document_version:\s*([^\s]+)\s*$", path.read_text(encoding="utf-8"))
        entries.append((f"{relative}:document_version", match.group(1) if match else None))
    return entries


def validate_release_version_policy(findings: Findings) -> None:
    manifest = load_yaml(ROOT / "TOOLKIT_MANIFEST.yaml", findings)
    state = load_yaml(ROOT / "CURRENT_STATE.yaml", findings)
    policy = manifest.get("release_policy", {}) if isinstance(manifest, dict) else {}
    authorized = policy.get("formal_release_authorized") is True if isinstance(policy, dict) else False
    if not isinstance(policy, dict) or policy.get("reserved_formal_release_version") != "1.0.0":
        findings.error("RELEASE_VERSION_POLICY", "1.0.0 must remain reserved for an explicit user-authorized formal release")
    if not isinstance(policy, dict) or policy.get("formal_release_authorized") is not False:
        findings.error("RELEASE_VERSION_POLICY", "formal release must remain unauthorized in the current repository state")
    for label, value in toolkit_owned_release_versions(ROOT):
        issue = release_version_issue(label, value, authorized)
        if issue:
            findings.error("PREMATURE_RELEASE_VERSION", issue)
    manifest_version = manifest.get("metadata", {}).get("version") if isinstance(manifest, dict) else None
    state_version = state.get("toolkit_version") if isinstance(state, dict) else None
    if manifest_version != state_version:
        findings.error("RELEASE_VERSION_DRIFT", "Toolkit Manifest and CURRENT_STATE must use the same release version")


def repository_absolute_path_issues(root: Path) -> list[str]:
    issues: list[str] = []
    excluded_parts = {".git", ".venv", "__pycache__"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in PORTABILITY_TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part in excluded_parts for part in relative.parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(lines, start=1):
            if WINDOWS_ABSOLUTE_PATH_LITERAL.search(line) or POSIX_MACHINE_PATH_LITERAL.search(line):
                issues.append(f"{relative.as_posix()}:{line_number} contains a machine-specific absolute path")
    return issues


def validate_static_boundaries(findings: Findings) -> None:
    for path in ROOT.rglob("*"):
        if path.is_file() and any(marker in path.name for marker in LEGACY_NAME_MARKERS):
            findings.error("LEGACY_COPY", f"legacy monolith copied into active specification: {rel(path)}")
    runs_root = ROOT / "runs"
    if runs_root.exists():
        for path in runs_root.rglob("*"):
            if path.is_file() and path.name != "README.md":
                findings.error("RUNTIME_IN_SPEC", rel(path))
    for issue in repository_absolute_path_issues(ROOT):
        findings.error("MACHINE_SPECIFIC_PATH", issue)


def validate_truthful_state(findings: Findings) -> None:
    path = ROOT / "CURRENT_STATE.yaml"
    state = load_yaml(path, findings)
    if not isinstance(state, dict):
        return
    dimensions = state.get("status_dimensions", {})
    truth = state.get("truthful_summary", {})
    if not isinstance(dimensions, dict) or not isinstance(truth, dict):
        return
    if dimensions.get("activation_status") == "ACTIVE" and not truth.get("acceptance_tests_executed"):
        findings.error("ACTIVE_WITHOUT_TESTS", "toolkit cannot be ACTIVE before acceptance tests execute")
    if truth.get("provider_bindings_active") and not truth.get("real_project_validation_executed"):
        findings.error("PROVIDER_ACTIVE_WITHOUT_VALIDATION", "active provider binding lacks real-project validation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cpp-evidence-root",
        type=Path,
        help="runtime-only absolute root for reopening external C++ validation artifacts",
    )
    parser.add_argument(
        "--require-cpp-evidence",
        action="store_true",
        help="fail closed unless external C++ artifacts are mounted and reverified",
    )
    args = parser.parse_args(argv)
    findings = Findings()
    env_root_text = os.environ.get("EET_CPP_EVIDENCE_ROOT")
    env_root = Path(env_root_text) if env_root_text else None
    cli_root = args.cpp_evidence_root
    if cli_root is not None and env_root is not None:
        if cli_root.expanduser().resolve() != env_root.expanduser().resolve():
            findings.error(
                "CPP_EVIDENCE_ROOT_CONFLICT",
                "--cpp-evidence-root and EET_CPP_EVIDENCE_ROOT resolve to different locations",
            )
    runtime_evidence_root = cli_root if cli_root is not None else env_root
    require_paths(findings)
    parse_all_structured_files(findings)
    validate_machine_contracts(findings)
    validate_cpp_acceptance_records(
        findings,
        external_evidence_root=runtime_evidence_root,
        require_external_evidence=args.require_cpp_evidence,
    )
    validate_manifest(findings)
    validate_canonical_runtime_vocabulary(findings)
    validate_code_fact_consistency(findings)
    validate_restored_provider_requirements(findings)
    validate_outer_runtime_boundary(findings)
    validate_experience_memory(findings)
    validate_lifecycle_manifest(findings)
    validate_harness_support_matrix(findings)
    validate_capability_progress_dashboard(findings)
    validate_rule_ids(findings)
    validate_repository_reader_policy(findings)
    validate_release_version_policy(findings)
    validate_static_boundaries(findings)
    validate_truthful_state(findings)

    print("Engineering Evidence Toolkit specification validation")
    print(f"root: {ROOT}")
    if runtime_evidence_root is None:
        print(
            "cpp_external_evidence: UNMOUNTED; portable metadata was checked, raw external artifacts were not reopened "
            "(bind --cpp-evidence-root or EET_CPP_EVIDENCE_ROOT; use --require-cpp-evidence to fail closed)"
        )
    else:
        print("cpp_external_evidence: RUNTIME_BOUND; external artifacts were required to resolve below the supplied root")
    for item in findings.warnings:
        print(item)
    for item in findings.errors:
        print(item)
    print(f"summary: errors={len(findings.errors)} warnings={len(findings.warnings)}")
    if findings.errors:
        print("RESULT: FAIL: the specification bundle is not internally consistent.")
        return 1
    print("RESULT: PASS: built-in, Draft 2020-12 and RunBundle semantic checks passed.")
    print("No capability implementation or business-code check was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
