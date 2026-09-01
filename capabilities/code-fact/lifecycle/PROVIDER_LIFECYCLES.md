# Provider lifecycles

Status: **DESIGNED**  
Execution status: **NOT_RUN**

A single `ACTIVE/DEPRECATED/REMOVED` label hides several independent facts. Code Fact therefore tracks three lifecycles. A provider may be healthy in one and unusable in another.

## 1. Artifact lifecycle

This lifecycle concerns the executable/package/container and locked dependencies.

| State | Meaning | Minimum receipt to advance |
|---|---|---|
| `DESIGNED` | Provider integration is specified only | Design file |
| `SOURCED` | Canonical source and pinned revision are identified | Source URL/ID, revision, license and integrity metadata |
| `BUILT` | Reproducible internal build or fixed artifact exists | Build recipe, dependency lock, artifact digest |
| `VERIFIED` | Artifact passes security, smoke, compatibility, and deterministic-output checks | Verification report and signatures/digests |
| `QUARANTINED` | Artifact may not be selected pending investigation | Quarantine reason and affected versions |
| `RETIRED` | Artifact is retained for audit but no longer eligible | Retirement decision and replacement/migration note |

There is no example `VERIFIED` artifact in this design package. Current entries remain `DESIGNED/NOT_RUN` until receipts exist.

## 2. Deployment and index lifecycle

This lifecycle concerns a concrete environment and, when applicable, the corpus-derived index.

| State | Meaning | Required evidence |
|---|---|---|
| `NOT_DEPLOYED` | No deployment fact has been established | None |
| `DEPLOYED_UNVALIDATED` | Artifact is installed but not proven usable for the target context | Deployment identity and config receipt |
| `INDEXING` | A corpus/index build is in progress | Snapshot, profile, progress and error receipts |
| `VALIDATED` | Deployment/index passes the declared validation suite for a fixed corpus/build profile | Coverage, freshness, correctness, and performance receipts |
| `STALE` | Deployment or index no longer matches its bound snapshot/profile | Drift receipt |
| `FAILED` | Health, query, or index validation failed | Failure receipt and diagnostics |
| `REMOVED` | Deployment/index was removed; audit metadata remains | Removal receipt |

`VALIDATED` is scoped. The scope includes provider version, environment, corpus content ID, provenance ID, build profile, generated inputs, extractor/config version, index digest, and validation suite version. It is not a global badge.

## 3. Profile-binding lifecycle

This lifecycle concerns whether a caller/profile may select a validated deployment/index.

| State | Meaning |
|---|---|
| `UNBOUND` | No profile selection rule exists |
| `CANDIDATE` | Evidence is being evaluated for a named profile and query family |
| `APPROVED` | The named profile may select it within recorded ceilings |
| `SUSPENDED` | Selection is temporarily disabled while evidence is reviewed |
| `REVOKED` | The binding is withdrawn; historical receipts remain |

Approval is specific to a profile version, query family, corpus/build profile, evidence ceiling, and validity window. Artifact verification or deployment validation does not automatically approve a binding.

## 4. Why the lifecycles must remain separate

Examples:

- A verified artifact can be `NOT_DEPLOYED`.
- A deployment can be healthy while its index is `STALE`.
- A validated index can remain `UNBOUND` for a strict review profile.
- A profile binding can be `SUSPENDED` while the artifact itself remains valid for other contexts.
- Retirement must not erase prior evidence bundles or audit receipts.

## 5. Controlled third-party supply chain

The designed chain is:

1. resolve canonical source and license;
2. pin an immutable revision and all transitive dependencies;
3. resolve the approved artifact source through the outer runtime boundary and record its receipt;
4. build in a controlled environment or accept a fixed, integrity-checked artifact;
5. scan and verify the artifact;
6. deploy through an environment-approved, integrity-receipted channel;
7. construct indexes from frozen snapshots;
8. validate correctness, coverage, freshness, security, and performance;
9. bind explicitly to profiles.

Editable package installs, unpinned branches, ambient user configuration, and “latest” downloads cannot advance the artifact lifecycle to `VERIFIED`.

## 6. Revalidation triggers

Any of the following requires scoped revalidation:

- provider or dependency version change;
- toolchain, OS, Python, Java, compiler, or container base change;
- extractor, parser, query-driver, or configuration change;
- repository set, branch/revision, submodule, LFS, or generated input change;
- compilation database, target, macro, include path, or sysroot change;
- index schema or normalization change;
- profile evidence policy change;
- a correctness incident or user-provided contradictory evidence.

## 7. Source-change invalidation and incremental refresh

A source or build-context change is a lifecycle event, not merely a reason to repeat the same query. As soon as the workspace `content_id` changes, evidence and indexes bound to the prior `content_id` are ineligible for conclusions about the new snapshot.

For a bound provider that declares incremental indexing/refresh support, the required transition is:

1. mark affected prior evidence stale/superseded while preserving audit history;
2. derive the changed-file set and affected dependency closure;
3. execute the provider-neutral incremental-refresh operation;
4. verify the resulting index is bound to the new `content_id`, build profile, generated inputs, and provider configuration;
5. persist a refresh receipt;
6. only then run new queries and emit replacement evidence bundles.

The refresh receipt must record at least:

- provider, artifact, deployment, and old/new index identities;
- old and new `content_id` plus relevant provenance change;
- changed files and the dependency-closure derivation method;
- repositories, targets, generated inputs, and configuration included/excluded;
- refreshed, skipped, and failed units;
- start/end time, exit/error channels, and health checks;
- post-refresh binding verification result;
- old evidence bundle IDs superseded by the refresh;
- new query/evidence bundle IDs, when produced.

If incremental refresh is unsupported or fails, the deployment/index lifecycle becomes `STALE` for the new snapshot. The caller may use first-class Native providers within their declared ceilings or request an approved full index rebuild. It may not use the old index for the new snapshot. A successful command without new-`content_id` binding evidence is still `STALE`.

The lifecycle rule is provider-neutral. Provider-specific refresh commands belong only in provider adapters and may not be embedded in Recovery Review or another Profile.

## 8. Removal behavior

Removal is not silent deletion. The capability must preserve:

- artifact and deployment identities;
- last validated scope;
- historical profile bindings;
- evidence bundle references;
- reason, approver, timestamp, and replacement decision;
- reproducibility limitations after removal.

`RETIRED` and `UNBOUND/REVOKED` are preferable to a vague global `REMOVED` label because they identify what ceased to be usable.
