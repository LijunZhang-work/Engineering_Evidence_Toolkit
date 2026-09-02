#!/usr/bin/env python3
"""Focused tests for the read-only toolkit doctor."""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import toolkit_doctor  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    require(toolkit_doctor.classify([{"status": "PASS"}]) == "HEALTHY", "PASS must be healthy")
    require(
        toolkit_doctor.classify([{"status": "PASS"}, {"status": "LIMITED"}]) == "LIMITED",
        "optional dependency limits must remain visible",
    )
    require(
        toolkit_doctor.classify([{"status": "LIMITED"}, {"status": "FAIL"}]) == "UNHEALTHY",
        "a failed mandatory check must dominate",
    )

    protected_paths = [
        ROOT / "TOOLKIT_MANIFEST.yaml",
        ROOT / "CURRENT_STATE.yaml",
        ROOT / "dashboard/index.html",
        ROOT / "dashboard/workset-planner.html",
        ROOT / "dashboard/run-console.html",
        ROOT / "dashboard/capability-progress.html",
    ]
    before = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in protected_paths
    }
    completed = subprocess.run(
        [sys.executable, str(ROOT / "tools/toolkit_doctor.py"), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    require(completed.returncode == 0, completed.stdout + completed.stderr)
    report = json.loads(completed.stdout)
    require(report["status"] in {"HEALTHY", "LIMITED"}, "doctor must report an honest non-failing state")
    require(report["scope"] == "TOOLKIT_SPECIFICATION_BUNDLE_ONLY", "doctor scope must be narrow")
    require(len(report["checks"]) == 10, "doctor must run the declared ten checks")
    require(report["limitations"], "doctor must retain limitations")
    after = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in protected_paths
    }
    require(before == after, "doctor must not mutate protected toolkit state")
    print("toolkit doctor tests: 10 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
