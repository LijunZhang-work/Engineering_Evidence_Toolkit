from __future__ import annotations

import unittest
from datetime import datetime, timezone

try:
    from tools.validate_toolkit import Findings, validate_status_dimensions
except ModuleNotFoundError:  # unittest discover -s tools
    from validate_toolkit import Findings, validate_status_dimensions


SOURCE = {
    "subject_id": "fixture",
    "status_axis": "implementation",
    "evidence_kind": "IMPLEMENTATION_ARTIFACT",
    "path": "acceptance/fixtures/run-bundles/workspace/sample.cpp",
    "content_id": "sha256:9e920c9d63eff27d16f021e776a187fa15e8a7f0aa885ab46ead8312de3b1cf5",
    "result": "PARTIAL",
    "observed_at": "2026-09-02T12:00:00Z",
}


def receipt(axis: str, kind: str, result: str, filename: str, content_id: str, observed_at: str) -> dict:
    return {
        "subject_id": "fixture",
        "status_axis": axis,
        "evidence_kind": kind,
        "path": f"acceptance/fixtures/status-evidence/{filename}",
        "content_id": content_id,
        "result": result,
        "observed_at": observed_at,
    }


IMPLEMENTATION = receipt("implementation", "IMPLEMENTATION_RECEIPT", "IMPLEMENTED", "fixture-implementation.json", "sha256:d277f9f5a36dba784abfb39b207ae8dd8030618d6a5ca1fa81fcdcf5d4986202", "2026-09-02T12:00:00Z")
VALIDATION_PARTIAL = receipt("validation", "TEST_RECEIPT", "PARTIAL", "fixture-validation-partial.json", "sha256:6745638905a8cc7f7b54c22a229b827e308aed4b6a1a893a3c640c240b4bfbd0", "2026-09-02T12:00:30Z")
VALIDATION = receipt("validation", "TEST_RECEIPT", "PASSED", "fixture-validation.json", "sha256:88cff092eca689b8dd2cafc5512d6fab00677844b8a7d6734c0993e341045c18", "2026-09-02T12:01:00Z")
QUALIFICATION = receipt("qualification", "QUALIFICATION_RECEIPT", "QUALIFIED", "fixture-qualification.json", "sha256:e20858855d83fc2ad2b647e249da523a0b6fbbb9c4c4d044bda32bc63c9235fb", "2026-09-02T12:02:00Z")
ACTIVATION = receipt("activation", "ACTIVATION_RECEIPT", "ACTIVE", "fixture-activation.json", "sha256:c40a8bf160fa701ecea45dba1b5c581073fd13fa034f76149e1601da16b11fb0", "2026-09-02T12:03:00Z")
UNPINNED_ACTIVATION = receipt("activation", "ACTIVATION_RECEIPT", "ACTIVE", "fixture-activation-unpinned.json", "sha256:a12fe20c522defb2de1d98986d8b95e36796cd06e1c761156c31aa338e51a53a", "2026-09-02T12:03:00Z")


def state(
    *,
    status: str,
    implementation: str,
    validation: str,
    qualification: str,
    activation: str,
    evidence: dict | None = None,
) -> dict:
    result = {
        "status": status,
        "status_dimensions": {
            "specification_status": "DESIGNED",
            "implementation_status": implementation,
            "validation_status": validation,
            "qualification_status": qualification,
            "activation_status": activation,
        },
    }
    if evidence is not None:
        result["status_evidence"] = evidence
    return result


