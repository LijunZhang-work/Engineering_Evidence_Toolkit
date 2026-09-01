#!/usr/bin/env python3
"""Validate the static Engineering Evidence Toolkit specification bundle.

A zero exit code means that the available structural checks passed. It never
means that a capability is implemented, activated, or that business code passed.
When ``jsonschema`` is unavailable, the validator emits an explicit warning and
continues with built-in path, identity, status, boundary, and reference checks.
"""

from __future__ import annotations

import json
import importlib.util
import re
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError:
    print("ERROR [DEPENDENCY] PyYAML is required; obtain it only through the configured outer runtime boundary.")
    raise SystemExit(2)

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # Optional enhancement: built-in checks still run truthfully.
    Draft202012Validator = None  # type: ignore[assignment,misc]
    FormatChecker = None  # type: ignore[assignment,misc]


ROOT = Path(__file__).resolve().parents[1]
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
    if Draft202012Validator is None:
        findings.warning(
            "SCHEMA_ENGINE_UNAVAILABLE",
            "jsonschema is not installed; full Draft 2020-12 validation was skipped. "
            "Obtain jsonschema only through the configured outer runtime boundary; no download was attempted.",
        )
        return
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


def manifest_entries(manifest: dict[str, Any], collection: str) -> list[dict[str, Any]]:
    entries = manifest.get(collection, [])
    return entries if isinstance(entries, list) else []


def validate_status_dimensions(
    data: dict[str, Any],
    item_id: str,
    findings: Findings,
    *,
    required: bool,
) -> None:
    if data.get("status") != "DESIGNED":
        findings.error("SPEC_STATUS", f"{item_id} must declare status: DESIGNED")
    dimensions = data.get("status_dimensions")
    if dimensions is None and not required:
        return
    if not isinstance(dimensions, dict):
        findings.error("STATUS_DIMENSIONS", f"{item_id} must separate specification/implementation/validation/activation status")
        return
    expected = {
        "specification_status": "DESIGNED",
        "implementation_status": "NOT_IMPLEMENTED",
        "validation_status": "NOT_RUN",
        "activation_status": "INACTIVE",
    }
    for field, value in expected.items():
        if dimensions.get(field) != value:
            findings.error("STATUS_DIMENSIONS", f"{item_id}.{field}={dimensions.get(field)!r}; expected {value!r}")


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
        "api_version", "kind", "metadata", "status_dimensions", "architecture",
        "entrypoint", "state_file", "shared_contracts", "capabilities", "profiles",
        "adapters", "harness_support_matrix", "lifecycle", "runtime_boundaries",
        "canonical_policy", "canonical_projection_policy",
    }
    missing_root = required_root_fields - set(manifest)
    if missing_root:
        findings.error("MANIFEST_FIELDS", f"missing fields: {sorted(missing_root)}")

    metadata = manifest.get("metadata", {})
    if not isinstance(metadata, dict):
        findings.error("MANIFEST_METADATA", "metadata must be a mapping")
    else:
        validate_status_dimensions(
            {"status": metadata.get("status"), "status_dimensions": manifest.get("status_dimensions")},
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
                validate_status_dimensions(data, item_id, findings, required=(item_id == "code-fact"))
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
    expected_doctor_command = ["python3", "tools/toolkit_doctor.py", "--json"]
    if doctor.get("implementation_status") != "IMPLEMENTED":
        findings.error("DOCTOR_STATUS", "doctor implementation must remain visible as IMPLEMENTED")
    if doctor.get("validation_status") != "PASSED":
        findings.error("DOCTOR_STATUS", "doctor focused tests must remain PASSED or the lifecycle state must be downgraded")
    if doctor.get("side_effect") != "READ_ONLY" or doctor.get("command") != expected_doctor_command:
        findings.error("DOCTOR_CONTRACT", f"doctor must be read-only and use {expected_doctor_command!r}")
    for operation_id in expected_ids - {"doctor"}:
        operation = by_id[operation_id]
        if operation.get("implementation_status") != "NOT_IMPLEMENTED":
            findings.error(
                "LIFECYCLE_FALSE_IMPLEMENTATION",
                f"{operation_id} cannot be marked implemented before an executable and focused tests exist",
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
            if entry.get("integration_status") == "VERIFIED":
                if entry.get("validation_status") != "PASSED" or not entry.get("evidence_refs"):
                    findings.error(
                        "HARNESS_FALSE_VERIFICATION",
                        f"{adapter_id}:{capability_id} VERIFIED requires PASSED validation and evidence refs",
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
    if snapshot.get("source_digest") != fresh_snapshot.get("source_digest"):
        findings.error("DASHBOARD_STALE", "capability dashboard does not match current manifest/state bytes; rerender it")


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


def validate_static_boundaries(findings: Findings) -> None:
    for path in ROOT.rglob("*"):
        if path.is_file() and any(marker in path.name for marker in LEGACY_NAME_MARKERS):
            findings.error("LEGACY_COPY", f"legacy monolith copied into active specification: {rel(path)}")
    runs_root = ROOT / "runs"
    if runs_root.exists():
        for path in runs_root.rglob("*"):
            if path.is_file() and path.name != "README.md":
                findings.error("RUNTIME_IN_SPEC", rel(path))


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


def main() -> int:
    findings = Findings()
    require_paths(findings)
    parse_all_structured_files(findings)
    validate_machine_contracts(findings)
    validate_manifest(findings)
    validate_code_fact_consistency(findings)
    validate_outer_runtime_boundary(findings)
    validate_experience_memory(findings)
    validate_lifecycle_manifest(findings)
    validate_harness_support_matrix(findings)
    validate_capability_progress_dashboard(findings)
    validate_rule_ids(findings)
    validate_repository_reader_policy(findings)
    validate_static_boundaries(findings)
    validate_truthful_state(findings)

    print("Engineering Evidence Toolkit specification validation")
    print(f"root: {ROOT}")
    for item in findings.warnings:
        print(item)
    for item in findings.errors:
        print(item)
    print(f"summary: errors={len(findings.errors)} warnings={len(findings.warnings)}")
    if findings.errors:
        print("RESULT: FAIL — the specification bundle is not internally consistent.")
        return 1
    if Draft202012Validator is None:
        print("RESULT: PASS_WITH_LIMITATION — built-in checks passed; JSON Schema engine was unavailable.")
    else:
        print("RESULT: PASS — built-in and Draft 2020-12 schema checks passed.")
    print("No capability implementation or business-code check was executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
