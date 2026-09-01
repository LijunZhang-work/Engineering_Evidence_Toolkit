# clangd provider design

Status: **DESIGNED**  
Deployment/index status: **NOT_RUN**  
Profile binding: **UNBOUND**

## Purpose

clangd can provide compiler-aware definitions, references, types, diagnostics, and include suggestions for translation units whose build context is described accurately. It is an optional Code Fact provider—not a substitute for the product compiler, an automatic cross-repository graph, or proof that the production target builds.

## Hard truth boundary

A clean clangd view means only that clangd, with the recorded configuration, could analyze the covered translation units without the reported issue. It does **not** prove:

- parity with a different product compiler or compiler version;
- parity with production target flags, sysroot, ABI, standard library, or macros;
- that every repository or generated source was indexed;
- that all conditional branches were compiled;
- link correctness, runtime behavior, DT behavior, or end-to-end product correctness;
- transitive dependency completeness outside its workspace/index scope.

When these facts are unknown, the provider response is partial or inconclusive. It must never be summarized as “no problem.”

## Required configuration

### Compilation database

The provider requires an attributable `compile_commands.json` (or a documented equivalent) for the relevant target. The receipt must record:

- how it was generated or obtained;
- which repository revisions and workspace snapshot it describes;
- target/configuration name;
- compiler path and version;
- working directories;
- include paths and order;
- macro definitions and language standard;
- sysroot, target triple, ABI-sensitive flags, and forced includes;
- whether command rewriting was applied.

Borrowing a compilation database from another target, platform, or compiler is not silent “best effort”; it changes the evidence ceiling and must be disclosed.

### `--query-driver` allowlist

If clangd must query a non-default compiler driver, the allowed paths must be narrowly enumerated. Wildcards over broad company or system directories are prohibited by design. The receipt records:

- exact allowlisted driver paths;
- resolved executable digest/version;
- why each driver is needed;
- environment variables or wrappers involved;
- whether the query succeeded.

The allowlist is a security and reproducibility boundary, not a convenience flag.

### Generated headers and sources

Generated inputs must either be materialized from the frozen snapshot or represented by integrity-checked cached artifacts. Record generator identity, inputs, output digests, and target binding. Missing generated headers must produce `BLOCKED_CONFIGURATION` or a narrowed scope—not synthetic placeholder files presented as real evidence.

### Target and external dependencies

Record target triple, sysroot, SDK, external headers, standard library, compiler resource directory, and ABI-sensitive configuration. External caches are permitted only when content-addressed, immutable for the run, integrity-checked, and linked to provenance receipts. An ambient developer cache is not evidence.

### Multi-repository workspace

All repositories relevant to a query must be enumerated in the workspace snapshot. Folder visibility alone does not establish semantic integration. Compilation commands must refer to the correct workspace paths, and external/include paths must resolve to frozen content.

## Index identity

A clangd index identity should include:

- clangd artifact ID and digest;
- configuration digest;
- content ID and provenance ID;
- compilation database digest;
- target/build profile;
- generated-input manifest digest;
- query-driver allowlist digest;
- external-cache digests;
- indexed and skipped translation units;
- index build/refresh time and errors.

The index becomes stale when any material field drifts.

## Coverage receipt

At minimum, report:

```yaml
translation_units_expected: ...
translation_units_indexed: ...
translation_units_failed: ...
files_skipped: [...]
repositories_in_scope: [...]
repositories_missing: [...]
generated_inputs_missing: [...]
targets_covered: [...]
targets_not_covered: [...]
configuration_divergences: [...]
```

Diagnostics written to standard error, log files, or protocol channels are evidence and must be captured. “The command returned results” is not a health check.

## Intended query kinds

When configured and validated, clangd may support:

- definition and declaration lookup;
- reference candidates inside covered translation units;
- type and overload information;
- local call relationships;
- include and diagnostic candidates;
- cross-file navigation within its actual index scope.

For include reachability or “was this compiled?” questions, combine clangd with build metadata and, where available, the exact product compilation command. clangd alone cannot elevate a candidate path to proof of active product compilation.

## Validation plan

Before any profile binding, validate against a real multi-repository snapshot:

1. create the workspace through the company source-control adapter;
2. preserve local modifications and record both content/provenance IDs;
3. obtain/generate target-accurate compilation commands;
4. materialize generated inputs and external caches;
5. start from a cold index and record duration/errors;
6. run an adjudicated query set with known answers;
7. modify one source/header/build input at a time and test freshness detection;
8. test missing repository, missing generated header, wrong target, wrong driver, and stale cache cases;
9. verify all failures are surfaced instead of reported as clean results;
10. repeat warm runs and compare determinism.

Until those receipts exist, this provider remains `DESIGNED / NOT_RUN / UNBOUND`.
