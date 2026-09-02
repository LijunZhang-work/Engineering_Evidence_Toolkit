from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable

import yaml

try:
    from tools.validate_run_bundle import ROOT, load_document, validate_run_bundle
    from tools.validate_run_bundle_semantic import _authority_pins_decision_receipt, _verify_file, canonical_content_id, decision_receipt_content_id, file_content_id
except ModuleNotFoundError:  # unittest discover -s tools places tools/ on sys.path
    from validate_run_bundle import ROOT, load_document, validate_run_bundle
    from validate_run_bundle_semantic import _authority_pins_decision_receipt, _verify_file, canonical_content_id, decision_receipt_content_id, file_content_id


FIXTURE_ROOT = ROOT / "acceptance/fixtures/run-bundles"
ACCEPTANCE_AUTHORITY_REGISTRY_CONTENT_ID = "sha256:3d9e58fc18eec4e479a573a2a4205f6cbe05c4dc396ce84afe5f1c372c7136eb"


def _user_error_evidence(bundle: dict[str, Any]) -> dict[str, Any]:
    item = copy.deepcopy(bundle["evidence"][0])
    item["evidence_id"] = "ev_user_error"
    item["content_id"] = "sha256:cdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcd"
    item["provenance_id"] = "sha256:dededededededededededededededededededededededededededededededededede"
    item["direction"] = "REFUTES"
    item["assertion_source"] = "user_external"
    item["derivation_method"] = "user_supplied"
    item["evidence_ceiling"] = "SUPPORTED_WITH_LIMITS"
    item["artifacts"][0]["artifact_id"] = "art_user_error"
    item["artifacts"][0]["description"] = "User supplied compiler error"
    return item


def mutate_empty_accept(bundle: dict[str, Any]) -> None:
    bundle["instance"]["tasks"] = []
    bundle["instance"]["claims"] = []
    bundle["instance"]["gates"] = []


def mutate_pass_without_evidence(bundle: dict[str, Any]) -> None:
    bundle["instance"]["gates"][0]["evidence_refs"] = []


def mutate_fake_qualified_receipt(bundle: dict[str, Any]) -> None:
    receipt = bundle["receipts"][0]
    receipt["inputs"] = []
    receipt["outputs"] = []
    receipt["coverage_summary"] = {
        "expected_units": 0,
        "processed_units": 0,
        "failed_units": 0,
        "skipped_units": 0,
    }


def mutate_proven_with_refutation(bundle: dict[str, Any]) -> None:
    bundle["claims"][0]["refuting_evidence_refs"] = ["ev_structural"]


def mutate_external_error_without_reason(bundle: dict[str, Any]) -> None:
    bundle["evidence"].append(_user_error_evidence(bundle))
    bundle["instance"]["external_failures"] = [
        {
            "failure_id": "xf_user",
            "evidence_ref": "ev_user_error",
            "applicability_status": "DOES_NOT_APPLY",
            "reason": "",
            "reconciliation_evidence_refs": [],
        }
    ]


def mutate_quick_accept(bundle: dict[str, Any]) -> None:
    policy = load_document(ROOT / "policies/quick.yaml")
    bundle["run_policy"] = policy
    bundle["instance"]["assurance_policy"] = {
        "policy_id": "quick",
        "version": "0.1.0-draft",
        "preset": "QUICK",
        "outcome_authority": "HINTS_ONLY",
    }
    bundle["instance"]["mode"] = "EXPLORE"


def mutate_unresolved_user_error_accept(bundle: dict[str, Any]) -> None:
    bundle["instance"]["final_verdict"] = "ACCEPT"
    bundle["evidence"].append(_user_error_evidence(bundle))
    bundle["claims"][0]["refuting_evidence_refs"] = ["ev_user_error"]
    bundle["instance"]["external_failures"] = [
        {
            "failure_id": "xf_user",
            "evidence_ref": "ev_user_error",
            "applicability_status": "UNKNOWN",
            "reason": "The supplied compiler error has not been reproduced or excluded.",
            "reconciliation_evidence_refs": [],
        }
    ]


def mutate_false_complete_coverage(bundle: dict[str, Any]) -> None:
    bundle["evidence"][0]["coverage"]["covered_units"] = 0


