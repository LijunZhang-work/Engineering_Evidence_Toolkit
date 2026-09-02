from __future__ import annotations

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

try:
    from tools.profile_runner_mvp import AUTHORIZATION_PATH, PLAN_PATH, ROOT, run_profile
except ModuleNotFoundError:
    from profile_runner_mvp import AUTHORIZATION_PATH, PLAN_PATH, ROOT, run_profile


FIXTURE = ROOT / "acceptance/fixtures/windows-mvp/missing-paren"
CLEAN = ROOT / "acceptance/fixtures/windows-mvp/clean"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gate(record: dict, phase: str, gate_id: str) -> str:
    return record[phase]["gates"][gate_id]


class ProfileRunnerMvpTests(unittest.TestCase):
    def test_isolated_fixture_edit_runs_bootstrap_mutation_revalidation_and_reports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-runner-mvp-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            output = root / "run"
            shutil.copytree(FIXTURE, workspace)
            record = run_profile(
                workspace,
                workspace / "target.yaml",
                output,
                acceptance_fixture_mutation=True,
                authorization_path=AUTHORIZATION_PATH,
                edit_plan_path=PLAN_PATH,
            )
            self.assertEqual(record["runtime_states"], ["NOT_STARTED", "BOOTSTRAPPING", "READY", "RUNNING", "COMPLETED"])
            self.assertEqual(gate(record, "before", "F1_STRUCTURAL_CHANGE_SAFETY"), "FAIL")
            self.assertEqual(gate(record, "after", "F1_STRUCTURAL_CHANGE_SAFETY"), "PASS")
            self.assertEqual(record["mutation"]["status"], "APPLIED")
            self.assertEqual(record["post_mutation_validation"]["status"], "PASS")
            self.assertEqual(record["final_verdict"], "NO_VERDICT")
            self.assertEqual(sha(workspace / "source.cpp"), "9190f46f9771823699c26c0affece3191788f5231c984eaf27f8f456b3b518fd")
            self.assertTrue((output / "mutation.diff").is_file())
            for phase in ("before", "after"):
                for path in record[phase]["reports"].values():
                    self.assertTrue(Path(path).is_file())

    def test_no_edit_flow_bootstraps_without_mutating_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-runner-mvp-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            shutil.copytree(CLEAN, workspace)
            before = sha(workspace / "source.cpp")
            record = run_profile(workspace, workspace / "target.yaml", root / "run")
            self.assertEqual(record["mutation"]["status"], "NOT_APPLICABLE")
            self.assertEqual(before, sha(workspace / "source.cpp"))

    def test_repository_workspace_cannot_be_mutated_by_fixture_runner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-runner-mvp-") as temporary:
            with self.assertRaisesRegex(ValueError, "temporary-directory copy"):
                run_profile(
                    FIXTURE,
                    FIXTURE / "target.yaml",
                    Path(temporary) / "run",
                    acceptance_fixture_mutation=True,
                    authorization_path=AUTHORIZATION_PATH,
                    edit_plan_path=PLAN_PATH,
                )

    def test_edit_plan_without_explicit_fixture_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-runner-mvp-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            shutil.copytree(FIXTURE, workspace)
            with self.assertRaisesRegex(ValueError, "explicit acceptance_fixture_mutation"):
                run_profile(
                    workspace,
                    workspace / "target.yaml",
                    root / "run",
                    authorization_path=AUTHORIZATION_PATH,
                    edit_plan_path=PLAN_PATH,
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
