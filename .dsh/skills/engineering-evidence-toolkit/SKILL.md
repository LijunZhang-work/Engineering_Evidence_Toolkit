---
name: engineering-evidence-toolkit
description: Route Engineering Evidence Toolkit checks through local machine validators with explicit Quick, Balanced, Strict, or Custom evidence ceilings.
whenToUse: Use for repository evidence collection, safe-edit verification, Windows C/C++ precheck, RunBundle validation, or Toolkit/Harness compatibility checks in this project.
disable-model-invocation: false
user-invocable: true
---

# Engineering Evidence Toolkit

EET_GLM_ROLE=FINAL_COMPATIBILITY_OBSERVER
EET_GLM_MUST_RUN_AFTER=TOOLKIT_MULTI_ANGLE_REVIEW
EET_GLM_REVIEW_AUTHORITY=NONE
EET_GLM_CLAIM_AUTHORITY=NONE
EET_GLM_GATE_AUTHORITY=NONE
EET_GLM_QUALIFICATION_AUTHORITY=NONE
EET_GLM_LIFECYCLE_PROMOTION_AUTHORITY=NONE

This is a thin Harness entrypoint. The model explains and routes checks; local artifacts and validators decide whether evidence is structurally and semantically valid. Never turn model confidence into a Claim, Gate, qualification, or final Verdict.

## Establish the run boundary

1. Read `CURRENT_STATE.yaml`, `00_START_HERE.md`, and the selected Capability's `CAPABILITY.yaml` and `SPEC.md`.
2. Use a standalone Capability unless the user explicitly requests a Profile. A Profile that is not implemented, validated, qualified, and active cannot issue `ACCEPT`.
3. Select and freeze one Run Policy. If the user does not choose, use `balanced`.
4. Record the workspace, target, revision, dirty/untracked state, permissions, output directory, time budget, and unresolved external errors. Never invent missing values.

## Policy choices

- `quick`: target-scoped discovery, fastest qualified Provider, no required corroboration or active Canary, and `NO_VERDICT` only.
- `balanced`: risk-adaptive evidence with fresh workspace binding and fallback; may report evidence and risk but cannot issue `ACCEPT`.
- `strict`: complete named scope, independent corroboration, qualified Providers, fresh artifacts, and an end-to-end active negative Canary. Missing any item is `INCOMPLETE` or `REJECT`, never a narrative override.
- `custom`: pass a complete policy with `--policy-file`; it must bind a canonical base preset and match the machine-derived conclusion ceiling. Any weakened evidence axis weakens authority.

The Provider sequence is a query-family preference, not a mandatory ritual. For example, `zg`, CodeGraph, and `rg` are not all run for every request. Stop early when the selected policy permits it; demand independent execution lineages when the Claim risk requires it.

## Local Windows commands

Run from the Toolkit repository root with the approved `.venv`; do not install dependencies automatically:

```powershell
.\.venv\Scripts\python.exe tools\validate_toolkit.py
.\.venv\Scripts\python.exe -m unittest discover -s tools -p 'test_*.py' -v
.\.venv\Scripts\python.exe tools\validate_run_bundle.py <run-bundle.yaml> `
  --authority-registry <trusted-authority-registry.yaml> `
  --authority-registry-content-id <externally-pinned-sha256>
```

The expected Registry digest must come from protected runtime/CI configuration or
an independently verified signature. Never derive it from the Bundle or Registry
inside the same invocation; those two objects cannot authenticate each other.

Executable verification requires a split permission boundary: keep repository source
read-only, but allow the Python child process to write to an OS temporary directory and
the declared external run-artifact directory. A fully read-only preset is suitable only
for inspection. If it blocks `tempfile`, report `ENVIRONMENT_BLOCKED`; do not translate
Doctor or unittest exit codes from that preset into a Toolkit failure.

For the bounded C/C++ precheck:

```powershell
.\.venv\Scripts\python.exe tools\windows_precheck_mvp.py `
  --workspace <cpp-workspace> `
  --target-manifest <target.yaml> `
  --policy balanced `
  --output <external-run-directory>
```

For a Custom policy, replace `--policy balanced` with `--policy-file <custom-policy.yaml>`. The CLI validates its schema, canonical base digest and derived authority before reading the workspace.

An optional `--user-error <log.txt>` must also declare `--external-error-source UNVERIFIED_EXTERNAL`; only repository acceptance tests may use `ACCEPTANCE_FIXTURE`. The CLI deliberately rejects `USER_PROVIDED`, because a caller cannot self-assert trusted provenance. The error remains unresolved until a same-snapshot applicability Claim proves otherwise. A clean MVP result is only structural and declared-target metadata evidence; it is not a product build, linker, DT, runtime, or company-environment pass.

## Non-negotiable evidence behavior

- Preserve raw errors, conflicts, limitations, timeouts, and missing inputs.
- Do not interpret no finding as proof when coverage, qualification, freshness, or the active Canary is absent.
- Do not dismiss user-supplied failures because a different local environment is green.
- Do not modify business source without an explicit structured authorization bounded by repository, paths, deletion/file budgets, baseline, and expiry.
- After an authorized edit, verify the diff, deleted content, target membership, refreshed snapshot, invalidated old evidence, and affected checks.
- Keep secrets in the Harness/provider UI. Never print, store, or commit API keys or session tokens.

## Output contract

Return professional, plain-language, and machine-readable views from one fact set. Each view must preserve the same fact digest, finding IDs, Gate states, final Verdict, external errors, unresolved items, and limitations. File links must resolve inside the selected workspace or declared external run directory.

When GLM is used through DeepSeek Harness, treat it only as a final independent compatibility observer: it may exercise this entrypoint, local commands, workspace/file links, and rendered views after the Toolkit's own multi-angle review has completed. Its prose cannot replace the machine gates or promote any lifecycle status.