def mutate_strict_single_source(bundle: dict[str, Any]) -> None:
    bundle["claims"][0]["supporting_evidence_refs"] = ["ev_parser"]
    bundle["instance"]["gates"][0]["evidence_refs"] = ["ev_parser"]


def mutate_forged_accept_with_risk(bundle: dict[str, Any]) -> None:
    bundle["instance"]["final_verdict"] = "ACCEPT_WITH_RISK"


def mutate_custom_policy_overclaim(bundle: dict[str, Any]) -> None:
    policy = bundle["run_policy"]
    policy["id"] = "custom-fast-but-final"
    policy["preset"] = "CUSTOM"
    policy["base_preset"] = "STRICT"
    policy["customization_reason"] = "Reduce checks for speed while attempting to retain final authority."
    policy["evidence_requirements"]["coverage_requirement"] = "BEST_EFFORT"
    policy["evidence_requirements"]["corroboration"] = "NOT_REQUIRED"
    policy["evidence_requirements"]["minimum_independent_sources"] = 1
    policy["evidence_requirements"]["high_risk_minimum_independent_sources"] = 1
    policy["evidence_requirements"]["active_negative_canary"] = False
    policy["provider_strategy"]["fallback_required"] = False
    policy["base_policy_content_id"] = canonical_content_id(load_document(ROOT / "policies/strict.yaml"))
    bundle["instance"]["assurance_policy"]["policy_id"] = "custom-fast-but-final"
    bundle["instance"]["assurance_policy"]["preset"] = "CUSTOM"


def mutate_build_without_rejecting_adopt(bundle: dict[str, Any]) -> None:
    decision = bundle["provider_adoption_decisions"][0]
    decision["selected_action"] = "BUILD"
    decision["selected_candidate_id"] = "internal-build"
    decision["candidates"].append(
        {
            "candidate_id": "internal-build",
            "source_identity": "planned-internal-implementation",
            "immutable_revision": "design-only",
            "maturity": "EXPERIMENTAL",
            "license_status": "ACCEPTABLE",
            "fit": "DIRECT",
            "decision_layer": "BUILD",
            "disposition": "SELECTED",
            "reason": "Attempted build without rejecting the direct candidate.",
            "evidence_refs": ["design_note"],
        }
    )


def mutate_adapt_without_rejecting_adopt(bundle: dict[str, Any]) -> None:
    decision = bundle["provider_adoption_decisions"][0]
    decision["selected_action"] = "ADAPT"
    decision["selected_candidate_id"] = "fixture-adapter"
    decision["candidates"][0]["disposition"] = "DEFERRED"
    decision["candidates"].append({
        "candidate_id": "fixture-adapter",
        "source_identity": "acceptance-fixture://fixture-adapter",
        "provider_artifact_content_id": "sha256:" + "6" * 64,
        "immutable_revision": "fixture-adapter@1.0+sha256:" + "6" * 64,
        "maturity": "MATURE",
        "license_status": "ACCEPTABLE",
        "fit": "ADAPTER_REQUIRED",
        "decision_layer": "ADAPT",
        "disposition": "SELECTED",
        "reason": "Fixture adapter selected without rejecting the direct candidate.",
        "evidence_refs": ["rcpt_parser", "ev_parser"],
    })


def mutate_strict_axis_downgrade(bundle: dict[str, Any]) -> None:
    requirements = bundle["run_policy"]["evidence_requirements"]
    requirements["coverage_requirement"] = "BEST_EFFORT"
    requirements["minimum_independent_sources"] = 1
    requirements["high_risk_minimum_independent_sources"] = 1
    requirements["active_negative_canary"] = False
    bundle["run_policy"]["provider_strategy"]["fallback_required"] = False


def mutate_inactive_profile_accept(bundle: dict[str, Any]) -> None:
    profile = load_document(ROOT / "profiles/recovery-review/PROFILE.yaml")
    content_ids = []
    for capability_id in profile["capabilities"]["required"]:
        capability = load_document(ROOT / f"capabilities/{capability_id}/CAPABILITY.yaml")
        content_ids.append(canonical_content_id(capability))
    bundle["instance"]["profile"] = {
        "profile_id": profile["id"],
        "version": profile["version"],
        "profile_content_id": canonical_content_id(profile),
        "capability_contract_content_ids": content_ids,
    }


