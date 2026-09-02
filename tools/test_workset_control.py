#!/usr/bin/env python3
"""Focused tests for minimum-workset resolution and the desktop control plane."""

from __future__ import annotations

import json
import copy
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import render_toolkit_console, workset_control  # noqa: E402


class WorksetResolutionTests(unittest.TestCase):
    def test_focused_review_is_smaller_than_registered_toolkit(self) -> None:
        request = workset_control.resolve_request(
            "focused-code-review",
            operation="BUILD_MISSING",
            policy="BALANCED",
            time_budget_minutes=45,
            permission="TOOLKIT_ONLY",
        )
        selected = {item["id"] for item in request["selected_capabilities"]}
        registered = set(workset_control.catalog_snapshot()["registered_ids"])
        self.assertLess(len(selected), len(registered))
        self.assertEqual(selected | {item["id"] for item in request["excluded_capabilities"]}, registered)
        self.assertEqual(request["conclusion_ceiling"], "NO_VERDICT")

    def test_continuation_cannot_expand_scope(self) -> None:
        request = workset_control.resolve_request(
            "windows-cpp-precheck",
            operation="USE_AVAILABLE",
            policy="BALANCED",
            time_budget_minutes=20,
            permission="READ_ONLY",
        )
        selected = {item["id"] for item in request["selected_capabilities"]}
        self.assertEqual(selected, {"workspace-snapshot", "windows-static-precheck", "evidence-kernel", "report-renderer"})
        self.assertNotIn("experience-memory", selected)

    def test_build_requires_toolkit_only_permission(self) -> None:
        with self.assertRaisesRegex(ValueError, "TOOLKIT_ONLY"):
            workset_control.resolve_request(
                "focused-code-review",
                operation="BUILD_MISSING",
                policy="BALANCED",
                time_budget_minutes=45,
                permission="READ_ONLY",
            )

    def test_use_downgrades_when_required_capability_is_unavailable(self) -> None:
        request = workset_control.resolve_request(
            "focused-code-review",
            operation="USE_AVAILABLE",
            policy="BALANCED",
            time_budget_minutes=30,
            permission="READ_ONLY",
        )
        self.assertIn("UNAVAILABLE", {item["disposition"] for item in request["selected_capabilities"]})
        self.assertEqual(request["conclusion_ceiling"], "NO_VERDICT")

    def test_partial_capability_is_visible_as_limited_not_fully_runnable(self) -> None:
        request = workset_control.resolve_request(
            "windows-cpp-precheck",
            operation="USE_AVAILABLE",
            policy="BALANCED",
            time_budget_minutes=20,
            permission="READ_ONLY",
        )
        windows = next(item for item in request["selected_capabilities"] if item["id"] == "windows-static-precheck")
        self.assertEqual(windows["disposition"], "RUN_LIMITED")

    def test_assurance_policy_is_content_addressed_not_just_a_label(self) -> None:
        request = workset_control.resolve_request(
            "windows-cpp-precheck",
            operation="USE_AVAILABLE",
            policy="STRICT",
            time_budget_minutes=20,
            permission="READ_ONLY",
        )
        policy_path = ROOT / "policies/strict.yaml"
        self.assertEqual(request["assurance_policy_ref"], "policies/strict.yaml")
        self.assertEqual(request["assurance_policy_digest"], workset_control.file_content_id(policy_path))

        tampered = copy.deepcopy(request)
        tampered["assurance_policy_digest"] = "sha256:" + "0" * 64
        tampered["intent_digest"] = workset_control.digest_without(tampered, "intent_digest")
        with self.assertRaisesRegex(ValueError, "assurance_policy_digest"):
            workset_control.validate_request(tampered)


