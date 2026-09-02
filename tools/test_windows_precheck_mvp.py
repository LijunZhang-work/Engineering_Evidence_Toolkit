from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import yaml

try:
    from tools.windows_precheck_mvp import ROOT, load_policy, render_reports, run_precheck
except ModuleNotFoundError:  # unittest discover -s tools
    from windows_precheck_mvp import ROOT, load_policy, render_reports, run_precheck


FIXTURES = ROOT / "acceptance/fixtures/windows-mvp"


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def finding_codes(result: dict) -> set[str]:
    return {finding["code"] for finding in result["findings"]}


def gate_status(result: dict, gate_id: str) -> str:
    return next(gate["gate_status"] for gate in result["gates"] if gate["gate_id"] == gate_id)


class WindowsPrecheckMvpTests(unittest.TestCase):
    def run_case(self, name: str, *, policy: str = "balanced", user_error: bool = False) -> dict:
        workspace = FIXTURES / name
        before = tree_hash(workspace)
        result = run_precheck(
            workspace,
            workspace / "target.yaml",
            policy_id=policy,
            user_error_path=workspace / "user-error.txt" if user_error else None,
            external_error_source="ACCEPTANCE_FIXTURE" if user_error else None,
        )
        self.assertEqual(before, tree_hash(workspace), "MVP must not mutate its source fixture")
        return result

    def run_temporary_source(self, source: str, manifest: str | None = None) -> dict:
        with tempfile.TemporaryDirectory(prefix="eet-windows-mvp-") as temporary:
            workspace = Path(temporary)
            (workspace / "source.cpp").write_text(source, encoding="utf-8")
            (workspace / "target.yaml").write_text(
                manifest
                or (
                    'schema_version: "1.0.0"\n'
                    "target_id: temporary-bounded-target\n"
                    "scope_kind: BOUNDED_FILE_SET\n"
                    "source_origin: MANUAL\n"
                    "source_origin_ref: temporary-test\n"
                    "sources: [source.cpp]\n"
                    "expected_sources: [source.cpp]\n"
                    "include_dirs: [.]\n"
                ),
                encoding="utf-8",
            )
            return run_precheck(workspace, workspace / "target.yaml")

    def test_clean_balanced_is_bounded_no_verdict(self) -> None:
        result = self.run_case("clean")
        self.assertEqual(finding_codes(result), set())
        self.assertEqual(result["detector_self_test"]["status"], "PASS")
        self.assertEqual(result["active_negative_canary"]["status"], "NOT_IMPLEMENTED")
        self.assertEqual(gate_status(result, "F0_CHECK_EFFECTIVENESS"), "INCONCLUSIVE")
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "PASS")
        self.assertEqual(gate_status(result, "F2_BUILD_TARGET_AND_DEPENDENCY"), "PASS")
        self.assertEqual(result["final_verdict"], "NO_VERDICT")
        self.assertEqual(result["evidence_ceiling"], "WINDOWS_STRUCTURAL_AND_DECLARED_METADATA_ONLY")

    def test_missing_right_parenthesis_fails_structure_gate(self) -> None:
        result = self.run_case("missing-paren")
        self.assertTrue(
            {"UNCLOSED_DELIMITER", "MISMATCHED_CLOSING_DELIMITER"} & finding_codes(result)
        )
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "FAIL")

    def test_truncated_tail_fails_structure_gate(self) -> None:
        result = self.run_case("truncated-tail")
        self.assertIn("UNCLOSED_DELIMITER", finding_codes(result))
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "FAIL")

    def test_missing_include_fails_dependency_gate(self) -> None:
        result = self.run_case("missing-include")
        self.assertIn("MISSING_QUOTED_INCLUDE", finding_codes(result))
        self.assertEqual(gate_status(result, "F2_BUILD_TARGET_AND_DEPENDENCY"), "FAIL")

    def test_expected_source_not_in_target_fails_dependency_gate(self) -> None:
        result = self.run_case("not-in-target")
        self.assertIn("SOURCE_NOT_IN_TARGET", finding_codes(result))
        self.assertEqual(gate_status(result, "F2_BUILD_TARGET_AND_DEPENDENCY"), "FAIL")

    def test_external_error_overrides_local_green_until_reconciled(self) -> None:
        result = self.run_case("external-error-clean", user_error=True)
        self.assertIn("USER_ERROR_UNRESOLVED", finding_codes(result))
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "PASS")
        self.assertEqual(
            gate_status(result, "F5_EXTERNAL_EVIDENCE_RECONCILIATION"),
            "INCONCLUSIVE",
        )
        self.assertEqual(result["final_verdict"], "NO_VERDICT")
        self.assertEqual(result["external_error"]["status"], "UNRESOLVED")
        self.assertEqual(result["external_error"]["source_class"], "ACCEPTANCE_FIXTURE")

    def test_external_error_requires_explicit_provenance(self) -> None:
        workspace = FIXTURES / "external-error-clean"
        with self.assertRaisesRegex(ValueError, "supplied together"):
            run_precheck(
                workspace,
                workspace / "target.yaml",
                user_error_path=workspace / "user-error.txt",
            )

    def test_unverified_external_error_remains_unresolved(self) -> None:
        workspace = FIXTURES / "external-error-clean"
        result = run_precheck(
            workspace,
            workspace / "target.yaml",
            user_error_path=workspace / "user-error.txt",
            external_error_source="UNVERIFIED_EXTERNAL",
        )
        self.assertEqual(result["external_error"]["source_class"], "UNVERIFIED_EXTERNAL")
        self.assertEqual(result["external_error"]["status"], "UNRESOLVED")
        self.assertEqual(
            gate_status(result, "F5_EXTERNAL_EVIDENCE_RECONCILIATION"),
            "INCONCLUSIVE",
        )

    def test_user_provided_source_class_is_rejected(self) -> None:
        workspace = FIXTURES / "external-error-clean"
        with self.assertRaisesRegex(ValueError, "unsupported external error source"):
            run_precheck(
                workspace,
                workspace / "target.yaml",
                user_error_path=workspace / "user-error.txt",
                external_error_source="USER_PROVIDED",
            )

    def test_policy_ceiling_is_enforced(self) -> None:
        quick = self.run_case("clean", policy="quick")
        strict = self.run_case("clean", policy="strict")
        strict_broken = self.run_case("missing-paren", policy="strict")
        self.assertEqual(quick["detector_self_test"]["status"], "NOT_REQUIRED")
        self.assertEqual(quick["active_negative_canary"]["status"], "NOT_REQUIRED")
        self.assertEqual(quick["final_verdict"], "NO_VERDICT")
        self.assertEqual(strict["final_verdict"], "INCOMPLETE")
        self.assertEqual(gate_status(strict, "F0_CHECK_EFFECTIVENESS"), "INCONCLUSIVE")
        self.assertEqual(strict_broken["final_verdict"], "REJECT")

    def test_custom_policy_file_executes_independent_axes(self) -> None:
        workspace = FIXTURES / "clean"
        policy_path = ROOT / "acceptance/fixtures/policies/custom-strict-no-fallback.yaml"
        result = run_precheck(
            workspace,
            workspace / "target.yaml",
            policy_path=policy_path,
        )
        self.assertEqual(result["policy"]["preset"], "CUSTOM")
        self.assertEqual(result["policy"]["outcome_authority"], "FINAL_VERDICT")
        self.assertEqual(result["final_verdict"], "INCOMPLETE")

    def test_custom_policy_cannot_store_an_overstated_ceiling(self) -> None:
        source = ROOT / "acceptance/fixtures/policies/custom-strict-no-fallback.yaml"
        policy = yaml.safe_load(source.read_text(encoding="utf-8"))
        policy["evidence_requirements"]["coverage_requirement"] = "BEST_EFFORT"
        with tempfile.TemporaryDirectory(prefix="eet-custom-policy-") as temporary:
            path = Path(temporary) / "overclaim.yaml"
            path.write_text(yaml.safe_dump(policy, sort_keys=False, allow_unicode=True), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "overclaims authority"):
                load_policy("custom", path)

    def test_empty_target_is_inconclusive_not_green(self) -> None:
        result = self.run_case("empty-target")
        self.assertIn("EMPTY_ANALYSIS_SCOPE", finding_codes(result))
        self.assertEqual(result["coverage"]["expected_units"], 0)
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "INCONCLUSIVE")
        self.assertEqual(gate_status(result, "F2_BUILD_TARGET_AND_DEPENDENCY"), "INCONCLUSIVE")

    def test_bounded_manual_scope_cannot_pass_target_gate(self) -> None:
        result = self.run_case("bounded-scope")
        self.assertIn("TARGET_SCOPE_UNQUALIFIED", finding_codes(result))
        self.assertEqual(result["coverage"]["scope_kind"], "BOUNDED_FILE_SET")
        self.assertFalse(result["coverage"]["target_scope_qualified"])
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "PASS")
        self.assertEqual(gate_status(result, "F2_BUILD_TARGET_AND_DEPENDENCY"), "INCONCLUSIVE")

    def test_unrelated_vendor_file_is_outside_target_scope(self) -> None:
        result = self.run_case("unrelated-vendor")
        self.assertNotIn("UNCLOSED_DELIMITER", finding_codes(result))
        self.assertEqual(result["coverage"]["named_units"], ["source.cpp"])
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "PASS")

    def test_quick_snapshots_only_target_reachable_inputs(self) -> None:
        quick = self.run_case("unrelated-vendor", policy="quick")
        balanced = self.run_case("unrelated-vendor", policy="balanced")
        quick_files = {item["path"] for item in quick["workspace_snapshot"]["files"]}
        balanced_files = {item["path"] for item in balanced["workspace_snapshot"]["files"]}
        self.assertEqual(quick["workspace_snapshot"]["snapshot_scope"], "TARGET_REACHABLE_INPUTS")
        self.assertEqual(quick_files, {"source.cpp"})
        self.assertEqual(balanced["workspace_snapshot"]["snapshot_scope"], "FULL_WORKSPACE")
        self.assertIn("vendor/bad.cpp", balanced_files)

    def test_reachable_header_is_scanned(self) -> None:
        result = self.run_case("reachable-header")
        self.assertIn("UNCLOSED_DELIMITER", finding_codes(result))
        self.assertEqual(set(result["coverage"]["named_units"]), {"source.cpp", "dep.h"})
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "FAIL")

    def test_cpp_raw_string_delimiters_do_not_trigger_false_positive(self) -> None:
        result = self.run_case("raw-string")
        self.assertFalse({"UNTERMINATED_LITERAL", "UNTERMINATED_RAW_STRING", "MISMATCHED_CLOSING_DELIMITER"} & finding_codes(result))
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "PASS")

    def test_mutually_exclusive_preprocessor_branches_are_scanned_as_variants(self) -> None:
        result = self.run_case("preprocessor-alternatives")
        self.assertNotIn("UNCLOSED_DELIMITER", finding_codes(result))
        self.assertNotIn("MISMATCHED_CLOSING_DELIMITER", finding_codes(result))
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "PASS")

    def test_repeated_condition_approximation_is_inconclusive_not_fail(self) -> None:
        result = self.run_temporary_source(
            "#if A\n"
            "{\n"
            "#else\n"
            "[\n"
            "#endif\n"
            "#if A\n"
            "}\n"
            "#else\n"
            "]\n"
            "#endif\n"
        )
        possible = [
            finding
            for finding in result["findings"]
            if finding.get("certainty") == "POSSIBLE"
        ]
        self.assertTrue(possible)
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "INCONCLUSIVE")

    def test_if_zero_inactive_structure_is_inconclusive_not_fail(self) -> None:
        result = self.run_temporary_source("#if 0\n(\n#endif\nint ok;\n")
        self.assertTrue(
            any(finding.get("certainty") == "POSSIBLE" for finding in result["findings"])
        )
        self.assertEqual(gate_status(result, "F1_STRUCTURAL_CHANGE_SAFETY"), "INCONCLUSIVE")

    def test_unparsed_build_artifact_cannot_qualify_target_scope(self) -> None:
        source = "int valid() { return 0; }\n"
        source_content_id = "sha256:" + hashlib.sha256(source.encode("utf-8")).hexdigest()
        for source_origin in ("CMAKE_FILE_API", "BUILD_SYSTEM_EXPORT"):
            with self.subTest(source_origin=source_origin):
                result = self.run_temporary_source(
                    source,
                    (
                        'schema_version: "1.0.0"\n'
                        "target_id: forged-full-target\n"
                        "scope_kind: FULL_TARGET\n"
                        f"source_origin: {source_origin}\n"
                        "source_origin_ref: source.cpp\n"
                        f"source_origin_content_id: {source_content_id}\n"
                        "sources: [source.cpp]\n"
                        "expected_sources: [source.cpp]\n"
                        "include_dirs: [.]\n"
                    ),
                )
                self.assertFalse(result["coverage"]["target_scope_qualified"])
                self.assertIn("TARGET_SCOPE_UNQUALIFIED", finding_codes(result))
                self.assertEqual(
                    gate_status(result, "F2_BUILD_TARGET_AND_DEPENDENCY"),
                    "INCONCLUSIVE",
                )

    def test_source_outside_workspace_is_rejected_before_analysis(self) -> None:
        workspace = FIXTURES / "outside-source"
        with self.assertRaisesRegex(ValueError, "invalid target manifest|escapes workspace"):
            run_precheck(workspace, workspace / "target.yaml")

    def test_include_directory_outside_workspace_is_rejected(self) -> None:
        workspace = FIXTURES / "outside-include-dir"
        with self.assertRaisesRegex(ValueError, "escapes workspace"):
            run_precheck(workspace, workspace / "target.yaml")

    def test_all_report_views_share_fact_hash_findings_and_gates(self) -> None:
        result = self.run_case("external-error-clean", user_error=True)
        with tempfile.TemporaryDirectory() as temporary:
            paths = render_reports(result, Path(temporary))
            machine = json.loads(paths["machine"].read_text(encoding="utf-8"))
            professional = paths["professional"].read_text(encoding="utf-8")
            plain = paths["plain_language"].read_text(encoding="utf-8")
        self.assertEqual(machine["fact_set_hash"], result["fact_set_hash"])
        for view in (professional, plain):
            self.assertIn(result["fact_set_hash"], view)
            for finding in result["findings"]:
                self.assertIn(finding["finding_id"], view)
            for gate in result["gates"]:
                self.assertIn(gate["gate_id"], view)
            for limitation in result["limitations"]:
                self.assertIn(limitation, view)


if __name__ == "__main__":
    unittest.main(verbosity=2)