def mutate_all_required_false(bundle: dict[str, Any]) -> None:
    for task in bundle["instance"]["tasks"]:
        task["required_for_verdict"] = False
    for claim in bundle["instance"]["claims"]:
        claim["required_for_verdict"] = False


def mutate_not_applicable_without_evidence(bundle: dict[str, Any]) -> None:
    claim = bundle["claims"][0]
    claim["claim_status"] = "NOT_APPLICABLE"
    claim["supporting_evidence_refs"] = []
    claim["applicability_basis"] = {"reason": "Self-declared out of scope", "evidence_refs": ["ev_missing"]}
    bundle["instance"]["claims"][0]["claim_status"] = "NOT_APPLICABLE"
    gate = bundle["instance"]["gates"][0]
    gate["gate_status"] = "NOT_APPLICABLE"
    gate["evidence_refs"] = []
    gate["applicability_basis_ref"] = claim["claim_id"]


def mutate_missing_task_receipt(bundle: dict[str, Any]) -> None:
    bundle["instance"]["tasks"][0]["receipt_refs"] = ["rcpt_missing"]


def mutate_same_receipt_fake_independence(bundle: dict[str, Any]) -> None:
    first = bundle["evidence"][0]
    second = bundle["evidence"][1]
    second["capability"] = copy.deepcopy(first["capability"])
    second["receipt_refs"] = ["rcpt_parser"]
    second["freshness_basis"]["receipt_ref"] = "rcpt_parser"
    second["artifacts"] = copy.deepcopy(first["artifacts"])


def mutate_provider_mismatch(bundle: dict[str, Any]) -> None:
    bundle["evidence"][0]["capability"]["provider_id"] = "forged-provider"


def mutate_forged_artifact(bundle: dict[str, Any]) -> None:
    bundle["evidence"][0]["artifacts"][0]["content_id"] = "sha256:" + "f" * 64


def mutate_missing_artifact(bundle: dict[str, Any]) -> None:
    location = "acceptance/fixtures/run-bundles/artifacts/does-not-exist.json"
    bundle["receipts"][0]["outputs"][0]["location"] = location
    bundle["evidence"][0]["artifacts"][0]["location"] = location


def mutate_stale_claim_workspace(bundle: dict[str, Any]) -> None:
    bundle["claims"][0]["workspace_snapshot_id"] = "wss_stale"


def mutate_unrelated_scope(bundle: dict[str, Any]) -> None:
    for item in bundle["evidence"]:
        item["scope"]["files"] = ["unrelated.cpp"]


def mutate_model_inference_proof(bundle: dict[str, Any]) -> None:
    item = bundle["evidence"][0]
    item["derivation_method"] = "model_inference"
    item["assertion_source"] = "model"


def mutate_strict_missing_canary(bundle: dict[str, Any]) -> None:
    bundle["receipts"][0].pop("canary")


def mutate_canary_not_detected(bundle: dict[str, Any]) -> None:
    canary = bundle["receipts"][0]["canary"]
    canary["status"] = "FAIL"
    canary["observed_signal"] = False


def mutate_collaboration_mismatch(bundle: dict[str, Any]) -> None:
    bundle["collaboration_snapshot"]["readiness"] = "PARTIAL_EXPECTED_CODE"
    component = bundle["collaboration_snapshot"]["components"][0]
    component["code_availability"] = "EXPECTED_MISSING"
    bundle["collaboration_snapshot"]["unknowns"] = ["Consumer code has not arrived"]


def mutate_user_error_dismissed_by_local_green(bundle: dict[str, Any]) -> None:
    bundle["evidence"].append(_user_error_evidence(bundle))
    bundle["instance"]["external_failures"] = [{
        "failure_id": "xf_user",
        "evidence_ref": "ev_user_error",
        "applicability_status": "DOES_NOT_APPLY",
        "reason": "Local result was green",
        "reconciliation_evidence_refs": ["ev_parser"],
        "reconciliation_claim_ref": "cl_build_validity",
        "reconciliation_receipt_ref": "rcpt_parser",
        "reconciliation_dimensions": [
            "REVISION_PATCHSET", "TARGET", "TOOLCHAIN_FLAGS",
            "HEADERS_GENERATED_DEPENDENCIES", "FILE_SYMBOL_PATH", "DIFFERENCE_BASIS",
        ],
    }]


