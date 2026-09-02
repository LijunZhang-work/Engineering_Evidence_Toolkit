#!/usr/bin/env python3
"""Capture a bounded, read-only Git worktree observation outside the source repository."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_digest(value: Any) -> str:
    return digest_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))


def git(repo: Path, *args: str, check: bool = True) -> bytes:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo.as_posix()}", *args],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )
    return completed.stdout


def baseline_bytes(repo: Path, relative: str) -> bytes | None:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo.as_posix()}", "show", f"HEAD:{relative}"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout if completed.returncode == 0 else None


def status_entries(repo: Path) -> list[dict[str, str]]:
    raw = git(repo, "status", "--porcelain=v1", "-z").decode("utf-8", errors="surrogateescape")
    entries: list[dict[str, str]] = []
    records = [record for record in raw.split("\0") if record]
    index = 0
    while index < len(records):
        record = records[index]
        status = record[:2]
        path = record[3:]
        entry = {"status": status, "path": path.replace("\\", "/")}
        if "R" in status or "C" in status:
            index += 1
            if index < len(records):
                entry["source_path"] = records[index].replace("\\", "/")
        entries.append(entry)
        index += 1
    return entries


def numstat(repo: Path) -> dict[str, tuple[int | None, int | None]]:
    result: dict[str, tuple[int | None, int | None]] = {}
    text = git(repo, "diff", "--numstat", "HEAD").decode("utf-8", errors="replace")
    for line in text.splitlines():
        added, deleted, relative = line.split("\t", 2)
        result[relative.replace("\\", "/")] = (
            None if added == "-" else int(added),
            None if deleted == "-" else int(deleted),
        )
    return result


def capture(repo: Path, output: Path, phase: str) -> dict[str, Any]:
    repo = repo.resolve()
    output = output.resolve()
    if not (repo / ".git").exists() and not (repo / ".git").is_file():
        raise ValueError(f"not a Git worktree: {repo}")
    try:
        output.relative_to(repo)
    except ValueError:
        pass
    else:
        raise ValueError("observation output must be outside the source worktree")

    entries = status_entries(repo)
    stats = numstat(repo)
    paths: list[dict[str, Any]] = []
    for entry in entries:
        relative = entry["path"]
        current_path = repo / relative
        baseline = baseline_bytes(repo, relative)
        current = current_path.read_bytes() if current_path.is_file() else None
        added, deleted = stats.get(relative, (None, None))
        paths.append(
            {
                **entry,
                "baseline_content_id": digest_bytes(baseline) if baseline is not None else None,
                "current_content_id": digest_bytes(current) if current is not None else None,
                "size_bytes": len(current) if current is not None else None,
                "added_lines": added,
                "deleted_lines": deleted,
            }
        )
    patch = git(repo, "diff", "--binary", "--no-ext-diff", "HEAD")
    observation: dict[str, Any] = {
        "schema_version": "1.0.0",
        "kind": "GitWorktreeObservation",
        "phase": phase,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "repository": str(repo),
        "head_commit": git(repo, "rev-parse", "HEAD").decode().strip(),
        "branch": git(repo, "branch", "--show-current").decode().strip() or None,
        "detached": not bool(git(repo, "branch", "--show-current").decode().strip()),
        "changed_file_count": len(paths),
        "untracked_file_count": sum(1 for item in paths if item["status"] == "??"),
        "added_line_count": sum(item["added_lines"] or 0 for item in paths),
        "deleted_line_count": sum(item["deleted_lines"] or 0 for item in paths),
        "paths": sorted(paths, key=lambda item: item["path"]),
        "patch_content_id": digest_bytes(patch),
    }
    observation["observation_content_id"] = canonical_digest(observation)
    output.mkdir(parents=True, exist_ok=True)
    (output / "worktree.patch").write_bytes(patch)
    (output / "observation.json").write_text(
        json.dumps(observation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return observation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--phase", required=True, choices=["DEFECT", "FIXED", "BASELINE"])
    args = parser.parse_args()
    try:
        observation = capture(args.repo, args.output, args.phase)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(json.dumps({
        "observation_content_id": observation["observation_content_id"],
        "head_commit": observation["head_commit"],
        "changed_file_count": observation["changed_file_count"],
        "added_line_count": observation["added_line_count"],
        "deleted_line_count": observation["deleted_line_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
