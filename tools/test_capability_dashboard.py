#!/usr/bin/env python3
"""Focused, dependency-free tests for the capability progress dashboard."""

from __future__ import annotations

import importlib.util
import copy
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


def stages(scores: list[int | None]) -> list[dict]:
    return [
        {"key": definition["key"], "label": definition["label"], "weight": definition["weight"], "score": score}
        for definition, score in zip(renderer.STAGES, scores, strict=True)
    ]


class ProgressSemanticsTests(unittest.TestCase):
    def test_only_all_axes_complete_is_green(self) -> None:
        self.assertEqual(renderer.classify_progress(stages([100, 100, 100, 100, 100]))[1:4], ("complete", "已完成", "100%"))
        self.assertEqual(renderer.classify_progress(stages([100, 100, 100, 100, 50]))[1], "in-progress")

    def test_only_all_axes_zero_is_red(self) -> None:
        self.assertEqual(renderer.classify_progress(stages([0, 0, 0, 0, 0]))[1:4], ("not-started", "未开始", "0%"))
        self.assertEqual(renderer.classify_progress(stages([0, 0, None, 0, 0]))[1], "unknown")

    def test_unknown_is_gray_lower_bound(self) -> None:
        score, category, _, display, unknown = renderer.classify_progress(stages([100, 50, None, 0, 0]))
        self.assertEqual((score, category, display), (38, "unknown", "≥38%"))
        self.assertEqual(unknown, ["validation"])


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

    def test_coordinated_100_percent_tamper_is_detected(self) -> None:
        tampered = copy.deepcopy(self.snapshot)
        for capability in tampered["capabilities"]:
            capability["score"] = 100
            capability["score_display"] = "100%"
            capability["category"] = "complete"
            capability["status_label"] = "已完成"
            capability["unknown_stages"] = []
            for stage in capability["stages"]:
                stage["score"] = 100
                stage["status"] = "FORGED"
        tampered["summary"] = {
            "complete": len(tampered["capabilities"]),
            "in_progress": 0,
            "not_started": 0,
            "unknown": 0,
            "total": len(tampered["capabilities"]),
            "average": 100,
        }
        self.assertEqual(tampered["source_digest"], self.snapshot["source_digest"])
        self.assertFalse(renderer.snapshots_match(tampered, self.snapshot))

    def test_promoted_status_displays_declared_evidence_not_self_declaration(self) -> None:
        windows = next(item for item in self.snapshot["capabilities"] if item["id"] == "windows-static-precheck")
        by_stage = {stage["key"]: stage for stage in windows["stages"]}
        self.assertIn("tools/windows_precheck_mvp.py", by_stage["implementation"]["evidence"])
        self.assertIn("acceptance/status-receipts/windows-static-precheck-validation.json", by_stage["validation"]["evidence"])
        self.assertNotIn(
            "capabilities/windows-static-precheck/CAPABILITY.yaml#status_dimensions.implementation_status",
            by_stage["implementation"]["evidence"],
        )

    def test_freshness_dependencies_include_custom_spec_and_declared_status_evidence(self) -> None:
        toolkit = renderer.load_yaml(ROOT / "TOOLKIT_MANIFEST.yaml")
        entries = {entry["id"]: entry for entry in toolkit["capabilities"]}
        windows_paths = {path.relative_to(ROOT).as_posix() for path in renderer.capability_source_paths(entries["windows-static-precheck"])}
        code_fact_paths = {path.relative_to(ROOT).as_posix() for path in renderer.capability_source_paths(entries["code-fact"])}
        self.assertIn("tools/windows_precheck_mvp.py", windows_paths)
        self.assertIn("acceptance/status-receipts/windows-static-precheck-validation.json", windows_paths)
        self.assertIn("capabilities/code-fact/README.md", code_fact_paths)

    def test_static_first_view_has_every_capability(self) -> None:
        static_body = self.html.split('<script id="capabilityData"', 1)[0]
        for item in self.snapshot["capabilities"]:
            self.assertIn(f'data-id="{item["id"]}"', static_body)

    def test_single_file_has_no_remote_runtime_dependency(self) -> None:
        self.assertIsNone(re.search(r'<(?:script|link)[^>]+(?:src|href)=["\']https?://', self.html, re.IGNORECASE))

    def test_card_progress_track_has_block_geometry(self) -> None:
        self.assertIn(".card-name { display:block;", self.html)
        self.assertIn(".score { display:block;", self.html)
        self.assertIn(".progress { display:block; width:100%; height:6px;", self.html)

    def test_summary_headlines_show_counts_not_thresholds(self) -> None:
        static_body = self.html.split('<script id="capabilityData"', 1)[0]
        self.assertIn('id="completeCount"', static_body)
        self.assertIn("项已完成", static_body)
        self.assertNotIn('<span class="summary-value">100%</span><span class="summary-label">已完成</span>', static_body)

    def test_desktop_drawer_has_real_closed_state(self) -> None:
        self.assertIn(".main.drawer-closed { grid-template-columns:minmax(0,1fr); }", self.html)
        self.assertIn(".drawer.closed { display:none; }", self.html)
        self.assertIn("$('#detailDrawer').classList.add('closed');", self.html)
        self.assertIn("$('#mainLayout').classList.add('drawer-closed');", self.html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