def mutate_expired_waiver(bundle: dict[str, Any]) -> None:
    gate = bundle["instance"]["gates"][0]
    gate["gate_status"] = "WAIVED"
    gate["waiver_ref"] = "wvr_expired"
    bundle["instance"]["final_verdict"] = "ACCEPT_WITH_RISK"
    bundle["waivers"] = [{
        "schema_version": "1.0.0",
        "waiver_id": "wvr_expired",
        "gate_id": gate["gate_id"],
        "status": "ACTIVE",
        "scope": {
            "workspace_snapshot_id": bundle["workspace_snapshot"]["snapshot_id"],
            "gate_ids": [gate["gate_id"]],
            "claim_ids": gate["claim_refs"],
        },
        "reason": "Fixture expired waiver",
        "accepted_risk": "Known structural risk",
        "authorized_by": "fixture-authority",
        "authority_ref": "authority_fixture",
        "issued_at": "1999-01-01T00:00:00Z",
        "expires_at": "2000-01-01T00:00:00Z",
        "approval_receipt_ref": "rcpt_waiver",
    }]
    bundle["receipts"].append({
        "schema_version": "1.0.0", "receipt_id": "rcpt_waiver", "receipt_type": "WAIVER",
        "run_id": bundle["instance"]["run_id"], "created_at": "1999-01-01T00:00:00Z",
        "execution_status": "COMPLETED", "content_id": "sha256:" + "1" * 64,
        "provenance_id": "sha256:" + "2" * 64,
        "decision": {
            "subject": gate["gate_id"], "decision": "WAIVED", "reason": "Fixture",
            "authority_ref": "authority_fixture", "scope": [gate["gate_id"]],
        },
    })


def mutate_selected_candidate_rejected(bundle: dict[str, Any]) -> None:
    bundle["provider_adoption_decisions"][0]["candidates"][0]["disposition"] = "REJECTED"


def mutate_unacceptable_provider_license(bundle: dict[str, Any]) -> None:
    bundle["provider_adoption_decisions"][0]["candidates"][0]["license_status"] = "UNACCEPTABLE"


def mutate_provider_fake_refs(bundle: dict[str, Any]) -> None:
    bundle["provider_adoption_decisions"][0]["evidence_refs"] = ["ev_missing"]


def mutate_provider_gate_fail(bundle: dict[str, Any]) -> None:
    bundle["provider_adoption_decisions"][0]["gate_result"] = "FAIL"


def mutate_missing_provider_qualification(bundle: dict[str, Any]) -> None:
    bundle["provider_qualifications"] = []


def mutate_self_issued_qualification(bundle: dict[str, Any]) -> None:
    qualification = bundle["provider_qualifications"][0]
    qualification["qualified_by"] = qualification["provider_id"]


def mutate_expired_qualification(bundle: dict[str, Any]) -> None:
    bundle["provider_qualifications"][0]["expires_at"] = "2026-09-01T00:00:01Z"


def mutate_qualification_artifact_forged(bundle: dict[str, Any]) -> None:
    bundle["provider_qualifications"][0]["qualification_artifact"]["content_id"] = "sha256:" + "e" * 64


def mutate_missing_reports(bundle: dict[str, Any]) -> None:
    bundle["reports"] = []
    bundle["instance"]["report_refs"] = []


def mutate_report_fact_drift(bundle: dict[str, Any]) -> None:
    bundle["reports"][0]["fact_digest"] = "sha256:" + "d" * 64


def mutate_bundle_digest_forged(bundle: dict[str, Any]) -> None:
    bundle["instance"]["run_bundle_digest"] = "sha256:" + "c" * 64


def mutate_manifest_digest_forged(bundle: dict[str, Any]) -> None:
    bundle["workspace_snapshot"]["file_manifest"]["content_id"] = "sha256:" + "b" * 64


