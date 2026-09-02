#!/usr/bin/env python3
"""Stable CLI/import facade for the single RunBundle semantic validator."""

try:
    from tools.validate_run_bundle_semantic import (
        ROOT,
        bundle_content_id,
        canonical_content_id,
        file_content_id,
        load_document,
        main,
        report_facts,
        validate_run_bundle,
    )
except ModuleNotFoundError:  # direct execution from tools/
    from validate_run_bundle_semantic import (
        ROOT,
        bundle_content_id,
        canonical_content_id,
        file_content_id,
        load_document,
        main,
        report_facts,
        validate_run_bundle,
    )

__all__ = [
    "ROOT",
    "bundle_content_id",
    "canonical_content_id",
    "file_content_id",
    "load_document",
    "report_facts",
    "validate_run_bundle",
]


if __name__ == "__main__":
    raise SystemExit(main())
