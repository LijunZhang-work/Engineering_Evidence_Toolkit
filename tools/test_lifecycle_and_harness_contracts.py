#!/usr/bin/env python3
"""Negative checks for lifecycle truthfulness and Harness matrix parity."""

from __future__ import annotations

import copy
import shutil
import sys
import tempfile
import unittest
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
    (destination / ".dsh/skills/engineering-evidence-toolkit").mkdir(parents=True)
    (destination / "acceptance/harness-validation").mkdir(parents=True)
    shutil.copy2(ROOT / "TOOLKIT_MANIFEST.yaml", destination / "TOOLKIT_MANIFEST.yaml")
    shutil.copy2(
        ROOT / "adapters/HARNESS_CAPABILITY_MATRIX.yaml",
        destination / "adapters/HARNESS_CAPABILITY_MATRIX.yaml",
    )
    shutil.copy2(
        ROOT / "adapters/deepseek-harness/ADAPTER.yaml",
        destination / "adapters/deepseek-harness/ADAPTER.yaml",
    )
    shutil.copy2(
        ROOT / ".dsh/skills/engineering-evidence-toolkit/SKILL.md",
        destination / ".dsh/skills/engineering-evidence-toolkit/SKILL.md",
    )
    for name in ("GLM_COMPATIBILITY_OBSERVATION.yaml", "glm-final-observation.png"):
        shutil.copy2(
            ROOT / "acceptance/harness-validation" / name,
            destination / "acceptance/harness-validation" / name,
        )