def mutate_target_input_mismatch(bundle: dict[str, Any]) -> None:
    target = bundle["receipts"][0]["inputs"][0]
    target["content_id"] = "sha256:d618c758c4a31eea28192878f7b3b473b26b5ae635b2dc84c078616a7cce1bdd"
    target["location"] = "acceptance/fixtures/run-bundles/canary/control.cpp"


def mutate_claim_authority_missing(bundle: dict[str, Any]) -> None:
    bundle["claims"][0]["required_authority_tiers"].append("qualified_compiler_for_declared_scope")


def mutate_duplicate_nested_ids(bundle: dict[str, Any]) -> None:
    duplicate = copy.deepcopy(bundle["instance"]["tasks"][0])
    duplicate["capability_id"] = "change-safety"
    duplicate["receipt_refs"] = ["rcpt_structural"]
    bundle["instance"]["tasks"].append(duplicate)


def mutate_task_dependency_cycle(bundle: dict[str, Any]) -> None:
    bundle["instance"]["tasks"][0]["depends_on"] = ["task_structural"]
    bundle["instance"]["tasks"][1]["depends_on"] = ["task_parser"]


def mutate_authoritative_profile_missing(bundle: dict[str, Any]) -> None:
    bundle["workspace_snapshot"]["build_context"]["authoritative_profile_id"] = "missing_profile"


def mutate_collaboration_repo_missing(bundle: dict[str, Any]) -> None:
    bundle["collaboration_snapshot"]["components"][0]["repository_id"] = "repo_missing"


def mutate_dirty_capture_without_patch(bundle: dict[str, Any]) -> None:
    repository = bundle["workspace_snapshot"]["repositories"][0]
    repository["working_tree_status"] = "DIRTY_CAPTURED"
    repository.pop("patchset_content_id", None)


def mutate_unauthorized_mutation(bundle: dict[str, Any]) -> None:
    baseline = copy.deepcopy(bundle["workspace_snapshot"])
    baseline["snapshot_id"] = "wss_before_mutation"
    baseline["content_id"] = "sha256:" + "3" * 64
    bundle["baseline_workspace_snapshot"] = baseline
    bundle["receipts"].append({
        "schema_version": "1.0.0", "receipt_id": "rcpt_authorization", "receipt_type": "AUTHORIZATION",
        "run_id": bundle["instance"]["run_id"], "workspace_snapshot_id": baseline["snapshot_id"],
        "created_at": "2026-09-02T00:01:10Z", "execution_status": "COMPLETED",
        "content_id": "sha256:" + "4" * 64, "provenance_id": "sha256:" + "5" * 64,
        "decision": {
            "subject": "source_mutation", "decision": "GRANTED", "reason": "Only src/allowed.cpp",
            "authority_ref": "authority_fixture", "scope": ["repo_main", "src/allowed.cpp"],
            "expires_at": "2026-09-03T00:00:00Z",
        },
        "edit_authorization": {
            "repository_ids": ["repo_main"], "allowed_paths": ["src/allowed.cpp"],
            "forbidden_paths": ["secrets"], "maximum_changed_files": 1,
            "maximum_deleted_lines": 2, "expires_at": "2026-09-03T00:00:00Z",
        },
    })
    bundle["receipts"].append({
        "schema_version": "1.0.0", "receipt_id": "rcpt_mutation", "receipt_type": "MUTATION",
        "run_id": bundle["instance"]["run_id"], "workspace_snapshot_id": bundle["workspace_snapshot"]["snapshot_id"],
        "capability_id": "change-safety", "created_at": "2026-09-02T00:01:20Z",
        "execution_status": "COMPLETED", "content_id": "sha256:" + "6" * 64,
        "provenance_id": "sha256:" + "7" * 64,
        "mutation": {
            "authorization_receipt_ref": "rcpt_authorization", "changed_paths": ["secrets/outside.cpp"],
            "deleted_lines": 1, "baseline_content_id": baseline["content_id"],
            "result_content_id": bundle["workspace_snapshot"]["content_id"],
            "diff_content_id": "sha256:" + "8" * 64,
        },
    })
    bundle["instance"]["mutation_validation_status"] = "VALIDATED"


def mutate_strict_accept_without_profile(bundle: dict[str, Any]) -> None:
    bundle["instance"]["profile"] = None
    bundle["instance"]["final_verdict"] = "ACCEPT"


