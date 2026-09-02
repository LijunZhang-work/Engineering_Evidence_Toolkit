from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from tools.capture_git_worktree_state import capture
except ModuleNotFoundError:
    from capture_git_worktree_state import capture

from subprocess import run


class CaptureGitWorktreeStateTests(unittest.TestCase):
    def test_captures_tracked_and_untracked_bytes_and_deletion_budget(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-git-observation-") as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = root / "evidence"
            repo.mkdir()
            run(["git", "init", "-q"], cwd=repo, check=True)
            run(["git", "config", "user.email", "eet@example.invalid"], cwd=repo, check=True)
            run(["git", "config", "user.name", "EET Test"], cwd=repo, check=True)
            (repo / "tracked.cpp").write_text("line1\nline2\n", encoding="utf-8")
            run(["git", "add", "tracked.cpp"], cwd=repo, check=True)
            run(["git", "commit", "-q", "-m", "baseline"], cwd=repo, check=True)
            (repo / "tracked.cpp").write_text("line1\nchanged\n", encoding="utf-8")
            (repo / "new.hpp").write_text("#pragma once\n", encoding="utf-8")
            observation = capture(repo, output, "DEFECT")
            self.assertEqual(observation["changed_file_count"], 2)
            self.assertEqual(observation["untracked_file_count"], 1)
            self.assertEqual(observation["deleted_line_count"], 1)
            self.assertTrue(observation["patch_content_id"].startswith("sha256:"))
            self.assertTrue((output / "observation.json").is_file())
            self.assertTrue((output / "worktree.patch").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