def write_yaml(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


class LifecycleAndHarnessContractTests(unittest.TestCase):
    def matrix_fixture(self, temporary: str) -> tuple[Path, Path, dict]:
        root = Path(temporary) / "matrix"
        copy_matrix_fixture(root)
        matrix_path = root / "adapters/HARNESS_CAPABILITY_MATRIX.yaml"
        matrix = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
        return root, matrix_path, matrix

    def test_matrix_baseline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, _, _ = self.matrix_fixture(temporary)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertFalse(findings.errors, f"baseline matrix failed: {findings.errors}")

    def test_matrix_missing_capability(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, matrix_path, matrix = self.matrix_fixture(temporary)
            matrix["harnesses"][0]["capabilities"].pop()
            write_yaml(matrix_path, matrix)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_CAPABILITY_PARITY" in item for item in findings.errors))

    def test_matrix_false_verified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, matrix_path, matrix = self.matrix_fixture(temporary)
            matrix["harnesses"][0]["capabilities"][0]["integration_status"] = "VERIFIED"
            write_yaml(matrix_path, matrix)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_FALSE_VERIFICATION" in item for item in findings.errors))

    def test_matrix_verified_missing_evidence_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, matrix_path, matrix = self.matrix_fixture(temporary)
            entry = next(
                item
                for item in matrix["harnesses"][0]["capabilities"]
                if item["capability_id"] == "code-fact"
            )
            entry["integration_status"] = "VERIFIED"
            entry["validation_status"] = "PASSED"
            entry["evidence_refs"] = ["missing/harness-receipt.json"]
            write_yaml(matrix_path, matrix)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_EVIDENCE_REF" in item for item in findings.errors))

    def test_matrix_partial_runtime_requires_content_addressed_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, matrix_path, matrix = self.matrix_fixture(temporary)
            matrix["harnesses"][0].pop("runtime_evidence")
            write_yaml(matrix_path, matrix)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_RUNTIME_EVIDENCE" in item for item in findings.errors))

    def test_matrix_runtime_evidence_digest_cannot_be_forged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, matrix_path, matrix = self.matrix_fixture(temporary)
            matrix["harnesses"][0]["runtime_evidence"][0]["content_id"] = "sha256:" + "0" * 64
            write_yaml(matrix_path, matrix)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_RUNTIME_EVIDENCE" in item for item in findings.errors))

    def test_matrix_adapter_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, matrix_path, matrix = self.matrix_fixture(temporary)
            matrix["harnesses"][0]["capabilities"][0]["integration_status"] = "DESIGNED"
            write_yaml(matrix_path, matrix)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_ADAPTER_MATRIX_DRIFT" in item for item in findings.errors))

    def test_matrix_missing_project_skill(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, _, _ = self.matrix_fixture(temporary)
            (root / ".dsh/skills/engineering-evidence-toolkit/SKILL.md").unlink()
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_SKILL_ENTRYPOINT" in item for item in findings.errors))

    def test_glm_boundary_is_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, _, _ = self.matrix_fixture(temporary)
            adapter_path = root / "adapters/deepseek-harness/ADAPTER.yaml"
            adapter = yaml.safe_load(adapter_path.read_text(encoding="utf-8"))
            adapter.pop("glm_compatibility_observer")
            write_yaml(adapter_path, adapter)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_GLM_BOUNDARY" in item for item in findings.errors))

    def test_glm_boundary_cannot_gain_authority_or_run_early(self) -> None:
        mutations = {
            "role": "PRIMARY_REVIEWER",
            "must_run_after": "NONE",
            "claim_authority": "ADVISORY",
            "gate_authority": "ADVISORY",
            "qualification_authority": "ADVISORY",
            "lifecycle_promotion_authority": "ADVISORY",
        }
        for field, value in mutations.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
                root, _, _ = self.matrix_fixture(temporary)
                adapter_path = root / "adapters/deepseek-harness/ADAPTER.yaml"
                adapter = yaml.safe_load(adapter_path.read_text(encoding="utf-8"))
                adapter["glm_compatibility_observer"][field] = value
                write_yaml(adapter_path, adapter)
                findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
                self.assertTrue(any("HARNESS_GLM_BOUNDARY" in item for item in findings.errors))

    def test_skill_glm_boundary_cannot_be_rewritten_as_primary_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, _, _ = self.matrix_fixture(temporary)
            skill_path = root / ".dsh/skills/engineering-evidence-toolkit/SKILL.md"
            skill_text = skill_path.read_text(encoding="utf-8")
            skill_path.write_text(
                skill_text.replace(
                    "EET_GLM_REVIEW_AUTHORITY=NONE",
                    "EET_GLM_REVIEW_AUTHORITY=PRIMARY_REVIEWER",
                ),
                encoding="utf-8",
            )
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_GLM_SKILL_BOUNDARY" in item for item in findings.errors))

    def test_skill_frontmatter_requires_official_optional_field_types(self) -> None:
        replacements = {
            "whenToUse": (
                "whenToUse: Use for repository evidence collection, safe-edit verification, Windows C/C++ precheck, RunBundle validation, or Toolkit/Harness compatibility checks in this project.",
                'whenToUse: ""',
            ),
            "disable-model-invocation": (
                "disable-model-invocation: false",
                'disable-model-invocation: "false"',
            ),
            "user-invocable": ("user-invocable: true", "user-invocable: 1"),
        }
        for field, (original, replacement) in replacements.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
                root, _, _ = self.matrix_fixture(temporary)
                skill_path = root / ".dsh/skills/engineering-evidence-toolkit/SKILL.md"
                skill_text = skill_path.read_text(encoding="utf-8")
                self.assertIn(original, skill_text)
                skill_path.write_text(skill_text.replace(original, replacement), encoding="utf-8")
                findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
                self.assertTrue(any("HARNESS_SKILL_FRONTMATTER" in item for item in findings.errors))

    def test_skill_directory_must_equal_frontmatter_name(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root, _, _ = self.matrix_fixture(temporary)
            adapter_path = root / "adapters/deepseek-harness/ADAPTER.yaml"
            adapter = yaml.safe_load(adapter_path.read_text(encoding="utf-8"))
            old_skill = root / ".dsh/skills/engineering-evidence-toolkit/SKILL.md"
            new_skill = root / ".dsh/skills/wrong-directory/SKILL.md"
            new_skill.parent.mkdir(parents=True)
            shutil.copy2(old_skill, new_skill)
            adapter["project_skill_entrypoint"]["path"] = ".dsh/skills/wrong-directory/SKILL.md"
            write_yaml(adapter_path, adapter)
            findings = run_with_root(root, validate_toolkit.validate_harness_support_matrix)
            self.assertTrue(any("HARNESS_SKILL_FRONTMATTER" in item for item in findings.errors))

    def test_lifecycle_false_implementation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-contract-tests-") as temporary:
            root = Path(temporary) / "lifecycle-root"
            (root / "lifecycle").mkdir(parents=True)
            (root / "tools").mkdir(parents=True)
            lifecycle_path = root / "lifecycle/TOOLKIT_LIFECYCLE.yaml"
            shutil.copy2(ROOT / "tools/toolkit_doctor.py", root / "tools/toolkit_doctor.py")
            shutil.copy2(ROOT / "tools/test_toolkit_doctor.py", root / "tools/test_toolkit_doctor.py")
            lifecycle = yaml.safe_load((ROOT / "lifecycle/TOOLKIT_LIFECYCLE.yaml").read_text(encoding="utf-8"))
            write_yaml(lifecycle_path, lifecycle)
            baseline = run_with_root(root, validate_toolkit.validate_lifecycle_manifest)
            self.assertFalse(baseline.errors, f"baseline lifecycle failed: {baseline.errors}")
            for operation in lifecycle["operations"]:
                if operation["id"] == "apply":
                    operation["implementation_status"] = "IMPLEMENTED"
            write_yaml(lifecycle_path, lifecycle)
            findings = run_with_root(root, validate_toolkit.validate_lifecycle_manifest)
            self.assertTrue(any("LIFECYCLE_PROMOTION_WITHOUT_EVIDENCE" in item for item in findings.errors))


if __name__ == "__main__":
    unittest.main(verbosity=2)