def mutate_duplicate_receipt_alias_fake_independence(bundle: dict[str, Any]) -> None:
    original_receipt = bundle["receipts"][0]
    alias = copy.deepcopy(original_receipt)
    alias["receipt_id"] = "rcpt_parser_alias"
    bundle["receipts"].append(alias)
    first = bundle["evidence"][0]
    second = bundle["evidence"][1]
    second["capability"] = copy.deepcopy(first["capability"])
    second["authority_tier"] = first["authority_tier"]
    second["receipt_refs"] = [alias["receipt_id"]]
    second["freshness_basis"]["receipt_ref"] = alias["receipt_id"]
    second["artifacts"] = copy.deepcopy(first["artifacts"])


def mutate_derivation_label_fake_independence(bundle: dict[str, Any]) -> None:
    mutate_duplicate_receipt_alias_fake_independence(bundle)
    bundle["evidence"][1]["derivation_method"] = "lexical_search"


def mutate_untrusted_qualification_authority(bundle: dict[str, Any]) -> None:
    qualification = bundle["provider_qualifications"][0]
    qualification["qualified_by"] = "untrusted-self-assertion"
    qualification["authority_ref"] = "authority_untrusted_self_assertion"


def mutate_qualification_artifact_semantic_drift(bundle: dict[str, Any]) -> None:
    bundle["provider_qualifications"][0]["provider_version"] = "9.9-forged"


def mutate_fabricated_adoption_source(bundle: dict[str, Any]) -> None:
    candidate = bundle["provider_adoption_decisions"][0]["candidates"][0]
    candidate["source_identity"] = "fabricated://does-not-exist"
    candidate["immutable_revision"] = "fake-revision"


def mutate_https_source_without_matching_attestation(bundle: dict[str, Any]) -> None:
    candidate = bundle["provider_adoption_decisions"][0]["candidates"][0]
    candidate["source_identity"] = "https://example.invalid/nonexistent/provider.git"


def mutate_irrelevant_adoption_evidence(bundle: dict[str, Any]) -> None:
    bundle["provider_adoption_decisions"][0]["evidence_refs"] = ["rcpt_structural"]


def mutate_mutation_without_post_validation(bundle: dict[str, Any]) -> None:
    mutate_unauthorized_mutation(bundle)
    bundle["receipts"][-1]["mutation"]["changed_paths"] = ["src/allowed.cpp"]


def mutate_authority_registry_binding(bundle: dict[str, Any]) -> None:
    bundle["trust_context"]["authority_registry_content_id"] = "sha256:" + "0" * 64


def mutate_qualification_wrong_environment(bundle: dict[str, Any]) -> None:
    bundle["trust_context"]["environment_scope"] = "LOCAL_DEVELOPMENT"


def mutate_fictional_mutation_without_manifest_change(bundle: dict[str, Any]) -> None:
    mutate_unauthorized_mutation(bundle)
    authorization = bundle["receipts"][-2]
    mutation = bundle["receipts"][-1]
    authorization["edit_authorization"]["allowed_paths"] = ["src/allowed.cpp"]
    mutation["mutation"]["changed_paths"] = ["src/allowed.cpp"]


