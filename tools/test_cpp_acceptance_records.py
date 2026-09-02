from __future__ import annotations

import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

try:
    from tools.validate_toolkit import (
        _cpp_environment_content_id,
        cpp_candidate_selection_issues,
        cpp_real_validation_issues,
        repository_absolute_path_issues,
    )
except ModuleNotFoundError:
    from validate_toolkit import (
        _cpp_environment_content_id,
        cpp_candidate_selection_issues,
        cpp_real_validation_issues,
        repository_absolute_path_issues,
    )


ROOT = Path(__file__).resolve().parents[1]


def load(relative: str) -> dict:
    with (ROOT / relative).open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    assert isinstance(value, dict)
    return value


class CppAcceptanceRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.selection = load("acceptance/cpp-target-selection/CANDIDATE_SELECTION.yaml")
        self.record = load("acceptance/cpp-target-selection/REAL_VALIDATION.yaml")

    def test_current_records_are_semantically_consistent(self) -> None:
        self.assertEqual(cpp_candidate_selection_issues(self.selection), [])
        self.assertEqual(cpp_real_validation_issues(self.record, self.selection), [])

    def test_duplicate_candidate_id_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.selection)
        mutated["candidates"][1]["candidate_id"] = mutated["candidates"][0]["candidate_id"]
        self.assertTrue(any("duplicate candidate" in issue for issue in cpp_candidate_selection_issues(mutated)))

    def test_provisional_selection_cannot_claim_pass(self) -> None:
        mutated = copy.deepcopy(self.selection)
        mutated["selection_gate_status"] = "PASS"
        self.assertTrue(any("PROVISIONAL" in issue for issue in cpp_candidate_selection_issues(mutated)))

    def test_selected_candidate_must_meet_declared_medium_bounds(self) -> None:
        mutated = copy.deepcopy(self.selection)
        mutated["selection_criteria"]["product_physical_loc"]["maximum"] = 50000
        self.assertTrue(any("outside" in issue for issue in cpp_candidate_selection_issues(mutated)))

    def test_final_requires_all_build_measurements_and_tests(self) -> None:
        mutated = copy.deepcopy(self.selection)
        mutated["selection_status"] = "FINAL"
        mutated["selection_gate_status"] = "PASS"
        mutated["unresolved_requirements"] = []
        issues = cpp_candidate_selection_issues(mutated)
        self.assertTrue(any("measured build timing" in issue for issue in issues))
        self.assertTrue(any("PASSED tests" in issue for issue in issues))

    def test_fully_self_reported_final_without_receipts_is_rejected(self) -> None:
        mutated = copy.deepcopy(self.selection)
        mutated["selection_status"] = "FINAL"
        mutated["selection_gate_status"] = "PASS"
        mutated["unresolved_requirements"] = []
        mutated["environment"].update({
            "msvc": "AVAILABLE",
            "cmake": "AVAILABLE",
            "ninja": "AVAILABLE",
            "build_timing_status": "MEASURED",
        })
        for candidate in mutated["candidates"]:
            candidate["disposition"] = "SELECTED" if candidate["candidate_id"] == mutated["selected_candidate_id"] else "ALTERNATE"
            candidate["build_measurement"].update({
                "status": "MEASURED",
                "generator": "Ninja",
                "configuration": "Release",
                "clean_build_ms": 1,
                "incremental_build_ms": 1,
                "test_status": "PASSED",
            })
        issues = cpp_candidate_selection_issues(mutated)
        self.assertTrue(any("receipt" in issue for issue in issues), issues)

    def test_unrelated_file_cannot_be_reused_for_every_final_receipt(self) -> None:
        mutated = copy.deepcopy(self.selection)
        mutated["selection_status"] = "FINAL"
        mutated["selection_gate_status"] = "PASS"
        mutated["unresolved_requirements"] = []
        unrelated = ROOT / "tools/validate_toolkit.py"
        fake_ref = {
            "path": "tools/validate_toolkit.py",
            "content_id": "sha256:" + hashlib.sha256(unrelated.read_bytes()).hexdigest(),
        }
        mutated["selection_receipt"] = copy.deepcopy(fake_ref)
        mutated["environment"].update({
            "msvc": "AVAILABLE", "cmake": "AVAILABLE", "ninja": "AVAILABLE",
            "msvc_version": "19.40", "cmake_version": "3.30", "ninja_version": "1.12",
            "build_timing_status": "MEASURED", "discovery_receipt": copy.deepcopy(fake_ref),
        })
        for candidate in mutated["candidates"]:
            candidate["disposition"] = "SELECTED" if candidate["candidate_id"] == mutated["selected_candidate_id"] else "ALTERNATE"
            candidate["build_measurement"].update({
                "status": "MEASURED", "generator": "Ninja", "configuration": "Release",
                "clean_build_ms": 1, "incremental_build_ms": 1, "test_status": "PASSED",
                "receipt": copy.deepcopy(fake_ref),
            })
        issues = cpp_candidate_selection_issues(mutated)
        self.assertTrue(any("typed C++ acceptance receipt" in issue for issue in issues), issues)

    def test_schema_valid_self_reported_receipt_requires_authority_pin(self) -> None:
        mutated = copy.deepcopy(self.selection)
        mutated["selection_status"] = "FINAL"
        mutated["selection_gate_status"] = "PASS"
        mutated["unresolved_requirements"] = []
        mutated["environment"].update({
            "environment_scope": "LOCAL_DEVELOPMENT",
            "msvc": "AVAILABLE", "cmake": "AVAILABLE", "ninja": "AVAILABLE",
            "msvc_version": "19.40", "cmake_version": "3.30", "ninja_version": "1.12",
            "build_timing_status": "MEASURED",
        })
        mutated["environment"]["context_content_id"] = _cpp_environment_content_id(mutated["environment"])
        receipt_path = ROOT / "acceptance/fixtures/cpp-unpinned-selection-receipt.json"
        mutated["selection_receipt"] = {
            "path": "acceptance/fixtures/cpp-unpinned-selection-receipt.json",
            "content_id": "sha256:" + hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        }
        issues = cpp_candidate_selection_issues(mutated)
        self.assertTrue(any("not pinned by an active scoped C++ acceptance Authority" in issue for issue in issues), issues)

    def test_environment_context_digest_is_recomputed(self) -> None:
        mutated = copy.deepcopy(self.selection)
        mutated["environment"]["context_content_id"] = "sha256:" + "0" * 64
        self.assertTrue(any("environment context_content_id is stale or forged" in issue for issue in cpp_candidate_selection_issues(mutated)))

    def test_real_validation_target_must_match_pinned_selection(self) -> None:
        mutated = copy.deepcopy(self.record)
        mutated["target"]["commit"] = "0" * 40
        self.assertTrue(any("target commit" in issue for issue in cpp_real_validation_issues(mutated, self.selection)))

    def test_source_not_in_target_cannot_be_promoted_to_pass_without_build(self) -> None:
        mutated = copy.deepcopy(self.record)
        scenario = next(item for item in mutated["scenarios"] if item["scenario_id"] == "04-source-not-in-target")
        scenario["after"]["gates"]["F2_BUILD_TARGET_AND_DEPENDENCY"] = "PASS"
        self.assertTrue(any("must be INCONCLUSIVE" in issue for issue in cpp_real_validation_issues(mutated, self.selection)))

    def test_acceptance_fixture_cannot_impersonate_user_evidence(self) -> None:
        mutated = copy.deepcopy(self.record)
        scenario = next(item for item in mutated["scenarios"] if item["scenario_id"] == "05-external-compiler-error")
        scenario["evidence_source"] = "ISOLATED_GIT_WORKTREE"
        self.assertTrue(any("evidence source" in issue for issue in cpp_real_validation_issues(mutated, self.selection)))

    def test_partial_static_record_cannot_grant_qualification(self) -> None:
        mutated = copy.deepcopy(self.record)
        mutated["qualification_effect"] = "QUALIFIED"
        self.assertTrue(any("cannot grant qualification" in issue for issue in cpp_real_validation_issues(mutated, self.selection)))

    def test_top_level_formal_pass_cannot_conflict_with_blocked_scenarios(self) -> None:
        mutated = copy.deepcopy(self.record)
        mutated["environment"].update({
            "msvc": "AVAILABLE",
            "cmake": "AVAILABLE",
            "ninja": "AVAILABLE",
            "formal_build_status": "PASSED",
        })
        issues = cpp_real_validation_issues(mutated, self.selection)
        self.assertTrue(any("partial static record cannot claim" in issue for issue in issues), issues)

    def test_external_artifact_hash_is_opened_not_trusted(self) -> None:
        mutated = copy.deepcopy(self.record)
        mutated["scenarios"][0]["before"]["artifact_files"]["machine"]["content_id"] = "sha256:" + "f" * 64
        reference = mutated["scenarios"][0]["before"]["artifact_files"]["machine"]
        with tempfile.TemporaryDirectory(prefix="eet-external-evidence-") as temporary:
            artifact_path = Path(temporary) / reference["path"]
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(b"tampered artifact")
            issues = cpp_real_validation_issues(
                mutated,
                self.selection,
                external_evidence_root=Path(temporary),
            )
        self.assertTrue(any("stale or forged" in issue for issue in issues), issues)

    def test_static_blind_spot_cannot_claim_case_coverage(self) -> None:
        mutated = copy.deepcopy(self.record)
        scenario = next(item for item in mutated["scenarios"] if item["scenario_id"] == "03-missing-include")
        scenario["case_coverage"] = "SATISFIED_WITHIN_STATIC_MVP"
        scenario["case_result"] = "PASS_STATIC_ONLY"
        issues = cpp_real_validation_issues(mutated, self.selection)
        self.assertTrue(any("overstates" in issue for issue in issues), issues)

    def test_strict_external_reverification_requires_runtime_binding(self) -> None:
        issues = cpp_real_validation_issues(
            self.record,
            self.selection,
            require_external_evidence=True,
        )
        self.assertTrue(any("root is required" in issue for issue in issues), issues)

    def test_unavailable_runtime_evidence_binding_fails(self) -> None:
        issues = cpp_real_validation_issues(
            self.record,
            self.selection,
            external_evidence_root=ROOT / "acceptance/fixtures/does-not-exist",
        )
        self.assertTrue(any("root is unavailable" in issue for issue in issues), issues)

    def test_record_cannot_embed_machine_specific_root(self) -> None:
        mutated = copy.deepcopy(self.record)
        mutated["evidence_storage"]["root"] = "machine-specific-root"
        issues = cpp_real_validation_issues(mutated, self.selection)
        self.assertTrue(any("must not embed" in issue for issue in issues), issues)

    def test_repository_portability_guard_rejects_absolute_machine_paths(self) -> None:
        self.assertEqual(repository_absolute_path_issues(ROOT), [])
        with tempfile.TemporaryDirectory(prefix="eet-portability-") as temporary:
            sample = Path(temporary) / "record.yaml"
            sample.write_text("root: " + "D:" + "/machine-specific/evidence\n", encoding="utf-8")
            issues = repository_absolute_path_issues(Path(temporary))
        self.assertTrue(any("machine-specific absolute path" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main(verbosity=2)
