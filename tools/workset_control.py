#!/usr/bin/env python3
"""Goal-scoped workset resolver and local human/AI control surface.

The control plane records intent and execution visibility only. It cannot create
engineering evidence, pass a Gate, activate a Capability, or issue a Verdict.
Runtime files live outside the toolkit repository by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import yaml
from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "worksets/WORKSET_CATALOG.yaml"
REQUEST_SCHEMA_PATH = ROOT / "contracts/workset-request.schema.json"
RUN_SCHEMA_PATH = ROOT / "contracts/workset-run-state.schema.json"
CHECKPOINT_SCHEMA_PATH = ROOT / "contracts/workset-step-checkpoint.schema.json"
DASHBOARD_ROOT = ROOT / "dashboard"
VALIDATED_FOR_REUSE = {"PASSED"}
VALIDATED_FOR_LIMITED_USE = {"PARTIAL"}
BUSINESS_EDIT_REQUEST = "REQUEST_SCOPED_BUSINESS_EDIT"
REFERENCE_PATTERN = re.compile(r"^(repo|runtime):([^#]+)#(sha256:[a-f0-9]{64})$")
POLICY_PATHS = {preset: ROOT / "policies" / f"{preset.lower()}.yaml" for preset in ("QUICK", "BALANCED", "STRICT")}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_mapping(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
    else:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def digest_without(value: dict[str, Any], field: str) -> str:
    material = dict(value)
    material.pop(field, None)
    return canonical_digest(material)


def file_content_id(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def verify_artifact_reference(reference: str, runtime: Path) -> Path:
    match = REFERENCE_PATTERN.fullmatch(reference)
    if match is None:
        raise ValueError("reference must be repo:<relative-path>#sha256:<digest> or runtime:<relative-path>#sha256:<digest>")
    namespace, raw_path, expected = match.groups()
    relative = PurePosixPath(raw_path)
    if relative.is_absolute() or not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError(f"reference path is not a safe relative path: {raw_path}")
    base = ROOT if namespace == "repo" else runtime
    target = (base / Path(*relative.parts)).resolve()
    if target == base.resolve() or base.resolve() not in target.parents:
        raise ValueError(f"reference escapes {namespace} root: {raw_path}")
    if not target.is_file():
        raise ValueError(f"referenced artifact does not exist: {reference}")
    actual = file_content_id(target)
    if actual != expected:
        raise ValueError(f"referenced artifact digest mismatch: {reference}")
    return target


def verify_step_checkpoint(reference: str, runtime: Path, run: dict[str, Any], step: dict[str, Any]) -> Path:
    match = REFERENCE_PATTERN.fullmatch(reference)
    if match is None or match.group(1) != "runtime" or not match.group(2).startswith("checkpoints/"):
        raise ValueError("completed steps require a runtime:checkpoints/... WorksetStepCheckpoint reference")
    checkpoint_path = verify_artifact_reference(reference, runtime)
    checkpoint = load_mapping(checkpoint_path)
    validate_object(checkpoint, CHECKPOINT_SCHEMA_PATH)
    bindings = {
        "request_id": run["request_id"],
        "request_intent_digest": run["request_intent_digest"],
        "run_id": run["run_id"],
        "step_id": step["id"],
        "operation": run["operation"],
    }
    for field, expected in bindings.items():
        if checkpoint.get(field) != expected:
            raise ValueError(f"WorksetStepCheckpoint {field} does not match the completed step")
    for artifact in checkpoint["artifacts"]:
        nested = verify_artifact_reference(str(artifact["ref"]), runtime)
        if nested == checkpoint_path:
            raise ValueError("a WorksetStepCheckpoint cannot cite itself as its artifact")
    return checkpoint_path


def create_step_checkpoint(
    runtime_root: Path,
    run_id: str | None,
    step_id: str,
    summary: str,
    artifacts: list[dict[str, str]],
    producer: str = "AI",
) -> tuple[dict[str, Any], str]:
    runtime = resolve_runtime_root(runtime_root)
    latest_path = runtime / "latest-run.json"
    if not latest_path.is_file():
        raise FileNotFoundError(latest_path)
    run = load_mapping(latest_path)
    validate_run(run, runtime)
    selected_run_id = run["run_id"] if run_id is None else require_identifier(run_id, "wsrun_")
    if selected_run_id != run["run_id"]:
        raise ValueError("checkpoints may only be created for the current run")
    step = next((item for item in run["steps"] if item["id"] == step_id), None)
    if step is None:
        raise ValueError(f"unknown step: {step_id}")
    summary = summary.strip()
    if not summary:
        raise ValueError("checkpoint summary must be non-blank")
    if not artifacts:
        raise ValueError("checkpoint requires at least one typed artifact")
    normalized: list[dict[str, str]] = []
    allowed_kinds = {"IMPLEMENTATION_ARTIFACT", "TEST_RECEIPT", "EVIDENCE_BUNDLE", "RUNNER_CHECKPOINT", "LOG", "REPORT"}
    for artifact in artifacts:
        kind = str(artifact.get("kind", "")).upper()
        reference = str(artifact.get("ref", "")).strip()
        if kind not in allowed_kinds:
            raise ValueError(f"unsupported checkpoint artifact kind: {kind}")
        verify_artifact_reference(reference, runtime)
        normalized.append({"kind": kind, "ref": reference})
    checkpoint: dict[str, Any] = {
        "schema_version": "1.0.0",
        "kind": "WorksetStepCheckpoint",
        "checkpoint_id": "wscp_" + secrets.token_hex(12),
        "created_at": utc_now(),
        "request_id": run["request_id"],
        "request_intent_digest": run["request_intent_digest"],
        "run_id": run["run_id"],
        "step_id": step_id,
        "operation": run["operation"],
        "producer": producer.upper(),
        "summary": summary,
        "artifacts": normalized,
    }
    validate_object(checkpoint, CHECKPOINT_SCHEMA_PATH)
    path = runtime / "checkpoints" / run["run_id"] / f"{checkpoint['checkpoint_id']}.json"
    atomic_write_json(path, checkpoint)
    relative = path.relative_to(runtime).as_posix()
    reference = f"runtime:{relative}#{file_content_id(path)}"
    verify_step_checkpoint(reference, runtime, run, step)
    return checkpoint, reference


def validate_object(value: dict[str, Any], schema_path: Path) -> None:
    schema = load_mapping(schema_path)
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda item: list(item.absolute_path),
    )
    if errors:
        detail = "; ".join(f"{'/'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}" for error in errors)
        raise ValueError(f"{schema_path.name} validation failed: {detail}")


def is_below(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    anchor = root.resolve()
    return resolved != anchor and anchor in resolved.parents


def containing_git_repository(path: Path) -> Path | None:
    """Return a containing Git worktree without invoking Git.

    Runtime state must never become untracked content in this toolkit or in an
    unrelated repository selected through EET_RUNTIME_ROOT.
    """

    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def default_runtime_root() -> Path:
    configured = os.environ.get("EET_RUNTIME_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return (base / "EngineeringEvidenceToolkit" / "runtime").resolve()
    base = Path(os.environ.get("XDG_STATE_HOME") or (Path.home() / ".local" / "state"))
    return (base / "engineering-evidence-toolkit" / "runtime").resolve()


def resolve_runtime_root(path: Path | None) -> Path:
    runtime = (path or default_runtime_root()).expanduser().resolve()
    repository = containing_git_repository(runtime)
    if repository is not None:
        raise ValueError(f"runtime root must remain outside every Git repository: {repository}")
    return runtime


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def catalog_snapshot() -> dict[str, Any]:
    catalog = load_mapping(CATALOG_PATH)
    toolkit = load_mapping(ROOT / "TOOLKIT_MANIFEST.yaml")
    registered = {str(item["id"]): item for item in toolkit.get("capabilities", []) if isinstance(item, dict)}
    capabilities: dict[str, dict[str, str]] = {}
    for capability_id, entry in registered.items():
        manifest = load_mapping(ROOT / str(entry["path"]) / "CAPABILITY.yaml")
        dimensions = manifest.get("status_dimensions", {})
        if not isinstance(dimensions, dict):
            dimensions = {}
        capabilities[capability_id] = {
            "implementation_status": str(dimensions.get("implementation_status") or "UNKNOWN"),
            "validation_status": str(dimensions.get("validation_status") or "UNKNOWN"),
        }
    return {"catalog": catalog, "capabilities": capabilities, "registered_ids": sorted(registered)}


def get_workset(goal_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    for workset in snapshot["catalog"].get("worksets", []):
        if isinstance(workset, dict) and workset.get("id") == goal_id:
            return workset
    raise ValueError(f"unknown workset: {goal_id}")


def capability_disposition(implementation: str, validation: str, operation: str) -> str:
    if operation == "BUILD_MISSING":
        return "REUSE" if implementation == "IMPLEMENTED" and validation in VALIDATED_FOR_REUSE else "BUILD_OR_COMPLETE"
    if implementation == "IMPLEMENTED" and validation in VALIDATED_FOR_REUSE:
        return "RUN"
    if implementation in {"PARTIAL", "IMPLEMENTED"} and validation in VALIDATED_FOR_LIMITED_USE:
        return "RUN_LIMITED"
    return "UNAVAILABLE"


def effective_ceiling(workset: dict[str, Any], operation: str, policy: str, selected: list[dict[str, Any]]) -> str:
    ceiling = str(workset.get("conclusion_ceiling", {}).get(operation, "NO_VERDICT"))
    if policy == "QUICK" and operation == "USE_AVAILABLE":
        ceiling = "HINTS_ONLY"
    if any(item["disposition"] == "UNAVAILABLE" for item in selected):
        return "NO_VERDICT"
    if any(item["disposition"] == "RUN_LIMITED" for item in selected):
        return "HINTS_ONLY"
    return ceiling


def executable_steps(workset: dict[str, Any], selected: list[dict[str, Any]], operation: str) -> list[dict[str, Any]]:
    dispositions = {item["id"]: item["disposition"] for item in selected}
    executable = {"RUN", "RUN_LIMITED"} if operation == "USE_AVAILABLE" else {"BUILD_OR_COMPLETE"}
    steps: list[dict[str, Any]] = []
    for step in workset.get("steps", []):
        original_ids = [str(value) for value in step["capability_ids"]]
        capability_ids = [value for value in original_ids if dispositions.get(value) in executable]
        if not capability_ids:
            continue
        limited = len(capability_ids) != len(original_ids)
        title = str(step["title"])
        if operation == "BUILD_MISSING":
            title = f"建设或补齐：{title}"
        elif limited:
            title = f"受限执行：{title}"
        steps.append({"id": str(step["id"]), "title": title, "capability_ids": capability_ids, "status": "PENDING"})
    return steps


def expected_request_semantics(request: dict[str, Any]) -> dict[str, Any]:
    snapshot = catalog_snapshot()
    workset = get_workset(str(request["goal"]["id"]), snapshot)
    operation = str(request["operation"])
    policy = str(request["assurance_preset"])
    permission = str(request["permission"])
    supported = {str(value) for value in workset.get("supported_operations", [])}
    if operation not in supported:
        raise ValueError(f"{workset['id']} does not support operation {operation}")
    if operation == "BUILD_MISSING" and permission != "TOOLKIT_ONLY":
        raise ValueError("BUILD_MISSING requires TOOLKIT_ONLY permission")
    if operation == "USE_AVAILABLE" and permission == "TOOLKIT_ONLY":
        raise ValueError("USE_AVAILABLE requires READ_ONLY or requested business-edit permission")
    if permission == BUSINESS_EDIT_REQUEST and workset["id"] != "safe-ai-edit":
        raise ValueError("business-source edit intent is only valid for the safe-ai-edit workset")

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for capability in workset.get("capabilities", []):
        capability_id = str(capability["id"])
        selected_ids.add(capability_id)
        state = snapshot["capabilities"].get(capability_id)
        if state is None:
            raise ValueError(f"workset references unregistered capability: {capability_id}")
        implementation = state["implementation_status"]
        selected.append(
            {
                "id": capability_id,
                "reason": str(capability["reason"]),
                "implementation_status": implementation,
                "validation_status": state["validation_status"],
                "disposition": capability_disposition(implementation, state["validation_status"], operation),
            }
        )
    excluded = [
        {"id": capability_id, "reason": "不属于本次目标的最小能力闭包；需要时另开工作集。"}
        for capability_id in snapshot["registered_ids"]
        if capability_id not in selected_ids
    ]
    return {
        "goal": {"id": str(workset["id"]), "title": str(workset["title"]), "summary": str(workset["summary"])},
        "catalog_digest": canonical_digest(snapshot["catalog"]),
        "capability_state_digest": canonical_digest(snapshot["capabilities"]),
        "assurance_policy_ref": POLICY_PATHS[policy].relative_to(ROOT).as_posix(),
        "assurance_policy_digest": file_content_id(POLICY_PATHS[policy]),
        "selected_capabilities": selected,
        "excluded_capabilities": excluded,
        "steps": executable_steps(workset, selected, operation),
        "conclusion_ceiling": effective_ceiling(workset, operation, policy, selected),
    }


def validate_request(request: dict[str, Any]) -> None:
    validate_object(request, REQUEST_SCHEMA_PATH)
    if request["intent_digest"] != digest_without(request, "intent_digest"):
        raise ValueError("WorksetRequest intent_digest does not match its content")
    expected = expected_request_semantics(request)
    for field, value in expected.items():
        if request.get(field) != value:
            raise ValueError(f"WorksetRequest {field} no longer matches the pinned catalog and capability state")


def validate_run(run: dict[str, Any], runtime: Path | None = None) -> None:
    validate_object(run, RUN_SCHEMA_PATH)
    if run["state_checksum"] != digest_without(run, "state_checksum"):
        raise ValueError("WorksetRunState state_checksum does not match its content")
    if run["operation"] == "BUILD_MISSING" and run["permission"] != "TOOLKIT_ONLY":
        raise ValueError("BUILD_MISSING run requires TOOLKIT_ONLY permission")
    if run["operation"] == "USE_AVAILABLE" and run["permission"] == "TOOLKIT_ONLY":
        raise ValueError("USE_AVAILABLE run cannot carry toolkit-build permission")
    step_ids = [str(step["id"]) for step in run["steps"]]
    if len(step_ids) != len(set(step_ids)):
        raise ValueError("WorksetRunState step ids must be unique")
    for step in run["steps"]:
        refs = step.get("evidence_refs", [])
        if any(not isinstance(ref, str) or not ref.strip() for ref in refs):
            raise ValueError("evidence/checkpoint references must be non-blank")
        if step["status"] == "COMPLETED" and not refs:
            raise ValueError(f"completed step {step['id']} has no evidence/checkpoint reference")
        if step["status"] == "COMPLETED" and runtime is not None:
            for reference in refs:
                verify_step_checkpoint(reference, runtime, run, step)
    status = run["execution_status"]
    statuses = [step["status"] for step in run["steps"]]
    if status == "COMPLETED" and (not statuses or any(value != "COMPLETED" for value in statuses)):
        raise ValueError("COMPLETED requires every planned step to be completed with a reference")
    if status == "CANCELLED" and (not statuses or "SKIPPED" not in statuses or any(value in {"PENDING", "RUNNING"} for value in statuses)):
        raise ValueError("CANCELLED requires a terminal plan with at least one skipped step")
    if status == "BLOCKED" and "BLOCKED" not in statuses and not (not statuses and run.get("blockers")):
        raise ValueError("BLOCKED requires at least one blocked step")
    if status == "FAILED" and "FAILED" not in statuses:
        raise ValueError("FAILED requires at least one failed step")
    current = run.get("current_step_id")
    if current is not None and current not in step_ids:
        raise ValueError("current_step_id must reference a planned step")
    if status == "NO_ACTION" and (run["operation"] != "BUILD_MISSING" or statuses):
        raise ValueError("NO_ACTION is only valid when BUILD_MISSING has no missing-capability steps")
    if status in {"COMPLETED", "CANCELLED", "BLOCKED", "FAILED", "NO_ACTION"} and current is not None:
        raise ValueError(f"terminal coordination status {status} requires current_step_id=null")
    if runtime is not None:
        request_path = runtime / "inbox" / f"{require_identifier(str(run['request_id']), 'wsr_')}.json"
        if not request_path.is_file():
            raise ValueError(f"bound WorksetRequest is missing: {request_path}")
        request = load_mapping(request_path)
        validate_request(request)
        bindings = {
            "request_intent_digest": request["intent_digest"],
            "catalog_digest": request["catalog_digest"],
            "capability_state_digest": request["capability_state_digest"],
            "assurance_policy_ref": request["assurance_policy_ref"],
            "assurance_policy_digest": request["assurance_policy_digest"],
            "goal": {"id": request["goal"]["id"], "title": request["goal"]["title"]},
            "operation": request["operation"],
            "policy": request["assurance_preset"],
            "permission": request["permission"],
            "time_budget_minutes": request["time_budget_minutes"],
            "conclusion_ceiling": request["conclusion_ceiling"],
        }
        for field, expected in bindings.items():
            if run.get(field) != expected:
                raise ValueError(f"WorksetRunState {field} does not match its bound request")
        request_steps = [(step["id"], step["title"], step["capability_ids"]) for step in request["steps"]]
        run_steps = [(step["id"], step["title"], step["capability_ids"]) for step in run["steps"]]
        if run_steps != request_steps:
            raise ValueError("WorksetRunState step plan does not match its bound request")
        expected_omissions = [
            {"id": item["id"], "disposition": item["disposition"], "reason": "当前操作不会调度该能力。"}
            for item in request["selected_capabilities"]
            if item["disposition"] in ({"UNAVAILABLE"} if request["operation"] == "USE_AVAILABLE" else {"REUSE"})
        ]
        if run["omissions"] != expected_omissions:
            raise ValueError("WorksetRunState omissions do not match its bound request")


def require_identifier(value: str, prefix: str) -> str:
    if not re.fullmatch(rf"{re.escape(prefix)}[a-f0-9]{{24}}", value):
        raise ValueError(f"invalid identifier: {value}")
    return value


@contextmanager
def runtime_write_lock(runtime: Path):
    """Take a non-blocking cross-process lock around current-pointer writes."""

    runtime.mkdir(parents=True, exist_ok=True)
    lock_path = runtime / ".control.lock"
    handle = lock_path.open("a+b")
    try:
        handle.seek(0)
        if handle.read(1) == b"":
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise RuntimeError("workset runtime is busy; retry after the current update finishes") from exc
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def resolve_request(
    goal_id: str,
    *,
    operation: str,
    policy: str,
    time_budget_minutes: int,
    permission: str,
    user_note: str = "",
    source: str = "CLI",
) -> dict[str, Any]:
    operation = operation.upper()
    policy = policy.upper()
    permission = permission.upper()
    if policy not in {"QUICK", "BALANCED", "STRICT"}:
        raise ValueError(f"unsupported assurance policy: {policy}")
    if not 5 <= time_budget_minutes <= 1440:
        raise ValueError("time budget must be between 5 and 1440 minutes")
    if permission not in {"READ_ONLY", "TOOLKIT_ONLY", BUSINESS_EDIT_REQUEST}:
        raise ValueError(f"unsupported permission: {permission}")
    seed = {
        "goal": {"id": goal_id},
        "operation": operation,
        "assurance_preset": policy,
        "permission": permission,
    }
    expected = expected_request_semantics(seed)

    request: dict[str, Any] = {
        "schema_version": "1.0.0",
        "kind": "WorksetRequest",
        "request_id": "wsr_" + secrets.token_hex(12),
        "created_at": utc_now(),
        "source": source,
        "goal": expected["goal"],
        "operation": operation,
        "assurance_preset": policy,
        "time_budget_minutes": time_budget_minutes,
        "permission": permission,
        "catalog_digest": expected["catalog_digest"],
        "capability_state_digest": expected["capability_state_digest"],
        "assurance_policy_ref": expected["assurance_policy_ref"],
        "assurance_policy_digest": expected["assurance_policy_digest"],
        "selected_capabilities": expected["selected_capabilities"],
        "excluded_capabilities": expected["excluded_capabilities"],
        "steps": expected["steps"],
        "conclusion_ceiling": expected["conclusion_ceiling"],
        "execution_status": "REQUESTED",
    }
    if user_note.strip():
        request["user_note"] = user_note.strip()
    request["intent_digest"] = canonical_digest(request)
    validate_request(request)
    return request


def persist_request(request: dict[str, Any], runtime_root: Path) -> Path:
    runtime = resolve_runtime_root(runtime_root)
    validate_request(request)
    request_id = require_identifier(str(request["request_id"]), "wsr_")
    path = runtime / "inbox" / f"{request_id}.json"
    with runtime_write_lock(runtime):
        if path.is_file():
            existing = load_mapping(path)
            validate_request(existing)
            if existing != request:
                raise ValueError(f"request id collision: {request_id}")
            latest_path = runtime / "latest-request.json"
            if latest_path.is_file() and load_mapping(latest_path).get("request_id") != request_id:
                raise ValueError("an older request id cannot be replayed as the latest user intent")
        else:
            atomic_write_json(path, request)
        atomic_write_json(runtime / "latest-request.json", request)
    return path


def request_instruction(request: dict[str, Any], request_path: Path | None = None) -> str:
    validate_request(request)
    selected = "、".join(item["id"] for item in request["selected_capabilities"])
    location = str(request_path) if request_path else f"request_id={request['request_id']}"
    instruction = (
        f"请从本工作区的 00_START_HERE.md 开始，读取工作集请求 {location}。"
        f"本次目标是“{request['goal']['title']}”，操作为 {request['operation']}，"
        f"保障档位 {request['assurance_preset']}，时间预算 {request['time_budget_minutes']} 分钟，"
        f"权限 {request['permission']}。只处理最小能力集：{selected}。"
        "不得自行扩大到全部能力；每一步把真实状态写回工作集运行状态，缺证据不得报完成。"
    )
    if request["permission"] == BUSINESS_EDIT_REQUEST:
        instruction += "此处只是申请受控业务修改，不构成修改授权；冻结仓库、路径和基线并取得 typed MutationAuthorization 前不得修改源码。"
    return instruction


def find_request(runtime: Path, request_id: str | None = None) -> tuple[dict[str, Any], Path]:
    path = runtime / "latest-request.json" if request_id is None else runtime / "inbox" / f"{require_identifier(request_id, 'wsr_')}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    request = load_mapping(path)
    validate_request(request)
    return request, path


def latest_visible_state(runtime_root: Path) -> dict[str, Any]:
    """Return the newest user request unless a run for that request exists."""

    runtime = resolve_runtime_root(runtime_root)
    request_path = runtime / "latest-request.json"
    run_path = runtime / "latest-run.json"
    request = load_mapping(request_path) if request_path.is_file() else None
    run = load_mapping(run_path) if run_path.is_file() else None
    if request is not None:
        validate_request(request)
    if run is not None:
        validate_run(run, runtime)
    if request is None:
        return run or {"status": "EMPTY"}
    if run is None or run.get("request_id") == request.get("request_id"):
        return run or request
    request_time = datetime.fromisoformat(str(request["created_at"]).replace("Z", "+00:00"))
    run_time = datetime.fromisoformat(str(run["started_at"]).replace("Z", "+00:00"))
    return request if request_time >= run_time else run


def claim_request(runtime_root: Path, request_id: str | None = None) -> tuple[dict[str, Any], Path]:
    runtime = resolve_runtime_root(runtime_root)
    with runtime_write_lock(runtime):
        request, _ = find_request(runtime, request_id)
        latest_request, _ = find_request(runtime)
        if latest_request["request_id"] != request["request_id"]:
            raise ValueError("only the latest workset request may be claimed")
        runs_dir = runtime / "runs"
        if runs_dir.is_dir():
            matches: list[tuple[dict[str, Any], Path]] = []
            for candidate in runs_dir.glob("wsrun_*.json"):
                existing = load_mapping(candidate)
                validate_run(existing, runtime)
                if existing["request_id"] == request["request_id"]:
                    matches.append((existing, candidate))
            if len(matches) > 1:
                raise ValueError("multiple runs claim the same request; manual reconciliation is required")
            if matches:
                existing, candidate = matches[0]
                if existing["request_intent_digest"] != request["intent_digest"]:
                    raise ValueError("existing run is bound to different request content")
                atomic_write_json(runtime / "latest-run.json", existing)
                return existing, candidate
        now = utc_now()
        omissions = [
            {"id": item["id"], "disposition": item["disposition"], "reason": "当前操作不会调度该能力。"}
            for item in request["selected_capabilities"]
            if item["disposition"] in ({"UNAVAILABLE"} if request["operation"] == "USE_AVAILABLE" else {"REUSE"})
        ]
        blocked = request["operation"] == "USE_AVAILABLE" and not request["steps"]
        no_action = request["operation"] == "BUILD_MISSING" and not request["steps"]
        run: dict[str, Any] = {
            "schema_version": "1.0.0",
            "kind": "WorksetRunState",
            "run_id": "wsrun_" + secrets.token_hex(12),
            "request_id": request["request_id"],
            "request_intent_digest": request["intent_digest"],
            "catalog_digest": request["catalog_digest"],
            "capability_state_digest": request["capability_state_digest"],
            "assurance_policy_ref": request["assurance_policy_ref"],
            "assurance_policy_digest": request["assurance_policy_digest"],
            "goal": {"id": request["goal"]["id"], "title": request["goal"]["title"]},
            "operation": request["operation"],
            "execution_status": "BLOCKED" if blocked else "NO_ACTION" if no_action else "CLAIMED",
            "started_at": now,
            "updated_at": now,
            "revision": 0,
            "policy": request["assurance_preset"],
            "permission": request["permission"],
            "time_budget_minutes": request["time_budget_minutes"],
            "current_step_id": request["steps"][0]["id"] if request["steps"] else None,
            "steps": [
                {
                    "id": step["id"],
                    "title": step["title"],
                    "capability_ids": step["capability_ids"],
                    "status": "PENDING",
                    "why": "该步骤属于已冻结的目标工作集和当前操作。",
                    "done_when": "形成可定位的实现、检查点或 Receipt；状态文字本身不算完成证据。",
                    "evidence_refs": [],
                }
                for step in request["steps"]
            ],
            "omissions": omissions,
            "activity": [
                {"at": request["created_at"], "actor": "SYSTEM", "message": f"控制面接收来源为 {request['source']} 的计划请求；来源标签本身不构成人类授权证明。"},
                {"at": now, "actor": "AI", "message": "AI 已接收工作集，尚未把任何步骤标为完成。"},
            ],
            "blockers": ["当前所选 USE_AVAILABLE 工作集没有可执行能力；需改为建设请求或等待能力可用。"] if blocked else [],
            "conclusion_ceiling": request["conclusion_ceiling"],
        }
        run["state_checksum"] = canonical_digest(run)
        validate_run(run, runtime)
        path = runtime / "runs" / f"{run['run_id']}.json"
        atomic_write_json(path, run)
        atomic_write_json(runtime / "latest-run.json", run)
        return run, path


def update_run(
    runtime_root: Path,
    run_id: str | None,
    step_id: str,
    status: str,
    message: str,
    evidence_refs: list[str],
    expected_revision: int,
) -> tuple[dict[str, Any], Path]:
    runtime = resolve_runtime_root(runtime_root)
    with runtime_write_lock(runtime):
        latest_path = runtime / "latest-run.json"
        if not latest_path.is_file():
            raise FileNotFoundError(latest_path)
        latest = load_mapping(latest_path)
        validate_run(latest, runtime)
        selected_run_id = latest["run_id"] if run_id is None else require_identifier(run_id, "wsrun_")
        if selected_run_id != latest["run_id"]:
            raise ValueError("historical runs are read-only and cannot replace the current run")
        canonical_path = runtime / "runs" / f"{selected_run_id}.json"
        run = load_mapping(canonical_path)
        validate_run(run, runtime)
        latest_request, _ = find_request(runtime)
        if latest_request["request_id"] != run["request_id"]:
            raise ValueError("the run was superseded by a newer workset request and is now read-only")
        if run["revision"] != expected_revision:
            raise ValueError(f"revision conflict: expected {expected_revision}, current {run['revision']}")
        status = status.upper()
        allowed = {"PENDING", "RUNNING", "COMPLETED", "BLOCKED", "SKIPPED", "FAILED"}
        if status not in allowed:
            raise ValueError(f"unsupported step status: {status}")
        message = message.strip()
        if not message:
            raise ValueError("activity message must be non-blank")
        normalized_refs = [value.strip() for value in evidence_refs]
        if any(not value for value in normalized_refs):
            raise ValueError("evidence/checkpoint references must be non-blank")
        target = next((step for step in run["steps"] if step["id"] == step_id), None)
        if target is None:
            raise ValueError(f"unknown step: {step_id}")
        if target["status"] in {"COMPLETED", "SKIPPED"} and status != target["status"]:
            raise ValueError(f"terminal step {step_id} cannot regress from {target['status']}")
        if status == "COMPLETED" and not normalized_refs and not target.get("evidence_refs"):
            raise ValueError("COMPLETED requires at least one evidence or checkpoint reference")
        target["status"] = status
        if normalized_refs:
            target["evidence_refs"] = list(dict.fromkeys([*target.get("evidence_refs", []), *normalized_refs]))
        run["updated_at"] = utc_now()
        run["revision"] += 1
        run["activity"].append({"at": run["updated_at"], "actor": "AI", "message": message})
        running = next((step for step in run["steps"] if step["status"] == "RUNNING"), None)
        pending = next((step for step in run["steps"] if step["status"] == "PENDING"), None)
        if any(step["status"] == "FAILED" for step in run["steps"]):
            run["execution_status"] = "FAILED"
            run["current_step_id"] = None
        elif running or pending:
            run["execution_status"] = "RUNNING"
            run["current_step_id"] = (running or pending)["id"]
        elif any(step["status"] == "BLOCKED" for step in run["steps"]):
            run["execution_status"] = "BLOCKED"
            run["current_step_id"] = None
        elif any(step["status"] == "SKIPPED" for step in run["steps"]):
            run["execution_status"] = "CANCELLED"
            run["current_step_id"] = None
        elif run["steps"] and all(step["status"] == "COMPLETED" for step in run["steps"]):
            run["execution_status"] = "COMPLETED"
            run["current_step_id"] = None
        if status == "BLOCKED":
            run["blockers"].append(f"{step_id}: {message}")
        if not any(step["status"] == "BLOCKED" for step in run["steps"]):
            run["blockers"] = []
        run.pop("state_checksum", None)
        run["state_checksum"] = canonical_digest(run)
        validate_run(run, runtime)
        atomic_write_json(canonical_path, run)
        atomic_write_json(latest_path, run)
        return run, canonical_path


class ConsoleHandler(SimpleHTTPRequestHandler):
    server_version = "EETConsole/0.1"

    def __init__(self, *args: Any, directory: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(DASHBOARD_ROOT), **kwargs)

    @property
    def runtime_root(self) -> Path:
        return self.server.runtime_root  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write("console: " + format % args + "\n")

    def send_json(self, value: dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def trusted_local_url(self, value: str) -> bool:
        try:
            parsed = urlparse(value if "://" in value else f"http://{value}")
            expected_port = int(self.server.server_address[1])  # type: ignore[attr-defined]
            return parsed.hostname in {"127.0.0.1", "localhost"} and (parsed.port or 80) == expected_port
        except (TypeError, ValueError):
            return False

    def trusted_api_request(self, *, mutation: bool = False) -> bool:
        if not self.trusted_local_url(self.headers.get("Host", "")):
            return False
        origin = self.headers.get("Origin")
        return not mutation or origin is None or self.trusted_local_url(origin)

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route.startswith("/api/") and not self.trusted_api_request():
            self.send_json({"error": "untrusted Host"}, HTTPStatus.FORBIDDEN)
            return
        if route == "/api/health":
            self.send_json({"status": "READY", "runtime_root": str(self.runtime_root)})
            return
        if route == "/api/visible/latest":
            try:
                self.send_json(latest_visible_state(self.runtime_root))
            except Exception as exc:
                self.send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
            return
        if route in {"/api/requests/latest", "/api/runs/latest"}:
            filename = "latest-request.json" if "requests" in route else "latest-run.json"
            path = self.runtime_root / filename
            if not path.is_file():
                self.send_json({"status": "EMPTY"})
            else:
                try:
                    value = load_mapping(path)
                    if "requests" in route:
                        validate_request(value)
                    else:
                        validate_run(value, self.runtime_root)
                    self.send_json(value)
                except Exception as exc:
                    self.send_json({"error": str(exc)}, HTTPStatus.CONFLICT)
            return
        if route == "/favicon.ico":
            self.send_response(HTTPStatus.NO_CONTENT)
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            return
        if route == "/":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route != "/api/requests":
            self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
            return
        if not self.trusted_api_request(mutation=True):
            self.send_json({"error": "untrusted Host or Origin"}, HTTPStatus.FORBIDDEN)
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self.send_json({"error": "application/json required"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except (TypeError, ValueError):
            self.send_json({"error": "invalid Content-Length"}, HTTPStatus.BAD_REQUEST)
            return
        if length <= 0 or length > 16_384:
            self.send_json({"error": "invalid request size"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            request = resolve_request(
                str(payload.get("goal_id", "")),
                operation=str(payload.get("operation", "")),
                policy=str(payload.get("policy", "")),
                time_budget_minutes=int(payload.get("time_budget_minutes", 0)),
                permission=str(payload.get("permission", "")),
                user_note=str(payload.get("user_note", "")),
                source="DESKTOP_CONSOLE",
            )
            path = persist_request(request, self.runtime_root)
            self.send_json({"request": request, "request_path": str(path), "ai_instruction": request_instruction(request, path)}, HTTPStatus.CREATED)
        except Exception as exc:
            self.send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def serve(runtime_root: Path, host: str, port: int) -> int:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("the control console may only bind to localhost")
    runtime = resolve_runtime_root(runtime_root)
    runtime.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), ConsoleHandler)
    server.runtime_root = runtime  # type: ignore[attr-defined]
    print(f"Engineering Evidence Toolkit console: http://{host}:{server.server_port}/")
    print(f"Runtime state: {runtime}")
    print("The console records intent and progress only; it does not issue engineering Verdicts.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def print_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, help="External runtime state directory; defaults to a portable per-user location")
    sub = parser.add_subparsers(dest="command", required=True)

    serve_parser = sub.add_parser("serve", help="Serve the desktop console on localhost")
    serve_parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    serve_parser.add_argument("--port", type=int, default=8765)

    resolve_parser = sub.add_parser("resolve", help="Resolve and persist a minimum workset request")
    resolve_parser.add_argument("--goal", required=True)
    resolve_parser.add_argument("--operation", required=True, choices=["USE_AVAILABLE", "BUILD_MISSING"])
    resolve_parser.add_argument("--policy", default="BALANCED", choices=["QUICK", "BALANCED", "STRICT"])
    resolve_parser.add_argument("--budget", type=int, default=45)
    resolve_parser.add_argument("--permission", default="READ_ONLY", choices=["READ_ONLY", "TOOLKIT_ONLY", BUSINESS_EDIT_REQUEST])
    resolve_parser.add_argument("--note", default="")

    inbox_parser = sub.add_parser("inbox", help="Read a validated workset request")
    inbox_parser.add_argument("--request-id")

    claim_parser = sub.add_parser("claim", help="Claim a workset request and create visible run state")
    claim_parser.add_argument("--request-id")

    checkpoint_parser = sub.add_parser("checkpoint", help="Bind a step to typed, content-addressed artifacts")
    checkpoint_parser.add_argument("--run-id")
    checkpoint_parser.add_argument("--step", required=True)
    checkpoint_parser.add_argument("--summary", required=True)
    checkpoint_parser.add_argument("--artifact", action="append", required=True, help="KIND=repo|runtime:<relative-path>#sha256:<digest>")

    update_parser = sub.add_parser("update", help="Update one visible run step")
    update_parser.add_argument("--run-id")
    update_parser.add_argument("--step", required=True)
    update_parser.add_argument("--status", required=True, choices=["PENDING", "RUNNING", "COMPLETED", "BLOCKED", "SKIPPED", "FAILED"])
    update_parser.add_argument("--message", required=True)
    update_parser.add_argument("--evidence", action="append", default=[])
    update_parser.add_argument("--expected-revision", required=True, type=int)

    status_parser = sub.add_parser("status", help="Read latest visible run state")
    status_parser.add_argument("--run-id")

    args = parser.parse_args()
    runtime = resolve_runtime_root(args.runtime_root)
    try:
        if args.command == "serve":
            return serve(runtime, args.host, args.port)
        if args.command == "resolve":
            request = resolve_request(
                args.goal,
                operation=args.operation,
                policy=args.policy,
                time_budget_minutes=args.budget,
                permission=args.permission,
                user_note=args.note,
            )
            path = persist_request(request, runtime)
            print_json({"request": request, "request_path": str(path), "ai_instruction": request_instruction(request, path)})
            return 0
        if args.command == "inbox":
            request, path = find_request(runtime, args.request_id)
            print_json({"request": request, "request_path": str(path), "ai_instruction": request_instruction(request, path)})
            return 0
        if args.command == "claim":
            run, path = claim_request(runtime, args.request_id)
            print_json({"run": run, "run_path": str(path)})
            return 0
        if args.command == "checkpoint":
            artifacts = []
            for value in args.artifact:
                kind, separator, reference = value.partition("=")
                if not separator:
                    raise ValueError("--artifact must use KIND=reference syntax")
                artifacts.append({"kind": kind, "ref": reference})
            checkpoint, reference = create_step_checkpoint(runtime, args.run_id, args.step, args.summary, artifacts)
            print_json({"checkpoint": checkpoint, "checkpoint_ref": reference})
            return 0
        if args.command == "update":
            run, path = update_run(runtime, args.run_id, args.step, args.status, args.message, args.evidence, args.expected_revision)
            print_json({"run": run, "run_path": str(path)})
            return 0
        if args.command == "status":
            path = runtime / "latest-run.json" if not args.run_id else runtime / "runs" / f"{require_identifier(args.run_id, 'wsrun_')}.json"
            run = load_mapping(path)
            validate_run(run, runtime)
            print_json({"run": run, "run_path": str(path)})
            return 0
    except Exception as exc:
        print(f"ERROR [WORKSET_CONTROL] {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