MUTATORS: dict[str, Callable[[dict[str, Any]], None]] = {
    "empty_accept": mutate_empty_accept,
    "pass_without_evidence": mutate_pass_without_evidence,
    "fake_qualified_receipt": mutate_fake_qualified_receipt,
    "proven_with_refutation": mutate_proven_with_refutation,
    "external_error_without_reason": mutate_external_error_without_reason,
    "quick_accept": mutate_quick_accept,
    "unresolved_user_error_accept": mutate_unresolved_user_error_accept,
    "false_complete_coverage": mutate_false_complete_coverage,
    "strict_single_source": mutate_strict_single_source,
    "forged_accept_with_risk": mutate_forged_accept_with_risk,
    "custom_policy_overclaim": mutate_custom_policy_overclaim,
    "build_without_rejecting_adopt": mutate_build_without_rejecting_adopt,
    "adapt_without_rejecting_adopt": mutate_adapt_without_rejecting_adopt,
    "strict_axis_downgrade": mutate_strict_axis_downgrade,
    "inactive_profile_accept": mutate_inactive_profile_accept,
    "all_required_false": mutate_all_required_false,
    "not_applicable_without_evidence": mutate_not_applicable_without_evidence,
    "missing_task_receipt": mutate_missing_task_receipt,
    "same_receipt_fake_independence": mutate_same_receipt_fake_independence,
    "provider_mismatch": mutate_provider_mismatch,
    "forged_artifact": mutate_forged_artifact,
    "missing_artifact": mutate_missing_artifact,
    "stale_claim_workspace": mutate_stale_claim_workspace,
    "unrelated_scope": mutate_unrelated_scope,
    "model_inference_proof": mutate_model_inference_proof,
    "strict_missing_canary": mutate_strict_missing_canary,
    "canary_not_detected": mutate_canary_not_detected,
    "collaboration_mismatch": mutate_collaboration_mismatch,
    "user_error_dismissed_by_local_green": mutate_user_error_dismissed_by_local_green,
    "expired_waiver": mutate_expired_waiver,
    "selected_candidate_rejected": mutate_selected_candidate_rejected,
    "unacceptable_provider_license": mutate_unacceptable_provider_license,
    "provider_fake_refs": mutate_provider_fake_refs,
    "provider_gate_fail": mutate_provider_gate_fail,
    "missing_provider_qualification": mutate_missing_provider_qualification,
    "self_issued_qualification": mutate_self_issued_qualification,
    "expired_qualification": mutate_expired_qualification,
    "qualification_artifact_forged": mutate_qualification_artifact_forged,
    "missing_reports": mutate_missing_reports,
    "report_fact_drift": mutate_report_fact_drift,
    "bundle_digest_forged": mutate_bundle_digest_forged,
    "manifest_digest_forged": mutate_manifest_digest_forged,
    "target_input_mismatch": mutate_target_input_mismatch,
    "claim_authority_missing": mutate_claim_authority_missing,
    "duplicate_nested_ids": mutate_duplicate_nested_ids,
    "task_dependency_cycle": mutate_task_dependency_cycle,
    "authoritative_profile_missing": mutate_authoritative_profile_missing,
    "collaboration_repo_missing": mutate_collaboration_repo_missing,
    "dirty_capture_without_patch": mutate_dirty_capture_without_patch,
    "unauthorized_mutation": mutate_unauthorized_mutation,
    "strict_accept_without_profile": mutate_strict_accept_without_profile,
    "duplicate_receipt_alias_fake_independence": mutate_duplicate_receipt_alias_fake_independence,
    "derivation_label_fake_independence": mutate_derivation_label_fake_independence,
    "untrusted_qualification_authority": mutate_untrusted_qualification_authority,
    "qualification_artifact_semantic_drift": mutate_qualification_artifact_semantic_drift,
    "fabricated_adoption_source": mutate_fabricated_adoption_source,
    "https_source_without_matching_attestation": mutate_https_source_without_matching_attestation,
    "irrelevant_adoption_evidence": mutate_irrelevant_adoption_evidence,
    "mutation_without_post_validation": mutate_mutation_without_post_validation,
    "authority_registry_binding": mutate_authority_registry_binding,
    "qualification_wrong_environment": mutate_qualification_wrong_environment,
    "fictional_mutation_without_manifest_change": mutate_fictional_mutation_without_manifest_change,
}


class RunBundleValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base = load_document(FIXTURE_ROOT / "valid-strict.yaml")
        with (FIXTURE_ROOT / "negative-cases.yaml").open("r", encoding="utf-8") as handle:
            cls.catalog = yaml.safe_load(handle)

    def test_valid_strict_vertical_fixture_passes(self) -> None:
        self.assertEqual(
            validate_run_bundle(
                copy.deepcopy(self.base),
                expected_authority_registry_content_id=ACCEPTANCE_AUTHORITY_REGISTRY_CONTENT_ID,
            ),
            [],
        )

    def test_missing_external_authority_registry_anchor_is_rejected(self) -> None:
        issues = validate_run_bundle(copy.deepcopy(self.base))
        self.assertTrue(any(issue.startswith("AUTHORITY_REGISTRY_TRUST_ANCHOR:") for issue in issues), issues)

    def test_wrong_external_authority_registry_anchor_is_rejected(self) -> None:
        issues = validate_run_bundle(
            copy.deepcopy(self.base),
            expected_authority_registry_content_id="sha256:" + "0" * 64,
        )
        self.assertTrue(any(issue.startswith("AUTHORITY_REGISTRY_TRUST_ANCHOR:") for issue in issues), issues)

    def test_every_catalog_case_has_a_mutator(self) -> None:
        case_ids = {case["id"] for case in self.catalog["cases"]}
        self.assertEqual(case_ids, set(MUTATORS))

    def test_negative_catalog_is_rejected_for_expected_reason(self) -> None:
        for case in self.catalog["cases"]:
            with self.subTest(case=case["id"]):
                bundle = copy.deepcopy(self.base)
                MUTATORS[case["id"]](bundle)
                issues = validate_run_bundle(
                    bundle,
                    expected_authority_registry_content_id=ACCEPTANCE_AUTHORITY_REGISTRY_CONTENT_ID,
                )
                self.assertTrue(
                    any(issue.startswith(f"{case['expected_issue']}:") for issue in issues),
                    msg=f"{case['id']} expected {case['expected_issue']}, got {issues}",
                )

    def test_additional_artifact_root_is_explicit_and_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            approved_root = Path(directory).resolve()
            artifact = approved_root / "run" / "result.json"
            artifact.parent.mkdir()
            artifact.write_text('{"result":"bounded"}', encoding="utf-8")
            reference = {"location": str(artifact), "content_id": file_content_id(artifact)}
            issues: list[str] = []
            self.assertTrue(_verify_file(reference, "external result", issues, {}, [approved_root]))
            self.assertEqual(issues, [])

            escaped = ROOT / "acceptance/fixtures/run-bundles/artifacts/parser-diagnostics.json"
            issues = []
            self.assertFalse(
                _verify_file(
                    {"location": str(escaped), "content_id": file_content_id(escaped)},
                    "escaped result",
                    issues,
                    {},
                    [approved_root],
                )
            )
            self.assertTrue(any(issue.startswith("ARTIFACT_PATH:") for issue in issues))

    def test_matching_authority_permission_without_pinned_authorization_is_insufficient(self) -> None:
        receipt = {
            "receipt_id": "rcpt_test_authorization",
            "receipt_type": "AUTHORIZATION",
            "issued_by": "fixture-issuer",
            "decision": {"authority_ref": "authority_fixture", "decision": "GRANTED"},
        }
        receipt["content_id"] = decision_receipt_content_id(receipt)
        authority = {
            "status": "ACTIVE",
            "environment_scope": "ACCEPTANCE_FIXTURE",
            "permissions": ["MUTATION_AUTHORIZATION"],
            "issuer_id": "fixture-issuer",
            "authorization_receipt_content_ids": [],
        }
        self.assertFalse(_authority_pins_decision_receipt(
            authority, receipt, "MUTATION_AUTHORIZATION", "authorization_receipt_content_ids", "ACCEPTANCE_FIXTURE"
        ))
        authority["authorization_receipt_content_ids"] = [receipt["content_id"]]
        self.assertTrue(_authority_pins_decision_receipt(
            authority, receipt, "MUTATION_AUTHORIZATION", "authorization_receipt_content_ids", "ACCEPTANCE_FIXTURE"
        ))

    def test_cli_automatically_approves_bundle_directory_for_relative_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory).resolve()
            (run_root / "reports").mkdir()
            source_root = FIXTURE_ROOT
            portable_root = run_root / "acceptance/fixtures/run-bundles"
            for source in source_root.rglob("*"):
                if source.is_file():
                    destination = portable_root / source.relative_to(source_root)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(source.read_bytes())
            bundle_path = run_root / "run-bundle.yaml"
            bundle_path.write_bytes((source_root / "valid-strict.yaml").read_bytes())
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/validate_run_bundle.py"),
                    str(bundle_path),
                    "--authority-registry",
                    str(ROOT / "governance/TRUSTED_AUTHORITY_REGISTRY.yaml"),
                    "--authority-registry-content-id",
                    ACCEPTANCE_AUTHORITY_REGISTRY_CONTENT_ID,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
