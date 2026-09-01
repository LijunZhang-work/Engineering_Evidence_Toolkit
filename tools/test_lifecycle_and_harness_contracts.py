#!/usr/bin/env python3
"""Negative checks for lifecycle truthfulness and Harness matrix parity."""

from __future__ import annotations

import copy
import shutil
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_toolkit  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_with_root(root: Path, function) -> validate_toolkit.Findings:
    original_root = validate_toolkit.ROOT
    validate_toolkit.ROOT = root
    try:
        findings = validate_toolkit.Findings()
        function(findings)
        return findings
    finally:
        validate_toolkit.ROOT = original_root


def copy_matrix_fixture(destination: Path) -> None:
    (destination / "adapters/deepseek-harness").mkdir(parents=True)
    shutil.copy2(ROOT / "TOOLKIT_MANIFEST.yaml", destination / "TOOLKIT_MANIFEST.yaml")
    shutil.copy2(
        ROOT / "adapters/HARNESS_CAPABILITY_MATRIX.yaml",
        destination / "adapters/HARNESS_CAPABILITY_MATRIX.yaml",
    )
    shutil.copy2(
        ROOT / "adapters/deepseek-harness/ADAPTER.yaml",
        destination / "adapters/deepseek-harness/ADAPTER.yaml",
    )


def write_yaml(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_matrix_baseline_and_canaries(temp_root: Path) -> None:
    copy_matrix_fixture(temp_root)
    baseline = run_with_root(temp_root, validate_toolkit.validate_harness_support_matrix)
    require(not baseline.errors, f"baseline matrix failed: {baseline.errors}")

    matrix_path = temp_root / "adapters/HARNESS_CAPABILITY_MATRIX.yaml"
    baseline_matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))

    missing = copy.deepcopy(baseline_matrix)
    missing["harnesses"][0]["capabilities"].pop()
    write_yaml(matrix_path, missing)
    findings = run_with_root(temp_root, validate_toolkit.validate_harness_support_matrix)
    require(any("HARNESS_CAPABILITY_PARITY" in item for item in findings.errors), "missing capability must fail parity")

    false_verified = copy.deepcopy(baseline_matrix)
    false_verified["harnesses"][0]["capabilities"][0]["integration_status"] = "VERIFIED"
    write_yaml(matrix_path, false_verified)
    findings = run_with_root(temp_root, validate_toolkit.validate_harness_support_matrix)
    require(any("HARNESS_FALSE_VERIFICATION" in item for item in findings.errors), "unproven VERIFIED must fail")

    drifted = copy.deepcopy(baseline_matrix)
    drifted["harnesses"][0]["capabilities"][0]["integration_status"] = "DESIGNED"
    write_yaml(matrix_path, drifted)
    findings = run_with_root(temp_root, validate_toolkit.validate_harness_support_matrix)
    require(any("HARNESS_ADAPTER_MATRIX_DRIFT" in item for item in findings.errors), "adapter/matrix drift must fail")


def test_lifecycle_false_implementation(temp_root: Path) -> None:
    (temp_root / "lifecycle").mkdir(parents=True)
    lifecycle_path = temp_root / "lifecycle/TOOLKIT_LIFECYCLE.yaml"
    lifecycle = yaml.safe_load((ROOT / "lifecycle/TOOLKIT_LIFECYCLE.yaml").read_text(encoding="utf-8"))
    write_yaml(lifecycle_path, lifecycle)
    baseline = run_with_root(temp_root, validate_toolkit.validate_lifecycle_manifest)
    require(not baseline.errors, f"baseline lifecycle failed: {baseline.errors}")

    for operation in lifecycle["operations"]:
        if operation["id"] == "apply":
            operation["implementation_status"] = "IMPLEMENTED"
    write_yaml(lifecycle_path, lifecycle)
    findings = run_with_root(temp_root, validate_toolkit.validate_lifecycle_manifest)
    require(
        any("LIFECYCLE_FALSE_IMPLEMENTATION" in item for item in findings.errors),
        "unimplemented apply must not be marked implemented",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
        base = Path(temporary)
        test_matrix_baseline_and_canaries(base / "matrix")
        test_lifecycle_false_implementation(base / "lifecycle")
    print("lifecycle and harness contract tests: 5 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
