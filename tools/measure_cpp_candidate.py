#!/usr/bin/env python3
"""Measure a tracked C/C++ repository for evidence-based acceptance-target selection."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}
HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx", ".inc", ".inl"}
TEST_PARTS = {"test", "tests", "testing", "unittest", "unittests"}
NON_PRODUCT_PARTS = TEST_PARTS | {
    "benchmark",
    "benchmarks",
    "example",
    "examples",
    "sample",
    "samples",
    "third_party",
    "third-party",
    "external",
    "extern",
    "vendor",
    ".conan",
    "cmake",
    "fuzz",
    "fuzzing",
    "tool",
    "tools",
    "util",
    "utils",
}
LICENSE_NAMES = {"license", "license.md", "license.txt", "copying", "copying.txt"}
TARGET_PATTERN = re.compile(r"\b(add_library|add_executable)\s*\(\s*([^\s\)]+)", re.IGNORECASE)
PACKAGE_PATTERN = re.compile(r"\bfind_package\s*\(\s*([^\s\)]+)", re.IGNORECASE)
FETCH_PATTERN = re.compile(r"\bFetchContent_Declare\s*\(\s*([^\s\)]+)", re.IGNORECASE)
TEST_PATTERN = re.compile(r"\b(add_test|catch_discover_tests|gtest_discover_tests)\s*\(", re.IGNORECASE)


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def run_git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo.as_posix()}", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.decode("utf-8", errors="replace").strip()


def tracked_paths(repo: Path) -> list[str]:
    output = subprocess.run(
        ["git", "-c", f"safe.directory={repo.as_posix()}", "ls-files", "-z"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    return sorted(item for item in output.decode("utf-8", errors="surrogateescape").split("\0") if item)


def require_clean_worktree(repo: Path) -> None:
    status = run_git(repo, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        entry_count = len(status.splitlines())
        raise ValueError(
            "repository worktree must be clean before measurement; "
            f"found {entry_count} tracked, staged, submodule, or untracked status entries"
        )


def path_parts(path: str) -> tuple[str, ...]:
    return tuple(part.lower() for part in PurePosixPath(path).parts)


def is_test_path(path: str) -> bool:
    return bool(set(path_parts(path)) & TEST_PARTS)


def is_product_path(path: str) -> bool:
    return not bool(set(path_parts(path)) & NON_PRODUCT_PARTS)


def line_counts(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    return len(lines), sum(1 for line in lines if line.strip())


def code_root(path: str) -> str:
    parts = PurePosixPath(path).parts
    if len(parts) >= 3 and parts[0].lower() in {"src", "source", "include", "lib", "libs"}:
        return f"{parts[0]}/{parts[1]}"
    return parts[0]


def analyze_files(repo: Path, paths: Iterable[str]) -> dict[str, Any]:
    tracked = sorted(paths)
    cpp_paths = [
        path for path in tracked
        if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES | HEADER_SUFFIXES
    ]
    source_paths = [path for path in cpp_paths if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES]
    header_paths = [path for path in cpp_paths if PurePosixPath(path).suffix.lower() in HEADER_SUFFIXES]
    product_paths = [path for path in cpp_paths if is_product_path(path)]
    product_sources = [path for path in product_paths if PurePosixPath(path).suffix.lower() in SOURCE_SUFFIXES]
    product_headers = [path for path in product_paths if PurePosixPath(path).suffix.lower() in HEADER_SUFFIXES]
    test_paths = [path for path in cpp_paths if is_test_path(path)]

    total_physical = total_nonblank = product_physical = product_nonblank = 0
    for relative in cpp_paths:
        physical, nonblank = line_counts(repo / relative)
        total_physical += physical
        total_nonblank += nonblank
        if relative in product_paths:
            product_physical += physical
            product_nonblank += nonblank

    cmake_paths = [
        path for path in tracked
        if PurePosixPath(path).name == "CMakeLists.txt" or PurePosixPath(path).suffix.lower() == ".cmake"
    ]
    targets: set[str] = set()
    packages: set[str] = set()
    fetch_dependencies: set[str] = set()
    test_registrations = 0
    for relative in cmake_paths:
        text = (repo / relative).read_text(encoding="utf-8", errors="replace")
        targets.update(match.group(2) for match in TARGET_PATTERN.finditer(text))
        packages.update(match.group(1) for match in PACKAGE_PATTERN.finditer(text))
        fetch_dependencies.update(match.group(1) for match in FETCH_PATTERN.finditer(text))
        test_registrations += len(TEST_PATTERN.findall(text))

    license_files = []
    for relative in tracked:
        if PurePosixPath(relative).name.lower() in LICENSE_NAMES:
            data = (repo / relative).read_bytes()
            license_files.append({"path": relative, "content_id": digest_bytes(data)})

    code_roots = sorted({code_root(path) for path in product_paths})
    return {
        "measurement_definition": {
            "physical_loc": "all physical lines in tracked C/C++ source and header files",
            "nonblank_loc": "non-empty physical lines; comments are retained",
            "product_scope": "tracked C/C++ files excluding test, benchmark, example, external and vendor path components",
            "cmake_target_count": "unique literal first arguments to add_library/add_executable; generated targets may be undercounted",
            "code_roots": "top-level code directories, or the first child under src/source/include/lib/libs",
        },
        "tracked_file_count": len(tracked),
        "cpp": {
            "all_file_count": len(cpp_paths),
            "source_file_count": len(source_paths),
            "header_file_count": len(header_paths),
            "compilation_unit_count": len(source_paths),
            "physical_loc": total_physical,
            "nonblank_loc": total_nonblank,
            "product_file_count": len(product_paths),
            "product_source_file_count": len(product_sources),
            "product_header_file_count": len(product_headers),
            "product_compilation_unit_count": len(product_sources),
            "product_physical_loc": product_physical,
            "product_nonblank_loc": product_nonblank,
            "test_file_count": len(test_paths),
            "code_root_count": len(code_roots),
            "code_roots": code_roots,
        },
        "cmake": {
            "file_count": len(cmake_paths),
            "module_file_count": sum(1 for path in cmake_paths if path.lower().endswith(".cmake")),
            "declared_target_count": len(targets),
            "declared_targets": sorted(targets),
            "test_registration_call_count": test_registrations,
        },
        "dependencies": {
            "find_package": sorted(packages),
            "fetch_content": sorted(fetch_dependencies),
            "gitmodules_present": ".gitmodules" in tracked,
        },
        "license_files": license_files,
    }


def measure_repository(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    if not (repo / ".git").exists():
        raise ValueError(f"not a Git repository: {repo}")
    require_clean_worktree(repo)
    measured_commit = run_git(repo, "rev-parse", "HEAD")
    result = {
        "repository": {
            "path": str(repo),
            "origin": run_git(repo, "remote", "get-url", "origin"),
            "branch": run_git(repo, "branch", "--show-current"),
            "commit": measured_commit,
            "commit_time": run_git(repo, "show", "-s", "--format=%cI", "HEAD"),
            "shallow": run_git(repo, "rev-parse", "--is-shallow-repository") == "true",
            "worktree_state": "CLEAN",
        }
    }
    result.update(analyze_files(repo, tracked_paths(repo)))
    if run_git(repo, "rev-parse", "HEAD") != measured_commit:
        raise ValueError("repository HEAD changed during measurement")
    require_clean_worktree(repo)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    try:
        result = measure_repository(args.repo)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
