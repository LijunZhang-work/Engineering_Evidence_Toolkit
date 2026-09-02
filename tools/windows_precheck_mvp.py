#!/usr/bin/env python3
"""Executable Windows-focused vertical MVP for bounded C/C++ prechecks.

This is intentionally smaller than the designed production capabilities. It
freezes bytes, validates an in-memory negative canary, checks structural
boundaries, quoted includes and declared target membership, ingests optional
unverified external-error bytes or an acceptance fixture, then renders three
views from one fact set. A clean result is never
reported as a product build or DT pass.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import platform
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("ERROR [DEPENDENCY] PyYAML is required.") from exc

try:
    from jsonschema import Draft202012Validator
except ImportError as exc:  # pragma: no cover
    raise SystemExit("ERROR [DEPENDENCY] jsonschema is required.") from exc

try:
    from tools.validate_run_bundle_semantic import derive_custom_ceiling
except ModuleNotFoundError:  # direct execution from tools/
    from validate_run_bundle_semantic import derive_custom_ceiling


ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx"}
OPEN_TO_CLOSE = {"(": ")", "[": "]", "{": "}"}
CLOSE_TO_OPEN = {value: key for key, value in OPEN_TO_CLOSE.items()}
TARGET_SCHEMA = ROOT / "capabilities/windows-static-precheck/contracts/target-manifest.schema.json"
RUN_POLICY_SCHEMA = ROOT / "contracts/run-policy.schema.json"


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return digest_bytes(payload)


def relative_posix(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def load_target_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        target = yaml.safe_load(handle)
    if not isinstance(target, dict):
        raise ValueError("target manifest must contain a mapping")
    schema = json.loads(TARGET_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(target), key=lambda item: list(item.absolute_path))
    if errors:
        messages = [f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in errors]
        raise ValueError("invalid target manifest: " + "; ".join(messages))
    return target


def workspace_path(workspace: Path, raw: Any, *, allow_dot: bool = False) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"target path must be a non-empty string: {raw!r}")
    normal = raw.replace("\\", "/")
    if normal == "." and allow_dot:
        candidate = workspace.resolve()
    else:
        logical = Path(normal)
        if logical.is_absolute() or any(part == ".." for part in logical.parts):
            raise ValueError(f"target path escapes workspace: {raw}")
        candidate = (workspace / logical).resolve()
    try:
        candidate.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ValueError(f"target path escapes workspace: {raw}") from exc
    return candidate


def freeze_workspace(
    workspace: Path,
    manifest_path: Path,
    user_error_path: Path | None,
    selected_paths: list[Path] | None = None,
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    candidates = (
        sorted(workspace.rglob("*"))
        if selected_paths is None
        else sorted({path.resolve() for path in selected_paths})
    )
    for path in candidates:
        if not path.is_file():
            continue
        relative = relative_posix(path, workspace)
        data = path.read_bytes()
        files.append({"path": relative, "size_bytes": len(data), "content_id": digest_bytes(data)})
    inputs = {
        "workspace": str(workspace.resolve()),
        "snapshot_scope": "FULL_WORKSPACE" if selected_paths is None else "TARGET_REACHABLE_INPUTS",
        "files": files,
        "target_manifest": {
            "path": str(manifest_path.resolve()),
            "content_id": digest_bytes(manifest_path.read_bytes()),
        },
        "user_error": None
        if user_error_path is None
        else {
            "path": str(user_error_path.resolve()),
            "content_id": digest_bytes(user_error_path.read_bytes()),
        },
    }
    inputs["workspace_content_id"] = canonical_digest(inputs)
    return inputs


def strip_non_code(text: str) -> tuple[str, list[dict[str, Any]]]:
    output = list(text)
    findings: list[dict[str, Any]] = []
    state = "CODE"
    quote_start = 0
    index = 0
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if state == "CODE":
            raw_match = re.match(r'(?:u8|u|U|L)?R"([^\s()\\]{0,16})\(', text[index:])
            previous = text[index - 1] if index else ""
            if raw_match and not (previous.isalnum() or previous == "_"):
                delimiter = raw_match.group(1)
                closing = ")" + delimiter + '"'
                content_start = index + raw_match.end()
                closing_start = text.find(closing, content_start)
                end = len(text) if closing_start < 0 else closing_start + len(closing)
                for raw_index in range(index, end):
                    output[raw_index] = "\n" if text[raw_index] == "\n" else " "
                if closing_start < 0:
                    findings.append(
                        {
                            "code": "UNTERMINATED_RAW_STRING",
                            "offset": index,
                            "message": "Raw string literal reaches end of file before its delimiter.",
                        }
                    )
                index = end
                continue
            if char == "/" and next_char == "/":
                output[index] = output[index + 1] = " "
                state = "LINE_COMMENT"
                index += 2
                continue
            if char == "/" and next_char == "*":
                output[index] = output[index + 1] = " "
                state = "BLOCK_COMMENT"
                quote_start = index
                index += 2
                continue
            if char == '"':
                output[index] = " "
                state = "STRING"
                quote_start = index
                index += 1
                continue
            if char == "'":
                output[index] = " "
                state = "CHAR"
                quote_start = index
                index += 1
                continue
            index += 1
            continue
        if state == "LINE_COMMENT":
            if char == "\n":
                state = "CODE"
            else:
                output[index] = " "
            index += 1
            continue
        if state == "BLOCK_COMMENT":
            if char == "*" and next_char == "/":
                output[index] = output[index + 1] = " "
                state = "CODE"
                index += 2
            else:
                if char != "\n":
                    output[index] = " "
                index += 1
            continue
        if state in {"STRING", "CHAR"}:
            output[index] = "\n" if char == "\n" else " "
            if char == "\\":
                if index + 1 < len(text):
                    output[index + 1] = "\n" if text[index + 1] == "\n" else " "
                index += 2
                continue
            expected = '"' if state == "STRING" else "'"
            if char == expected:
                state = "CODE"
            elif char == "\n":
                findings.append(
                    {
                        "code": "UNTERMINATED_LITERAL",
                        "offset": quote_start,
                        "message": "String or character literal reaches a newline before closing.",
                    }
                )
                state = "CODE"
            index += 1
    if state == "BLOCK_COMMENT":
        findings.append(
            {
                "code": "UNTERMINATED_BLOCK_COMMENT",
                "offset": quote_start,
                "message": "Block comment reaches end of file before closing.",
            }
        )
    elif state in {"STRING", "CHAR"}:
        findings.append(
            {
                "code": "UNTERMINATED_LITERAL",
                "offset": quote_start,
                "message": "String or character literal reaches end of file before closing.",
            }
        )
    return "".join(output), findings


def line_column(text: str, offset: int) -> tuple[int, int]:
    line = text.count("\n", 0, offset) + 1
    last_newline = text.rfind("\n", 0, offset)
    return line, offset - last_newline


def _mask_preprocessor_line(line: str) -> str:
    return "".join(char if char in "\r\n" else " " for char in line)


def preprocessor_variants(
    text: str,
    path: str,
    *,
    limit: int = 128,
) -> tuple[list[str], list[dict[str, Any]]]:
    lines = text.splitlines(keepends=True)
    directive_pattern = re.compile(r"^\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b")
    stack: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    directive_indices: set[int] = set()
    findings: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        match = directive_pattern.match(line)
        if not match:
            continue
        directive = match.group(1)
        directive_indices.add(index)
        if directive in {"if", "ifdef", "ifndef"}:
            stack.append(
                {
                    "opening": directive,
                    "opening_line": index + 1,
                    "branch_start": index + 1,
                    "branches": [],
                    "has_else": False,
                }
            )
        elif directive in {"elif", "else"}:
            if not stack:
                findings.append(
                    {
                        "code": "UNMATCHED_PREPROCESSOR_BRANCH",
                        "path": path,
                        "line": index + 1,
                        "severity": "ERROR",
                        "message": f"#{directive} has no matching opening condition.",
                    }
                )
                continue
            group = stack[-1]
            group["branches"].append((group["branch_start"], index))
            group["branch_start"] = index + 1
            if directive == "else":
                group["has_else"] = True
        else:
            if not stack:
                findings.append(
                    {
                        "code": "UNMATCHED_ENDIF",
                        "path": path,
                        "line": index + 1,
                        "severity": "ERROR",
                        "message": "#endif has no matching opening directive.",
                    }
                )
                continue
            group = stack.pop()
            group["branches"].append((group["branch_start"], index))
            if not group["has_else"]:
                # Without an #else, no branch can be active. Keep that state in
                # the approximation instead of treating the #if body as
                # unconditionally active (notably for #if 0).
                group["branches"].append((index, index))
            groups.append(group)
    for group in stack:
        group["branches"].append((group["branch_start"], len(lines)))
        if not group["has_else"]:
            group["branches"].append((len(lines), len(lines)))
        groups.append(group)
        findings.append(
            {
                "code": "UNCLOSED_PREPROCESSOR_CONDITION",
                "path": path,
                "line": group["opening_line"],
                "severity": "ERROR",
                "message": f"#{group['opening']} is not closed by #endif.",
            }
        )
    if not groups:
        return [text], findings

    branch_counts = [len(group["branches"]) for group in groups]
    total = 1
    for count in branch_counts:
        total *= count
    if total > limit:
        findings.append(
            {
                "code": "PREPROCESSOR_VARIANT_LIMIT",
                "path": path,
                "severity": "WARNING",
                "message": f"{total} conditional variants exceed the analysis limit {limit}; F1 is inconclusive.",
            }
        )
    choices = itertools.islice(itertools.product(*(range(count) for count in branch_counts)), limit)
    variants: list[str] = []
    for choice in choices:
        masked = set(directive_indices)
        for group, selected_branch in zip(groups, choice):
            for branch_index, (start, end) in enumerate(group["branches"]):
                if branch_index != selected_branch:
                    masked.update(range(start, end))
        variants.append(
            "".join(_mask_preprocessor_line(line) if index in masked else line for index, line in enumerate(lines))
        )
    return variants or [text], findings


def _scan_structure_variant(text: str, path: str) -> list[dict[str, Any]]:
    code, findings = strip_non_code(text)
    stack: list[tuple[str, int]] = []
    for offset, char in enumerate(code):
        if char in OPEN_TO_CLOSE:
            stack.append((char, offset))
        elif char in CLOSE_TO_OPEN:
            if not stack or stack[-1][0] != CLOSE_TO_OPEN[char]:
                line, column = line_column(text, offset)
                findings.append(
                    {
                        "code": "MISMATCHED_CLOSING_DELIMITER",
                        "path": path,
                        "line": line,
                        "column": column,
                        "message": f"Unexpected closing delimiter {char}.",
                    }
                )
            else:
                stack.pop()
    for opening, offset in stack:
        line, column = line_column(text, offset)
        findings.append(
            {
                "code": "UNCLOSED_DELIMITER",
                "path": path,
                "line": line,
                "column": column,
                "message": f"{opening} is not closed before end of file.",
            }
        )
    preprocessor: list[tuple[str, int]] = []
    for line_number, line in enumerate(code.splitlines(), start=1):
        match = re.match(r"^\s*#\s*(if|ifdef|ifndef|endif)\b", line)
        if not match:
            continue
        directive = match.group(1)
        if directive in {"if", "ifdef", "ifndef"}:
            preprocessor.append((directive, line_number))
        elif preprocessor:
            preprocessor.pop()
        else:
            findings.append(
                {
                    "code": "UNMATCHED_ENDIF",
                    "path": path,
                    "line": line_number,
                    "message": "#endif has no matching opening directive.",
                }
            )
    for directive, line_number in preprocessor:
        findings.append(
            {
                "code": "UNCLOSED_PREPROCESSOR_CONDITION",
                "path": path,
                "line": line_number,
                "message": f"#{directive} is not closed by #endif.",
            }
        )
    if text and not text.endswith("\n"):
        findings.append(
            {
                "code": "EOF_NEWLINE_MISSING",
                "path": path,
                "line": text.count("\n") + 1,
                "message": "File does not end with a newline; inspect for tail truncation.",
                "severity": "WARNING",
            }
        )
    for finding in findings:
        finding.setdefault("path", path)
        finding.setdefault("severity", "ERROR")
    return findings


def scan_structure(text: str, path: str) -> list[dict[str, Any]]:
    variants, findings = preprocessor_variants(text, path)
    variant_findings: dict[tuple[Any, ...], dict[str, Any]] = {}
    variant_occurrences: dict[tuple[Any, ...], set[int]] = {}
    for variant_index, variant in enumerate(variants):
        for finding in _scan_structure_variant(variant, path):
            key = (
                finding.get("code"),
                finding.get("path", path),
                finding.get("line"),
                finding.get("column"),
                finding.get("severity", "ERROR"),
                finding.get("message"),
            )
            variant_findings.setdefault(key, finding)
            variant_occurrences.setdefault(key, set()).add(variant_index)

    approximation_incomplete = any(
        finding.get("code") == "PREPROCESSOR_VARIANT_LIMIT"
        for finding in findings
    )
    for key, finding in variant_findings.items():
        occurrence_count = len(variant_occurrences[key])
        if (
            finding.get("severity", "ERROR") == "ERROR"
            and len(variants) > 1
            and (approximation_incomplete or occurrence_count < len(variants))
        ):
            finding = dict(finding)
            finding["severity"] = "WARNING"
            finding["certainty"] = "POSSIBLE"
            finding["message"] += (
                " This appears only in an approximate preprocessor variant; "
                "a bound macro configuration or real preprocessor is required to confirm it."
            )
        findings.append(finding)
    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for finding in findings:
        key = (
            finding.get("code"),
            finding.get("path", path),
            finding.get("line"),
            finding.get("column"),
            finding.get("severity", "ERROR"),
            finding.get("message"),
        )
        if key in seen:
            continue
        seen.add(key)
        finding.setdefault("path", path)
        finding.setdefault("severity", "ERROR")
        unique.append(finding)
    return unique


def quoted_includes(text: str) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    in_block_comment = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        cleaned = line
        if in_block_comment:
            if "*/" in cleaned:
                cleaned = cleaned.split("*/", 1)[1]
                in_block_comment = False
            else:
                continue
        while "/*" in cleaned:
            before, after = cleaned.split("/*", 1)
            if "*/" in after:
                cleaned = before + after.split("*/", 1)[1]
            else:
                cleaned = before
                in_block_comment = True
                break
        cleaned = cleaned.split("//", 1)[0]
        match = re.match(r'^\s*#\s*include\s*"([^"]+)"', cleaned)
        if match:
            result.append((line_number, match.group(1)))
    return result


def resolve_include(
    source: Path,
    include: str,
    include_dirs: list[Path],
    workspace: Path,
) -> tuple[Path | None, bool]:
    candidates = [source.parent / include, *(directory / include for directory in include_dirs)]
    outside_workspace = False
    for candidate in candidates:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(workspace.resolve())
        except ValueError:
            outside_workspace = True
            continue
        if resolved.is_file():
            return resolved, False
    return None, outside_workspace


def collect_analysis_scope(
    workspace: Path,
    declared_paths: set[Path],
    include_dirs: list[Path],
) -> tuple[list[Path], list[dict[str, Any]]]:
    pending = sorted(path for path in declared_paths if path.is_file())
    analysis_paths: list[Path] = []
    findings: list[dict[str, Any]] = []
    seen: set[Path] = set()
    while pending:
        path = pending.pop(0).resolve()
        if path in seen:
            continue
        seen.add(path)
        analysis_paths.append(path)
        relative = relative_posix(path, workspace)
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, include in quoted_includes(text):
            resolved, outside_workspace = resolve_include(path, include, include_dirs, workspace)
            if outside_workspace and resolved is None:
                findings.append(
                    {
                        "code": "OUTSIDE_WORKSPACE_INCLUDE",
                        "severity": "ERROR",
                        "path": relative,
                        "line": line_number,
                        "message": f'Quoted include "{include}" resolves outside the frozen workspace.',
                    }
                )
                continue
            if resolved is None:
                findings.append(
                    {
                        "code": "MISSING_QUOTED_INCLUDE",
                        "severity": "ERROR",
                        "path": relative,
                        "line": line_number,
                        "message": f'Quoted include "{include}" cannot be resolved from declared include roots.',
                    }
                )
            elif resolved.suffix.lower() in SOURCE_SUFFIXES and resolved not in seen:
                pending.append(resolved)
                pending.sort()
    return analysis_paths, findings


def run_detector_self_test() -> dict[str, Any]:
    bad = "int deliberately_broken( { return 0; }\n"
    control = 'const char* text = "{ not syntax }"; // }\nint valid() { return 0; }\n'
    bad_findings = scan_structure(bad, "<in-memory-negative-canary>")
    control_findings = [
        finding
        for finding in scan_structure(control, "<in-memory-control>")
        if finding.get("severity") == "ERROR"
    ]
    passed = any(
        finding["code"] in {"UNCLOSED_DELIMITER", "MISMATCHED_CLOSING_DELIMITER"}
        for finding in bad_findings
    ) and not control_findings
    return {
        "status": "PASS" if passed else "FAIL",
        "bad_finding_codes": sorted({finding["code"] for finding in bad_findings}),
        "control_error_codes": sorted({finding["code"] for finding in control_findings}),
        "content_id": canonical_digest({"bad": bad, "control": control}),
    }


# Backward-compatible name; this is explicitly not the end-to-end active Canary.
run_negative_canary = run_detector_self_test


def load_policy(policy_id: str = "balanced", policy_path: Path | None = None) -> dict[str, Any]:
    path = policy_path.resolve() if policy_path is not None else ROOT / f"policies/{policy_id}.yaml"
    if not path.is_file():
        raise ValueError(f"run policy does not exist: {path}")
    with path.open("r", encoding="utf-8") as handle:
        policy = yaml.safe_load(handle)
    if not isinstance(policy, dict):
        raise ValueError(f"{path} must contain a mapping")
    schema = json.loads(RUN_POLICY_SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(policy), key=lambda item: list(item.absolute_path))
    if errors:
        messages = [f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}" for error in errors]
        raise ValueError("invalid run policy: " + "; ".join(messages))
    if policy_path is not None:
        if policy.get("preset") != "CUSTOM":
            raise ValueError("--policy-file must contain preset=CUSTOM; canonical presets use --policy")
        base_path = ROOT / "policies" / f"{str(policy.get('base_preset')).lower()}.yaml"
        if not base_path.is_file():
            raise ValueError(f"Custom policy base preset does not exist: {base_path}")
        with base_path.open("r", encoding="utf-8") as handle:
            base_policy = yaml.safe_load(handle)
        if policy.get("base_policy_content_id") != canonical_digest(base_policy):
            raise ValueError("Custom policy base_policy_content_id does not bind the canonical preset")
        actual = (policy.get("outcome_authority"), policy.get("mode"), policy.get("allowed_final_verdicts"))
        derived = derive_custom_ceiling(policy)
        if actual != derived:
            raise ValueError(f"Custom policy overclaims authority: stored={actual!r}, derived={derived!r}")
    elif policy.get("preset") == "CUSTOM":
        raise ValueError("Custom policy must be supplied with --policy-file")
    return policy


def run_precheck(
    workspace: Path,
    target_manifest_path: Path,
    *,
    policy_id: str = "balanced",
    policy_path: Path | None = None,
    user_error_path: Path | None = None,
    external_error_source: str | None = None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    target_manifest_path = target_manifest_path.resolve()
    if not workspace.is_dir():
        raise ValueError(f"workspace is not a directory: {workspace}")
    if not target_manifest_path.is_file():
        raise ValueError(f"target manifest does not exist: {target_manifest_path}")
    if (user_error_path is None) != (external_error_source is None):
        raise ValueError("--user-error and --external-error-source must be supplied together")
    if external_error_source not in {None, "UNVERIFIED_EXTERNAL", "ACCEPTANCE_FIXTURE"}:
        raise ValueError(f"unsupported external error source: {external_error_source}")
    target = load_target_manifest(target_manifest_path)
    policy = load_policy(policy_id, policy_path)
    requirements = policy["evidence_requirements"]
    canary_required = requirements["active_negative_canary"] is True
    target_scoped_snapshot = requirements["coverage_requirement"] == "BEST_EFFORT"
    detector_self_test = (
        {"status": "NOT_REQUIRED", "content_id": None, "bad_finding_codes": [], "control_error_codes": []}
        if not canary_required
        else run_detector_self_test()
    )
    active_negative_canary = {
        "status": "NOT_REQUIRED" if not canary_required else "NOT_IMPLEMENTED",
        "reason": "The MVP has a detector self-test, but no isolated end-to-end target-routing Canary Receipt yet.",
    }
    findings: list[dict[str, Any]] = []
    fixture_root = (ROOT / "acceptance/fixtures/windows-mvp").resolve()
    target_scope_qualified = False
    if target["scope_kind"] == "FULL_TARGET" and target["source_origin"] == "FIXTURE_DECLARATION":
        try:
            target_manifest_path.relative_to(fixture_root)
            target_scope_qualified = True
        except ValueError:
            target_scope_qualified = False
    elif target["scope_kind"] == "FULL_TARGET" and target["source_origin"] in {
        "CMAKE_FILE_API",
        "BUILD_SYSTEM_EXPORT",
    }:
        # The manifest can bind the identity of a claimed artifact, but the MVP
        # does not yet parse either artifact format and therefore cannot prove
        # that sources/include roots came from the named target. Merely hashing
        # an arbitrary file must never qualify F2.
        target_scope_qualified = False
    if not target_scope_qualified:
        findings.append(
            {
                "code": "TARGET_SCOPE_UNQUALIFIED",
                "severity": "WARNING",
                "path": "<target-manifest>",
                "message": (
                    "Target scope is bounded, manually declared, or lacks a parsed and semantically bound "
                    "build-system artifact; "
                    "F2 cannot PASS."
                ),
            }
        )
    declared_paths = {workspace_path(workspace, item) for item in target["sources"]}
    expected_paths = {workspace_path(workspace, item) for item in target["expected_sources"]}
    declared_sources = {relative_posix(path, workspace) for path in declared_paths}
    expected_sources = {relative_posix(path, workspace) for path in expected_paths}
    include_dirs = [workspace_path(workspace, item, allow_dot=True) for item in target["include_dirs"]]
    for directory in include_dirs:
        if not directory.is_dir():
            findings.append(
                {
                    "code": "DECLARED_INCLUDE_DIR_MISSING",
                    "severity": "ERROR",
                    "path": relative_posix(directory, workspace),
                    "message": "Declared include directory is absent from the frozen workspace.",
                }
            )
    for relative in sorted(expected_sources - declared_sources):
        findings.append(
            {
                "code": "SOURCE_NOT_IN_TARGET",
                "severity": "ERROR",
                "path": relative,
                "message": f"Expected source is absent from target {target.get('target_id', 'UNKNOWN')}.",
            }
        )
    for path in sorted(declared_paths):
        if not path.is_file():
            findings.append(
                {
                    "code": "DECLARED_SOURCE_MISSING",
                    "severity": "ERROR",
                    "path": relative_posix(path, workspace),
                    "message": "Target manifest names a source that is absent from the workspace.",
                }
            )
    analysis_paths, _ = collect_analysis_scope(workspace, declared_paths, include_dirs)
    snapshot = freeze_workspace(
        workspace,
        target_manifest_path,
        user_error_path,
        analysis_paths if target_scoped_snapshot else None,
    )
    stable_analysis_paths, routing_findings = collect_analysis_scope(workspace, declared_paths, include_dirs)
    if set(stable_analysis_paths) != set(analysis_paths):
        findings.append(
            {
                "code": "INPUT_SCOPE_CHANGED_DURING_FREEZE",
                "severity": "ERROR",
                "path": "<target-scope>",
                "message": "The target-reachable input set changed while the snapshot was being established.",
            }
        )
    analysis_paths = stable_analysis_paths
    findings.extend(routing_findings)
    frozen_content_ids = {item["path"]: item["content_id"] for item in snapshot["files"]}
    for path in analysis_paths:
        relative = relative_posix(path, workspace)
        raw = path.read_bytes()
        if frozen_content_ids.get(relative) != digest_bytes(raw):
            findings.append(
                {
                    "code": "INPUT_CHANGED_AFTER_FREEZE",
                    "severity": "ERROR",
                    "path": relative,
                    "message": "Input bytes changed after the snapshot; all derived checks are invalid.",
                }
            )
            continue
        findings.extend(scan_structure(raw.decode("utf-8", errors="replace"), relative))
    if not analysis_paths:
        findings.append(
            {
                "code": "EMPTY_ANALYSIS_SCOPE",
                "severity": "ERROR",
                "path": "<target-manifest>",
                "message": "Target resolves to zero C/C++ analysis units; PASS is forbidden.",
            }
        )

    external_error: dict[str, Any] | None = None
    if user_error_path is not None:
        raw = user_error_path.read_text(encoding="utf-8", errors="replace")
        external_error = {
            "status": "UNRESOLVED",
            "source_class": external_error_source,
            "content_id": digest_bytes(raw.encode("utf-8")),
            "line_count": len(raw.splitlines()),
            "summary": raw.splitlines()[0][:240] if raw.splitlines() else "empty external error",
        }
        findings.append(
            {
                "code": "USER_ERROR_UNRESOLVED",
                "severity": "ERROR",
                "path": str(user_error_path.resolve()),
                "message": (
                    "External failure bytes are preserved, but their provenance is unverified; "
                    "same-snapshot context reconciliation is still required."
                    if external_error_source == "UNVERIFIED_EXTERNAL"
                    else "Acceptance fixture exercises external-error precedence; it is not actual user evidence."
                ),
            }
        )
    if detector_self_test["status"] == "FAIL":
        findings.append(
            {
                "code": "DETECTOR_SELF_TEST_FAILED",
                "severity": "ERROR",
                "path": "<in-memory-detector-self-test>",
                "message": "The structural check did not distinguish the negative canary from its control.",
            }
        )

    for index, finding in enumerate(findings, start=1):
        finding["finding_id"] = f"MVP-{index:03d}"
    structural_codes = {
        "MISMATCHED_CLOSING_DELIMITER",
        "UNCLOSED_DELIMITER",
        "UNMATCHED_ENDIF",
        "UNCLOSED_PREPROCESSOR_CONDITION",
        "UNMATCHED_PREPROCESSOR_BRANCH",
        "UNTERMINATED_LITERAL",
        "UNTERMINATED_RAW_STRING",
        "UNTERMINATED_BLOCK_COMMENT",
        "DETECTOR_SELF_TEST_FAILED",
        "INPUT_CHANGED_AFTER_FREEZE",
        "INPUT_SCOPE_CHANGED_DURING_FREEZE",
    }
    dependency_codes = {
        "SOURCE_NOT_IN_TARGET",
        "DECLARED_SOURCE_MISSING",
        "DECLARED_INCLUDE_DIR_MISSING",
        "MISSING_QUOTED_INCLUDE",
        "OUTSIDE_WORKSPACE_INCLUDE",
        "INPUT_CHANGED_AFTER_FREEZE",
        "INPUT_SCOPE_CHANGED_DURING_FREEZE",
    }
    structural_errors = [
        finding for finding in findings
        if finding["code"] in structural_codes and finding["severity"] == "ERROR"
    ]
    structural_inconclusive = [
        finding for finding in findings
        if finding["code"] == "PREPROCESSOR_VARIANT_LIMIT"
        or finding.get("certainty") == "POSSIBLE"
    ]
    dependency_errors = [
        finding for finding in findings
        if finding["code"] in dependency_codes and finding["severity"] == "ERROR"
    ]
    gates = [
        {
            "gate_id": "F0_CHECK_EFFECTIVENESS",
            "gate_status": (
                "NOT_APPLICABLE"
                if not canary_required
                else "FAIL"
                if detector_self_test["status"] == "FAIL"
                else "INCONCLUSIVE"
            ),
            "finding_ids": [
                finding["finding_id"]
                for finding in findings
                if finding["code"] == "DETECTOR_SELF_TEST_FAILED"
            ],
        },
        {
            "gate_id": "F1_STRUCTURAL_CHANGE_SAFETY",
            "gate_status": (
                "FAIL"
                if structural_errors
                else "INCONCLUSIVE"
                if structural_inconclusive or not analysis_paths
                else "PASS"
            ),
            "finding_ids": [
                finding["finding_id"]
                for finding in [*structural_errors, *structural_inconclusive]
            ],
        },
        {
            "gate_id": "F2_BUILD_TARGET_AND_DEPENDENCY",
            "gate_status": (
                "FAIL"
                if dependency_errors
                else "PASS"
                if analysis_paths and target_scope_qualified
                else "INCONCLUSIVE"
            ),
            "finding_ids": [finding["finding_id"] for finding in dependency_errors],
        },
        {
            "gate_id": "F5_EXTERNAL_EVIDENCE_RECONCILIATION",
            "gate_status": "INCONCLUSIVE" if external_error else "NOT_APPLICABLE",
            "finding_ids": [
                finding["finding_id"]
                for finding in findings
                if finding["code"] == "USER_ERROR_UNRESOLVED"
            ],
        },
    ]
    if policy["mode"] == "ENFORCE":
        verdict = (
            "REJECT"
            if any(gate["gate_status"] == "FAIL" for gate in gates)
            else "INCOMPLETE"
        )
    else:
        verdict = "NO_VERDICT"
    fact_set = {
        "schema_version": "1.0.0",
        "tool": "windows-precheck-vertical-mvp",
        "mvp_scope": [
            "workspace_byte_freeze",
            "policy_scoped_snapshot",
            "delimiter_and_preprocessor_structure",
            "end_of_file_signal",
            "quoted_include_resolution",
            "declared_target_membership",
            "target_routed_reachable_headers",
            "detector_self_test_only",
            "user_error_preservation",
            "three_view_fact_consistency",
        ],
        "policy": {
            "id": policy["id"],
            "version": policy["version"],
            "preset": policy["preset"],
            "content_id": canonical_digest(policy),
            "mode": policy["mode"],
            "outcome_authority": policy["outcome_authority"],
        },
        "workspace_snapshot": snapshot,
        "target": target,
        "environment": {
            "os_name": os.name,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "is_windows": os.name == "nt",
            "formal_product_environment_equivalence": "UNKNOWN",
        },
        "detector_self_test": detector_self_test,
        "active_negative_canary": active_negative_canary,
        "coverage": {
            "scope_kind": target["scope_kind"],
            "source_origin": target["source_origin"],
            "target_scope_qualified": target_scope_qualified,
            "expected_units": len(analysis_paths),
            "processed_units": len(analysis_paths),
            "failed_units": 0,
            "excluded_units": 0,
            "named_units": [relative_posix(path, workspace) for path in analysis_paths],
        },
        "findings": findings,
        "gates": gates,
        "external_error": external_error,
        "final_verdict": verdict,
        "evidence_ceiling": "WINDOWS_STRUCTURAL_AND_DECLARED_METADATA_ONLY",
        "forbidden_claims": [
            "formal_product_build_passed",
            "linux_or_image_equivalence_proven",
            "dt_or_runtime_passed",
            "no_problem",
        ],
        "limitations": [
            "No product compiler, linker, generated build expansion, DT or runtime execution is part of this MVP.",
            "A PASS gate means only that this MVP found no issue in its declared detector scope.",
            "The in-memory detector self-test is not an end-to-end active negative Canary and cannot qualify STRICT acceptance.",
        ] + (
            ["The target source set is not qualified as a complete build-system-derived target; F2 remains INCONCLUSIVE."]
            if not target_scope_qualified
            else []
        ),
    }
    fact_set["fact_set_hash"] = canonical_digest(fact_set)
    return fact_set


def render_reports(result: dict[str, Any], output: Path) -> dict[str, Path]:
    output.mkdir(parents=True, exist_ok=True)
    machine_path = output / "machine.json"
    professional_path = output / "professional.md"
    plain_path = output / "plain-language.md"
    machine_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    finding_lines = [
        f"- {item['finding_id']} [{item['code']}] {item['path']}: {item['message']}"
        for item in result["findings"]
    ] or ["- No finding inside the declared MVP detector scope."]
    gate_lines = [
        f"- {gate['gate_id']}: {gate['gate_status']} ({', '.join(gate['finding_ids']) or 'no finding'})"
        for gate in result["gates"]
    ]
    professional = [
        "# Windows Precheck Vertical MVP — Professional View",
        "",
        f"Fact set: `{result['fact_set_hash']}`",
        f"Policy: `{result['policy']['id']}` / `{result['policy']['mode']}`",
        f"Verdict: `{result['final_verdict']}`",
        f"Evidence ceiling: `{result['evidence_ceiling']}`",
        "",
        "## Gates",
        *gate_lines,
        "",
        "## Findings",
        *finding_lines,
        "",
        "## Limitations",
        *[f"- {item}" for item in result["limitations"]],
    ]
    plain = [
        "# Windows 预检纵向 MVP — 小白版",
        "",
        f"事实集：`{result['fact_set_hash']}`",
        f"本次选择：`{result['policy']['id']}`",
        f"机器结论：`{result['final_verdict']}`",
        "",
        "它实际检查了当前文件字节、基础结构、带引号头文件和声明的目标清单。",
        "它没有运行正式产品编译、链接或 DT，所以不能说“项目没问题”。",
        "",
        "## 同一批发现",
        *finding_lines,
        "",
        "## 同一批门禁",
        *gate_lines,
        "",
        "## 同一批局限",
        *[f"- {item}" for item in result["limitations"]],
    ]
    professional_path.write_text("\n".join(professional) + "\n", encoding="utf-8")
    plain_path.write_text("\n".join(plain) + "\n", encoding="utf-8")
    return {
        "machine": machine_path,
        "professional": professional_path,
        "plain_language": plain_path,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--target-manifest", required=True, type=Path)
    policy_group = parser.add_mutually_exclusive_group()
    policy_group.add_argument("--policy", choices=["quick", "balanced", "strict"])
    policy_group.add_argument("--policy-file", type=Path)
    parser.add_argument("--user-error", type=Path)
    parser.add_argument(
        "--external-error-source",
        choices=["UNVERIFIED_EXTERNAL", "ACCEPTANCE_FIXTURE"],
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        result = run_precheck(
            args.workspace,
            args.target_manifest,
            policy_id=args.policy or "balanced",
            policy_path=args.policy_file,
            user_error_path=args.user_error,
            external_error_source=args.external_error_source,
        )
        paths = render_reports(result, args.output)
    except Exception as exc:
        print(f"ERROR [MVP_FAILURE] {exc}")
        return 2
    print(json.dumps(
        {
            "fact_set_hash": result["fact_set_hash"],
            "final_verdict": result["final_verdict"],
            "gates": result["gates"],
            "reports": {key: str(path.resolve()) for key, path in paths.items()},
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 1 if any(gate["gate_status"] == "FAIL" for gate in result["gates"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
