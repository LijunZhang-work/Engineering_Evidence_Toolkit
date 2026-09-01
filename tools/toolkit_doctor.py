#!/usr/bin/env python3
"""Read-only health check for the Engineering Evidence Toolkit checkout.

Doctor health is intentionally scoped to the toolkit specification bundle. It
does not execute a Capability or inspect business source.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run_script(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    completed = subprocess.run(
        [sys.executable, str(path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "id": relative_path,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def dependency_status(module_name: str, required: bool) -> dict[str, Any]:
    available = importlib.util.find_spec(module_name) is not None
    return {
        "id": f"python-module:{module_name}",
        "status": "PASS" if available else "FAIL" if required else "LIMITED",
        "required": required,
        "available": available,
    }


def classify(checks: list[dict[str, Any]]) -> str:
    if any(check.get("status") == "FAIL" for check in checks):
        return "UNHEALTHY"
    if any(check.get("status") == "LIMITED" for check in checks):
        return "LIMITED"
    return "HEALTHY"


def build_report() -> dict[str, Any]:
    checks = [
        dependency_status("yaml", required=True),
        dependency_status("jsonschema", required=False),
        run_script("tools/test_capability_dashboard.py"),
        run_script("tools/test_lifecycle_and_harness_contracts.py"),
        run_script("tools/validate_toolkit.py"),
    ]
    status = classify(checks)
    return {
        "schema_version": 1,
        "tool": "engineering-evidence-toolkit-doctor",
        "scope": "TOOLKIT_SPECIFICATION_BUNDLE_ONLY",
        "status": status,
        "checks": checks,
        "limitations": [
            "No Capability implementation or business source was executed.",
            "Doctor success does not prove Windows precheck, compilation, DT, provider or review correctness.",
        ],
    }


def render_text(report: dict[str, Any]) -> str:
    lines = [
        "Engineering Evidence Toolkit doctor",
        f"scope: {report['scope']}",
        f"status: {report['status']}",
    ]
    for check in report["checks"]:
        lines.append(f"- {check['status']}: {check['id']}")
    lines.append("No Capability or business-code check was executed.")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args()
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_text(report))
    return 1 if report["status"] == "UNHEALTHY" else 0


if __name__ == "__main__":
    raise SystemExit(main())
