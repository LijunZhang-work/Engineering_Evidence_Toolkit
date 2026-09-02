#!/usr/bin/env python3
"""Focused tests for the categorical capability maturity dashboard."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER_PATH = ROOT / "tools/render_capability_dashboard.py"
DASHBOARD_PATH = ROOT / "dashboard/capability-progress.html"

spec = importlib.util.spec_from_file_location("eet_dashboard_renderer_test", RENDERER_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load dashboard renderer")
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def stages(kinds: list[str]) -> list[dict]:
    return [
        {"key": definition["key"], "label": definition["label"], "state_kind": kind}
        for definition, kind in zip(renderer.STAGES, kinds, strict=True)
    ]


class MaturitySemanticsTests(unittest.TestCase):
    def test_all_axes_complete_is_active(self) -> None:
        self.assertEqual(renderer.classify_maturity(stages(["complete"] * 5))[:3], ("active", "已激活", 5))

    def test_specification_only_is_designed_not_in_progress(self) -> None:
        self.assertEqual(
            renderer.classify_maturity(stages(["complete", "idle", "idle", "idle", "idle"]))[:3],
            ("designed", "仅完成设计", 1),
        )

    def test_partial_is_categorical_not_half_complete(self) -> None:
        category, label, completed, _ = renderer.classify_maturity(stages(["complete", "partial", "partial", "idle", "idle"]))
        self.assertEqual((category, label, completed), ("partial", "部分实现", 1))

    def test_failed_validation_is_blocked(self) -> None:
        category, label, _, _ = renderer.classify_maturity(stages(["complete", "complete", "failed", "idle", "idle"]))
        self.assertEqual((category, label), ("blocked", "受阻"))

    def test_unknown_axis_is_not_presented_as_precise(self) -> None:
        category, label, _, unknown = renderer.classify_maturity(stages(["complete", "partial", "unknown", "idle", "idle"]))
        self.assertEqual((category, label, unknown), ("unknown", "状态未知", ["validation"]))


class GeneratedDashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = renderer.build_snapshot()
        cls.html = DASHBOARD_PATH.read_text(encoding="utf-8")
        match = re.search(r'<script id="capabilityData" type="application/json">(.*?)</script>', cls.html, re.DOTALL)
        if not match:
            raise AssertionError("dashboard has no embedded capabilityData")
        cls.embedded = json.loads(match.group(1))

    def test_current_dashboard_is_fresh(self) -> None:
        self.assertTrue(renderer.snapshots_match(self.embedded, self.snapshot))

    def test_coordinated_active_tamper_is_detected(self) -> None:
        tampered = copy.deepcopy(self.snapshot)
        for capability in tampered["capabilities"]:
            capability["category"] = "active"
            capability["status_label"] = "已激活"
            capability["completed_axes"] = 5
            capability["unknown_stages"] = []
            for stage in capability["stages"]:
                stage["state_kind"] = "complete"
                stage["state_label"] = "完成"
                stage["status"] = "FORGED"
        tampered["summary"] = {"active": len(tampered["capabilities"]), "partial": 0, "designed": 0, "blocked": 0, "unknown": 0, "total": len(tampered["capabilities"])}
        self.assertEqual(tampered["source_digest"], self.snapshot["source_digest"])
        self.assertFalse(renderer.snapshots_match(tampered, self.snapshot))

    def test_promoted_status_displays_declared_evidence(self) -> None:
        windows = next(item for item in self.snapshot["capabilities"] if item["id"] == "windows-static-precheck")
        by_stage = {stage["key"]: stage for stage in windows["stages"]}
        self.assertIn("tools/windows_precheck_mvp.py", by_stage["implementation"]["evidence"])
        self.assertIn("acceptance/status-receipts/windows-static-precheck-validation.json", by_stage["validation"]["evidence"])

    def test_freshness_dependencies_include_declared_evidence(self) -> None:
        toolkit = renderer.load_yaml(ROOT / "TOOLKIT_MANIFEST.yaml")
        entries = {entry["id"]: entry for entry in toolkit["capabilities"]}
        windows_paths = {path.relative_to(ROOT).as_posix() for path in renderer.capability_source_paths(entries["windows-static-precheck"])}
        self.assertIn("tools/windows_precheck_mvp.py", windows_paths)
        self.assertIn("acceptance/status-receipts/windows-static-precheck-validation.json", windows_paths)

    def test_static_first_view_has_every_capability(self) -> None:
        static_body = self.html.split('<script id="capabilityData"', 1)[0]
        for item in self.snapshot["capabilities"]:
            self.assertIn(f'data-id="{item["id"]}"', static_body)

    def test_has_no_remote_runtime_dependency(self) -> None:
        self.assertIsNone(re.search(r'<(?:script|link)[^>]+(?:src|href)=["\']https?://', self.html, re.IGNORECASE))

    def test_visible_ui_has_no_fake_progress_geometry(self) -> None:
        static_body = self.html.split('<script id="capabilityData"', 1)[0]
        self.assertNotIn('class="progress"', static_body)
        self.assertNotIn('class="point partial"', static_body)
        self.assertIn("部分状态不换算成虚假的完成百分比", static_body)
        renderer_source = RENDERER_PATH.read_text(encoding="utf-8")
        self.assertNotIn('stage["score"]', renderer_source)
        self.assertNotIn("五轴得分", renderer_source)

    def test_summary_uses_honest_maturity_categories(self) -> None:
        static_body = self.html.split('<script id="capabilityData"', 1)[0]
        for expected in ("已激活", "部分实现", "仅完成设计", "受阻", "状态未知"):
            self.assertIn(expected, static_body)
        self.assertNotIn("已知项均值", static_body)

    def test_navigation_separates_three_surfaces(self) -> None:
        for destination in ("workset-planner.html", "run-console.html", "capability-progress.html"):
            self.assertIn(destination, self.html)

    def test_detail_has_real_closed_state(self) -> None:
        self.assertIn(".maturity-detail.closed { display: none; }", (ROOT / "dashboard/assets/console.css").read_text(encoding="utf-8"))
        self.assertIn('detail.classList.add("closed")', (ROOT / "dashboard/assets/maturity.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
