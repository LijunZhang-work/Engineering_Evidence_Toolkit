from __future__ import annotations

import tempfile
import subprocess
import unittest
from pathlib import Path

try:
    from tools.measure_cpp_candidate import analyze_files, measure_repository
except ModuleNotFoundError:
    from measure_cpp_candidate import analyze_files, measure_repository


class MeasureCppCandidateTests(unittest.TestCase):
    def create_git_repository(self, root: Path) -> None:
        def git(*args: str) -> None:
            subprocess.run(
                ["git", *args],
                cwd=root,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        git("init")
        git("config", "core.autocrlf", "false")
        (root / "src").mkdir()
        (root / "src/core.cpp").write_text("int core() { return 1; }\n", encoding="utf-8")
        (root / "LICENSE").write_text("permission granted\n", encoding="utf-8")
        git("add", ".")
        git(
            "-c",
            "user.name=Engineering Evidence Test",
            "-c",
            "user.email=evidence@example.invalid",
            "commit",
            "-m",
            "baseline",
        )
        git("remote", "add", "origin", "https://example.invalid/candidate.git")

    def test_counts_code_tests_cmake_and_dependencies(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-cpp-metrics-") as temporary:
            root = Path(temporary)
            files = {
                "src/core.cpp": "int core() {\n  return 1;\n}\n",
                "include/demo/core.hpp": "#pragma once\nint core();\n",
                "tests/core_test.cpp": "int test_core() { return 0; }\n",
                "cmake/Helpers.cmake": "find_package(Threads REQUIRED)\n",
                "CMakeLists.txt": (
                    "add_library(core src/core.cpp)\n"
                    "add_executable(core_tests tests/core_test.cpp)\n"
                    "FetchContent_Declare(fmt)\n"
                    "add_test(NAME core COMMAND core_tests)\n"
                ),
                "LICENSE": "permission granted\n",
            }
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            result = analyze_files(root, files)
            self.assertEqual(result["cpp"]["source_file_count"], 2)
            self.assertEqual(result["cpp"]["header_file_count"], 1)
            self.assertEqual(result["cpp"]["product_file_count"], 2)
            self.assertEqual(result["cpp"]["product_compilation_unit_count"], 1)
            self.assertEqual(result["cpp"]["product_header_file_count"], 1)
            self.assertEqual(result["cpp"]["test_file_count"], 1)
            self.assertEqual(result["cmake"]["declared_target_count"], 2)
            self.assertEqual(result["cmake"]["module_file_count"], 1)
            self.assertEqual(result["cmake"]["test_registration_call_count"], 1)
            self.assertEqual(result["dependencies"]["find_package"], ["Threads"])
            self.assertEqual(result["dependencies"]["fetch_content"], ["fmt"])
            self.assertEqual(len(result["license_files"]), 1)

    def test_clean_git_worktree_is_measured(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-cpp-clean-") as temporary:
            root = Path(temporary)
            self.create_git_repository(root)
            result = measure_repository(root)
            self.assertEqual(result["repository"]["worktree_state"], "CLEAN")
            self.assertEqual(result["cpp"]["product_compilation_unit_count"], 1)

    def test_tracked_dirty_worktree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-cpp-dirty-") as temporary:
            root = Path(temporary)
            self.create_git_repository(root)
            (root / "src/core.cpp").write_text(
                "int core() { return 2; }\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "worktree must be clean"):
                measure_repository(root)

    def test_untracked_worktree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eet-cpp-untracked-") as temporary:
            root = Path(temporary)
            self.create_git_repository(root)
            (root / "untracked.cpp").write_text("int extra;\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "worktree must be clean"):
                measure_repository(root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