class WorksetRuntimeTests(unittest.TestCase):
    def test_request_claim_and_evidenced_step_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            request = workset_control.resolve_request(
                "windows-cpp-precheck",
                operation="USE_AVAILABLE",
                policy="QUICK",
                time_budget_minutes=15,
                permission="READ_ONLY",
            )
            request_path = workset_control.persist_request(request, runtime)
            self.assertTrue(request_path.is_file())
            run, run_path = workset_control.claim_request(runtime, request["request_id"])
            self.assertTrue(run_path.is_file())
            first_step = run["steps"][0]["id"]
            run, _ = workset_control.update_run(runtime, run["run_id"], first_step, "RUNNING", "开始冻结范围。", [], run["revision"])
            self.assertEqual(run["execution_status"], "RUNNING")
            with self.assertRaisesRegex(ValueError, "evidence"):
                workset_control.update_run(runtime, run["run_id"], first_step, "COMPLETED", "完成。", [], run["revision"])
            with self.assertRaisesRegex(ValueError, "non-blank"):
                workset_control.update_run(runtime, run["run_id"], first_step, "COMPLETED", "完成。", [""], run["revision"])
            artifact = runtime / "artifacts" / "workspace-snapshot.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text('{"status":"captured"}\n', encoding="utf-8")
            artifact_reference = f"runtime:artifacts/workspace-snapshot.json#{workset_control.file_content_id(artifact)}"
            _, checkpoint_reference = workset_control.create_step_checkpoint(
                runtime,
                run["run_id"],
                first_step,
                "范围快照工件已绑定到当前步骤。",
                [{"kind": "RUNNER_CHECKPOINT", "ref": artifact_reference}],
            )
            run, _ = workset_control.update_run(runtime, run["run_id"], first_step, "COMPLETED", "范围快照已保存。", [checkpoint_reference], run["revision"])
            self.assertEqual(run["steps"][0]["status"], "COMPLETED")

    def test_nonexistent_reference_cannot_complete_a_step(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            request = workset_control.resolve_request(
                "windows-cpp-precheck", operation="USE_AVAILABLE", policy="STRICT", time_budget_minutes=20, permission="READ_ONLY"
            )
            workset_control.persist_request(request, runtime)
            run, _ = workset_control.claim_request(runtime, request["request_id"])
            fake = "runtime:checkpoints/not-real.json#sha256:" + "0" * 64
            with self.assertRaisesRegex(ValueError, "does not exist"):
                workset_control.update_run(runtime, run["run_id"], run["steps"][0]["id"], "COMPLETED", "fake", [fake], run["revision"])

    def test_unbound_real_repository_file_cannot_complete_a_step(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            request = workset_control.resolve_request(
                "windows-cpp-precheck", operation="USE_AVAILABLE", policy="STRICT", time_budget_minutes=20, permission="READ_ONLY"
            )
            workset_control.persist_request(request, runtime)
            run, _ = workset_control.claim_request(runtime, request["request_id"])
            readme = ROOT / "00_START_HERE.md"
            unbound = f"repo:00_START_HERE.md#{workset_control.file_content_id(readme)}"
            with self.assertRaisesRegex(ValueError, "WorksetStepCheckpoint"):
                workset_control.update_run(runtime, run["run_id"], run["steps"][0]["id"], "COMPLETED", "unbound", [unbound], run["revision"])

    def test_tampered_request_digest_and_catalog_closure_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            request = workset_control.resolve_request(
                "focused-code-review", operation="BUILD_MISSING", policy="STRICT", time_budget_minutes=45, permission="TOOLKIT_ONLY"
            )
            tampered = copy.deepcopy(request)
            tampered["permission"] = "REQUEST_SCOPED_BUSINESS_EDIT"
            with self.assertRaisesRegex(ValueError, "intent_digest|permission"):
                workset_control.persist_request(tampered, runtime)
            expanded = copy.deepcopy(request)
            moved = next(item for item in expanded["excluded_capabilities"] if item["id"] == "experience-memory")
            expanded["excluded_capabilities"].remove(moved)
            expanded["selected_capabilities"].append(
                {"id": "experience-memory", "reason": "tampered", "implementation_status": "NOT_IMPLEMENTED", "validation_status": "NOT_RUN", "disposition": "BUILD_OR_COMPLETE"}
            )
            expanded["intent_digest"] = workset_control.digest_without(expanded, "intent_digest")
            with self.assertRaisesRegex(ValueError, "selected_capabilities"):
                workset_control.persist_request(expanded, runtime)

    def test_all_skipped_is_not_completed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            request = workset_control.resolve_request(
                "focused-code-review", operation="BUILD_MISSING", policy="STRICT", time_budget_minutes=45, permission="TOOLKIT_ONLY"
            )
            workset_control.persist_request(request, runtime)
            run, _ = workset_control.claim_request(runtime, request["request_id"])
            for step in list(run["steps"]):
                run, _ = workset_control.update_run(runtime, run["run_id"], step["id"], "SKIPPED", "本步骤未执行。", [], run["revision"])
            self.assertEqual(run["execution_status"], "CANCELLED")
            self.assertNotEqual(run["execution_status"], "COMPLETED")

    def test_use_available_omits_unavailable_steps_and_keeps_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            request = workset_control.resolve_request(
                "windows-cpp-precheck", operation="USE_AVAILABLE", policy="BALANCED", time_budget_minutes=20, permission="READ_ONLY"
            )
            workset_control.persist_request(request, runtime)
            run, _ = workset_control.claim_request(runtime, request["request_id"])
            self.assertEqual(run["operation"], "USE_AVAILABLE")
            self.assertEqual({item["id"] for item in run["omissions"]}, {"workspace-snapshot", "evidence-kernel", "report-renderer"})
            scheduled = {capability_id for step in run["steps"] for capability_id in step["capability_ids"]}
            self.assertEqual(scheduled, {"windows-static-precheck"})

    def test_superseded_run_cannot_replace_current_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            first = workset_control.resolve_request(
                "windows-cpp-precheck", operation="USE_AVAILABLE", policy="BALANCED", time_budget_minutes=20, permission="READ_ONLY"
            )
            workset_control.persist_request(first, runtime)
            old_run, _ = workset_control.claim_request(runtime, first["request_id"])
            second = workset_control.resolve_request(
                "focused-code-review", operation="BUILD_MISSING", policy="BALANCED", time_budget_minutes=45, permission="TOOLKIT_ONLY"
            )
            workset_control.persist_request(second, runtime)
            with self.assertRaisesRegex(ValueError, "superseded"):
                workset_control.update_run(runtime, old_run["run_id"], old_run["steps"][0]["id"], "RUNNING", "late update", [], old_run["revision"])

    def test_revision_conflict_prevents_lost_update(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            request = workset_control.resolve_request(
                "focused-code-review", operation="BUILD_MISSING", policy="BALANCED", time_budget_minutes=45, permission="TOOLKIT_ONLY"
            )
            workset_control.persist_request(request, runtime)
            run, _ = workset_control.claim_request(runtime, request["request_id"])
            step = run["steps"][0]["id"]
            updated, _ = workset_control.update_run(runtime, run["run_id"], step, "RUNNING", "first update", [], run["revision"])
            with self.assertRaisesRegex(ValueError, "revision conflict"):
                workset_control.update_run(runtime, updated["run_id"], step, "RUNNING", "stale update", [], run["revision"])

    def test_claim_is_idempotent_for_the_same_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            request = workset_control.resolve_request(
                "focused-code-review",
                operation="BUILD_MISSING",
                policy="BALANCED",
                time_budget_minutes=45,
                permission="TOOLKIT_ONLY",
            )
            workset_control.persist_request(request, runtime)
            first, _ = workset_control.claim_request(runtime, request["request_id"])
            second, _ = workset_control.claim_request(runtime, request["request_id"])
            self.assertEqual(first["run_id"], second["run_id"])

    def test_new_request_is_not_hidden_behind_an_older_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            first_request = workset_control.resolve_request(
                "windows-cpp-precheck",
                operation="USE_AVAILABLE",
                policy="QUICK",
                time_budget_minutes=15,
                permission="READ_ONLY",
            )
            workset_control.persist_request(first_request, runtime)
            workset_control.claim_request(runtime, first_request["request_id"])
            second_request = workset_control.resolve_request(
                "focused-code-review",
                operation="BUILD_MISSING",
                policy="BALANCED",
                time_budget_minutes=45,
                permission="TOOLKIT_ONLY",
            )
            workset_control.persist_request(second_request, runtime)
            visible = workset_control.latest_visible_state(runtime)
            self.assertEqual(visible["request_id"], second_request["request_id"])
            self.assertEqual(visible["kind"], "WorksetRequest")

    def test_old_request_cannot_be_replayed_as_latest_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary) / "eet-runtime"
            first = workset_control.resolve_request(
                "windows-cpp-precheck", operation="USE_AVAILABLE", policy="QUICK", time_budget_minutes=15, permission="READ_ONLY"
            )
            second = workset_control.resolve_request(
                "focused-code-review", operation="BUILD_MISSING", policy="BALANCED", time_budget_minutes=45, permission="TOOLKIT_ONLY"
            )
            workset_control.persist_request(first, runtime)
            workset_control.persist_request(second, runtime)
            with self.assertRaisesRegex(ValueError, "older request id"):
                workset_control.persist_request(first, runtime)

    def test_runtime_state_is_rejected_inside_repository(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside"):
            workset_control.resolve_runtime_root(ROOT / "runs" / "runtime")

    def test_runtime_state_is_rejected_inside_any_git_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "business-repository"
            (repository / ".git").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "Git repository"):
                workset_control.resolve_runtime_root(repository / ".eet-runtime")


class ConsoleRenderTests(unittest.TestCase):
    def test_console_renders_separate_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            outputs = render_toolkit_console.render(Path(temporary))
            self.assertEqual(set(outputs), {"index", "worksets", "runs"})
            worksets = outputs["worksets"].read_text(encoding="utf-8")
            runs = outputs["runs"].read_text(encoding="utf-8")
            self.assertIn("选择本次工作集", worksets)
            self.assertIn("当前运行", runs)
            self.assertIn("capability-progress.html", worksets)

    def test_visible_workset_page_does_not_dump_all_capabilities(self) -> None:
        page = (ROOT / "dashboard/workset-planner.html").read_text(encoding="utf-8")
        visible = page.split('<script id="worksetData"', 1)[0]
        self.assertNotIn("工程经验记忆", visible)
        self.assertNotIn("可观测性规划", visible)
        self.assertIn("明确排除", visible)

    def test_palette_drops_old_navy_gray_dashboard(self) -> None:
        css = (ROOT / "dashboard/assets/console.css").read_text(encoding="utf-8").lower()
        self.assertIn("--forest:", css)
        self.assertIn("--canvas: #f5ecd8", css)
        self.assertIn("background: var(--forest-strong)", css)
        self.assertNotIn("#0b2247", css)
        self.assertNotIn("#f5f7fa", css)
        self.assertNotIn("#6b7280", css)

    def test_embedded_catalog_is_parseable(self) -> None:
        page = (ROOT / "dashboard/workset-planner.html").read_text(encoding="utf-8")
        start = page.index('<script id="worksetData" type="application/json">') + len('<script id="worksetData" type="application/json">')
        end = page.index("</script>", start)
        snapshot = json.loads(page[start:end])
        self.assertEqual(len(snapshot["worksets"]), 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