class StatusPromotionTests(unittest.TestCase):
    def validate(self, data: dict) -> Findings:
        findings = Findings()
        validate_status_dimensions(
            data,
            "fixture",
            findings,
            required=True,
            observed_at_ceiling=datetime(2026, 9, 3, tzinfo=timezone.utc),
        )
        return findings

    def test_current_designed_state_is_legal(self) -> None:
        findings = self.validate(
            state(
                status="DESIGNED",
                implementation="NOT_IMPLEMENTED",
                validation="NOT_RUN",
                qualification="NOT_ASSESSED",
                activation="INACTIVE",
            )
        )
        self.assertEqual(findings.errors, [])

    def test_partial_implementation_can_advance_with_evidence(self) -> None:
        findings = self.validate(
            state(
                status="SCAFFOLDED",
                implementation="PARTIAL",
                validation="PARTIAL",
                qualification="NOT_ASSESSED",
                activation="INACTIVE",
                evidence={
                    "implementation": [SOURCE],
                    "validation": [VALIDATION_PARTIAL],
                },
            )
        )
        self.assertEqual(findings.errors, [])

    def test_promotion_without_evidence_is_rejected(self) -> None:
        findings = self.validate(
            state(
                status="ACTIVE",
                implementation="IMPLEMENTED",
                validation="PASSED",
                qualification="QUALIFIED",
                activation="ACTIVE",
            )
        )
        self.assertGreaterEqual(
            sum("STATUS_PROMOTION_WITHOUT_EVIDENCE" in error for error in findings.errors),
            4,
        )

    def test_full_active_state_is_legal_with_all_evidence_axes(self) -> None:
        findings = self.validate(
            state(
                status="ACTIVE",
                implementation="IMPLEMENTED",
                validation="PASSED",
                qualification="QUALIFIED",
                activation="ACTIVE",
                evidence={
                    "implementation": [IMPLEMENTATION],
                    "validation": [VALIDATION],
                    "qualification": [QUALIFICATION],
                    "activation": [ACTIVATION],
                },
            )
        )
        self.assertEqual(findings.errors, [])

    def test_nonexistent_status_evidence_is_rejected(self) -> None:
        findings = self.validate(
            state(
                status="SCAFFOLDED",
                implementation="PARTIAL",
                validation="NOT_RUN",
                qualification="NOT_ASSESSED",
                activation="INACTIVE",
                evidence={
                    "implementation": [{
                        **SOURCE,
                        "path": "does/not/exist.txt",
                        "content_id": "sha256:" + "0" * 64,
                    }]
                },
            )
        )
        self.assertTrue(any("STATUS_EVIDENCE_REF" in error for error in findings.errors))

    def test_high_level_status_cannot_claim_active_over_inactive_axes(self) -> None:
        findings = self.validate(
            state(
                status="ACTIVE",
                implementation="NOT_IMPLEMENTED",
                validation="NOT_RUN",
                qualification="NOT_ASSESSED",
                activation="INACTIVE",
            )
        )
        self.assertTrue(any("STATUS_ROLLUP" in error for error in findings.errors))

    def test_validation_cannot_pass_before_full_implementation(self) -> None:
        findings = self.validate(
            state(
                status="VALIDATED",
                implementation="PARTIAL",
                validation="PASSED",
                qualification="NOT_ASSESSED",
                activation="INACTIVE",
                evidence={
                    "implementation": [SOURCE],
                    "validation": [VALIDATION],
                },
            )
        )
        self.assertTrue(any("STATUS_ORDER" in error for error in findings.errors))

    def test_plain_document_cannot_support_active_state(self) -> None:
        fake = {
            **ACTIVATION,
            "path": "lifecycle/TOOLKIT_LIFECYCLE.yaml",
            "content_id": "sha256:" + "0" * 64,
        }
        findings = self.validate(
            state(
                status="ACTIVE",
                implementation="IMPLEMENTED",
                validation="PASSED",
                qualification="QUALIFIED",
                activation="ACTIVE",
                evidence={
                    "implementation": [IMPLEMENTATION],
                    "validation": [VALIDATION],
                    "qualification": [QUALIFICATION],
                    "activation": [fake],
                },
            )
        )
        self.assertTrue(any("STATUS_EVIDENCE_DIGEST" in error or "STATUS_EVIDENCE_RECEIPT" in error for error in findings.errors))

    def test_self_written_lookalike_status_receipt_is_not_a_trust_root(self) -> None:
        findings = self.validate(
            state(
                status="ACTIVE",
                implementation="IMPLEMENTED",
                validation="PASSED",
                qualification="QUALIFIED",
                activation="ACTIVE",
                evidence={
                    "implementation": [IMPLEMENTATION],
                    "validation": [VALIDATION],
                    "qualification": [QUALIFICATION],
                    "activation": [UNPINNED_ACTIVATION],
                },
            )
        )
        self.assertTrue(any("authority-bound" in error for error in findings.errors), findings.errors)

    def test_future_status_evidence_is_rejected(self) -> None:
        future_validation = {
            **VALIDATION_PARTIAL,
            "observed_at": "2099-01-01T00:00:00Z",
        }
        findings = self.validate(
            state(
                status="SCAFFOLDED",
                implementation="PARTIAL",
                validation="PARTIAL",
                qualification="NOT_ASSESSED",
                activation="INACTIVE",
                evidence={
                    "implementation": [SOURCE],
                    "validation": [future_validation],
                },
            )
        )
        self.assertTrue(any("STATUS_EVIDENCE_FUTURE" in error for error in findings.errors), findings.errors)


if __name__ == "__main__":
    unittest.main(verbosity=2)
