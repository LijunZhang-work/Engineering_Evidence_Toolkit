#!/usr/bin/env python3
"""Isolated Profile Runner MVP for bootstrap and an acceptance-fixture safe edit.

The edit path is deliberately narrower than production authorization: it only
accepts repository-pinned fixture authorization/plan bytes and only mutates a
copy below the operating-system temporary directory. It never activates a
Profile, qualifies a company environment, or emits ACCEPT.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

try:
    from tools.windows_precheck_mvp import ROOT, canonical_digest, load_policy, render_reports, run_precheck
except ModuleNotFoundError:  # direct execution from tools/
    from windows_precheck_mvp import ROOT, canonical_digest, load_policy, render_reports, run_precheck


AUTHORIZATION_PATH = ROOT / "acceptance/fixtures/profile-runner/edit-authorization.yaml"
AUTHORIZATION_CONTENT_ID = "sha256:4b2f8ae8ce4e6c9be780e554791cc4e1b4bf03322d7ef3b6ebce6e2454380aad"
PLAN_PATH = ROOT / "acceptance/fixtures/profile-runner/exact-edit-plan.yaml"
PLAN_CONTENT_ID = "sha256:74d2c0aacdafcdecad7546ce0842a95f096b661524918302a483634338b85ce5"
RECORD_SCHEMA = ROOT / "contracts/profile-runner-mvp-record.schema.json"


def file_content_id(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a mapping")
    return value


def below(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    anchor = root.resolve()
    return resolved != anchor and anchor in resolved.parents


def gate_map(result: dict[str, Any]) -> dict[str, str]:
    return {item["gate_id"]: item["gate_status"] for item in result["gates"]}


def phase_record(result: dict[str, Any], report_paths: dict[str, Path]) -> dict[str, Any]:
    return {
        "fact_set_hash": result["fact_set_hash"],
        "workspace_content_id": result["workspace_snapshot"]["workspace_content_id"],
        "gates": gate_map(result),
        "reports": {name: str(path.resolve()) for name, path in report_paths.items()},
    }


def validate_fixture_authorization(authorization_path: Path, plan_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if authorization_path.resolve() != AUTHORIZATION_PATH.resolve() or file_content_id(authorization_path) != AUTHORIZATION_CONTENT_ID:
        raise ValueError("fixture edit authorization is not the repository-pinned object")
    if plan_path.resolve() != PLAN_PATH.resolve() or file_content_id(plan_path) != PLAN_CONTENT_ID:
        raise ValueError("fixture edit plan is not the repository-pinned object")
    authorization = load_mapping(authorization_path)
    plan = load_mapping(plan_path)
    if authorization.get("kind") != "BoundedEditAuthorization" or authorization.get("environment_scope") != "ACCEPTANCE_FIXTURE":
        raise ValueError("only the bounded ACCEPTANCE_FIXTURE authorization is supported")
    if authorization.get("edit_plan", {}).get("content_id") != PLAN_CONTENT_ID:
        raise ValueError("authorization does not bind the exact edit plan")
    expiry = datetime.fromisoformat(str(authorization.get("expires_at")).replace("Z", "+00:00"))
    if datetime.now(timezone.utc) >= expiry:
        raise ValueError("fixture authorization has expired")
    return authorization, plan


def apply_fixture_edit(
    workspace: Path,
    output: Path,
    authorization: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    raw_path = str(plan.get("path", ""))
    logical = Path(raw_path.replace("\\", "/"))
    if logical.is_absolute() or ".." in logical.parts or raw_path not in authorization.get("allowed_paths", []):
        raise ValueError("edit path is outside the fixed authorization")
    target = (workspace / logical).resolve()
    if not below(target, workspace) or not target.is_file():
        raise ValueError("edit target is missing or outside the temporary workspace")
    before = target.read_bytes()
    before_id = "sha256:" + hashlib.sha256(before).hexdigest()
    if before_id != plan.get("expected_input_content_id") or before_id not in authorization.get("expected_input_content_ids", []):
        raise ValueError("edit input bytes differ from the authorized fixture")
    encoding = str(plan.get("encoding", "utf-8"))
    before_text = before.decode(encoding)
    old_text = str(plan.get("old_text"))
    new_text = str(plan.get("new_text"))
    maximum = int(plan.get("maximum_replacements", 0))
    occurrences = before_text.count(old_text)
    if occurrences != 1 or maximum != 1:
        raise ValueError("exact edit requires one and only one authorized match")
    after_text = before_text.replace(old_text, new_text, 1)
    after = after_text.encode(encoding)
    after_id = "sha256:" + hashlib.sha256(after).hexdigest()
    if after_id != plan.get("expected_output_content_id"):
        raise ValueError("edit output bytes differ from the pre-authorized result")
    deleted_lines = max(0, len(before_text.splitlines()) - len(after_text.splitlines()))
    if deleted_lines > int(authorization.get("maximum_deleted_lines", -1)):
        raise ValueError("edit exceeds the authorized deletion budget")
    target.write_bytes(after)
    diff = "".join(difflib.unified_diff(
        before_text.splitlines(keepends=True),
        after_text.splitlines(keepends=True),
        fromfile=f"a/{logical.as_posix()}",
        tofile=f"b/{logical.as_posix()}",
    ))
    diff_path = output / "mutation.diff"
    diff_path.write_text(diff, encoding="utf-8")
    return {
        "status": "APPLIED",
        "changed_paths": [logical.as_posix()],
        "before_content_id": before_id,
        "after_content_id": after_id,
        "deleted_lines": deleted_lines,
        "authorization_content_id": AUTHORIZATION_CONTENT_ID,
        "plan_content_id": PLAN_CONTENT_ID,
        "diff": {"path": str(diff_path.resolve()), "content_id": file_content_id(diff_path)},
    }


def run_profile(
    workspace: Path,
    target_manifest: Path,
    output: Path,
    *,
    policy_id: str = "balanced",
    policy_path: Path | None = None,
    acceptance_fixture_mutation: bool = False,
    authorization_path: Path | None = None,
    edit_plan_path: Path | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    output = output.resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if acceptance_fixture_mutation and not below(workspace, temporary_root):
        raise ValueError("acceptance fixture mutation is restricted to an OS temporary-directory copy")
    if acceptance_fixture_mutation and not below(output, temporary_root):
        raise ValueError("acceptance fixture run artifacts must stay below the OS temporary directory")
    if (authorization_path is None) != (edit_plan_path is None):
        raise ValueError("authorization and edit plan must be supplied together")
    if authorization_path is not None and not acceptance_fixture_mutation:
        raise ValueError("fixture edit requires explicit acceptance_fixture_mutation=True")
    output.mkdir(parents=True, exist_ok=True)
    states = ["NOT_STARTED", "BOOTSTRAPPING"]
    policy = load_policy(policy_id, policy_path)
    before = run_precheck(workspace, target_manifest, policy_id=policy_id, policy_path=policy_path)
    before_reports = render_reports(before, output / "before")
    states.extend(["READY", "RUNNING"])
    collaboration = {
        "workspace_content_id": before["workspace_snapshot"]["workspace_content_id"],
        "delivery_mode": "SOLO",
        "readiness": "ALL_EXPECTED_CODE_PRESENT",
        "components": [{"component_id": before["target"]["target_id"], "code_availability": "PRESENT"}],
    }
    mutation: dict[str, Any] = {"status": "NOT_APPLICABLE", "changed_paths": []}
    after = before
    after_reports = before_reports
    post = {"status": "NOT_APPLICABLE", "validated_paths": []}
    if authorization_path is not None and edit_plan_path is not None:
        authorization, plan = validate_fixture_authorization(authorization_path.resolve(), edit_plan_path.resolve())
        mutation = apply_fixture_edit(workspace, output, authorization, plan)
        after = run_precheck(workspace, target_manifest, policy_id=policy_id, policy_path=policy_path)
        after_reports = render_reports(after, output / "after")
        after_gates = gate_map(after)
        post_ok = (
            mutation["after_content_id"] == plan["expected_output_content_id"]
            and after["workspace_snapshot"]["workspace_content_id"] != before["workspace_snapshot"]["workspace_content_id"]
            and after_gates.get("F1_STRUCTURAL_CHANGE_SAFETY") == "PASS"
            and after_gates.get("F2_BUILD_TARGET_AND_DEPENDENCY") != "FAIL"
        )
        post = {
            "status": "PASS" if post_ok else "FAIL",
            "validated_paths": mutation["changed_paths"],
            "result_workspace_content_id": after["workspace_snapshot"]["workspace_content_id"],
            "machine_report_content_id": file_content_id(after_reports["machine"]),
        }
    states.append("COMPLETED" if post.get("status") != "FAIL" else "FAILED")
    record: dict[str, Any] = {
        "schema_version": "1.0.0",
        "kind": "IsolatedProfileRunnerMvpRecord",
        "run_id": "runner_" + uuid.uuid4().hex,
        "execution_status": states[-1],
        "runtime_states": states,
        "policy": {
            "id": policy["id"], "preset": policy["preset"], "mode": policy["mode"],
            "outcome_authority": policy["outcome_authority"], "content_id": canonical_digest(policy),
        },
        "bootstrap": {
            "request_fields": ["workspace_roots", "profile_ref", "run_policy_ref", "capability_contract_set"],
            "workspace_content_id": before["workspace_snapshot"]["workspace_content_id"],
        },
        "collaboration_snapshot": collaboration,
        "before": phase_record(before, before_reports),
        "mutation": mutation,
        "post_mutation_validation": post,
        "after": phase_record(after, after_reports),
        "final_verdict": after["final_verdict"],
        "limitations": [
            "ACCEPTANCE_FIXTURE_ONLY",
            "NO_PROFILE_ACTIVATION_OR_ACCEPT_AUTHORITY",
            "STATIC_WINDOWS_MVP_ONLY_NO_PRODUCT_BUILD_LINK_DT_OR_RUNTIME_PROOF",
        ],
    }
    record["record_content_id"] = canonical_digest(record)
    schema = json.loads(RECORD_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(record), key=lambda item: list(item.absolute_path))
    if errors:
        raise ValueError("runner record failed schema: " + "; ".join(error.message for error in errors))
    (output / "runner-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--target-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--policy", choices=["quick", "balanced", "strict"])
    group.add_argument("--policy-file", type=Path)
    parser.add_argument("--acceptance-fixture-mutation", action="store_true")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--edit-plan", type=Path)
    args = parser.parse_args()
    try:
        record = run_profile(
            args.workspace, args.target_manifest, args.output,
            policy_id=args.policy or "balanced", policy_path=args.policy_file,
            acceptance_fixture_mutation=args.acceptance_fixture_mutation,
            authorization_path=args.authorization, edit_plan_path=args.edit_plan,
        )
    except Exception as exc:
        print(f"ERROR [RUNNER_MVP_FAILURE] {exc}")
        return 2
    print(json.dumps({"run_id": record["run_id"], "execution_status": record["execution_status"], "final_verdict": record["final_verdict"], "record_content_id": record["record_content_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
