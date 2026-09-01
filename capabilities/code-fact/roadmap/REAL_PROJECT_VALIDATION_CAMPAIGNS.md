# Real-project validation campaigns

Document type: **PLAN**  
Specification status: **DESIGNED**  
Execution status: **NOT_RUN**

This file carries forward the “next step” Code Fact document as a set of explicit validation campaigns. Nothing here asserts that company integration, provider deployment, indexing, or benchmarking has already happened.

## Campaign overview

| ID | Campaign | Goal | Status |
|---|---|---|---|
| CF-C01 | Company workspace intake | Prove reproducible multi-repository snapshot intake using company Python scripts | `NOT_RUN` |
| CF-C02 | Real multi-repository cases | Test fact queries on actual producer/consumer and dependency paths | `NOT_RUN` |
| CF-C03 | clangd context fidelity | Establish what clangd can and cannot prove for actual targets | `NOT_RUN` |
| CF-C04 | Provider benchmark | Compare Native, semantic, and indexed cohorts with adjudication | `NOT_RUN` |
| CF-C05 | Provider off/swap/remove | Prove replaceability and fail-closed behavior | `NOT_RUN` |
| CF-C06 | Thin dispatcher decision | Decide whether measured complexity justifies routing automation | `NOT_RUN` |
| CF-C07 | Joern/Kythe trigger review | Admit a watchlist provider only for a demonstrated unmet query family | `NOT_RUN` |

## CF-C01 — Company workspace intake

### Purpose

Adapt Code Fact to the company's Python-scripted pull/workspace model without embedding those scripts in the evidence kernel.

### Designed steps

1. Inventory script names, versions/digests, configuration, authentication boundary, and read/write effects.
2. Create a task workspace through the adapter using a non-destructive intake action.
3. Record all repository identities, branches/revisions, local changes, submodules, LFS state, sparse paths, and generated inputs.
4. Compute separate content and provenance IDs.
5. Verify that repeated intake of the same declared source produces an equivalent snapshot or an explicit drift receipt.
6. Confirm submit commands are unavailable during evidence-only execution.

### Exit evidence

- adapter invocation receipt;
- task workspace manifest;
- revision freeze manifest;
- content/provenance IDs;
- dirty-state and missing-repository checks;
- cleanup/recovery instructions.

## CF-C02 — Real multi-repository cases

### Purpose

Validate Code Fact on actual company questions rather than toy repositories.

### Minimum case families

- C++ producer to another repository's consumer;
- include and transitive dependency chain;
- build target membership;
- generated header/source dependency;
- changed signal field through a shared data-buffer mechanism;
- collaborator-owned consumer absent from the current snapshot;
- negative query whose absence can be proven;
- incomplete snapshot that must produce an inconclusive result.

Each case needs an independent expected answer and authority source. Pending collaborator work is recorded as an external dependency, not guessed.

## CF-C03 — clangd context fidelity

Follow [`../providers/clangd.md`](../providers/clangd.md). Test exact and intentionally wrong compilation databases, targets, query-driver settings, generated headers, include paths, and external caches. Compare diagnostics and symbol results with the actual product build evidence supplied by the user or controlled environment.

Success means the provider's ceilings are measured and configuration gaps fail visibly. It does not mean clangd becomes equivalent to the product compiler.

## CF-C04 — Provider benchmark

Execute [`../benchmark/BENCHMARK_AND_ADJUDICATION.md`](../benchmark/BENCHMARK_AND_ADJUDICATION.md) on the frozen real-project cases. Start with Native, then evaluate one candidate at a time. Keep setup/index cost separate from query cost.

No “30–40% improvement” or similar claim may be carried forward without a campaign report and raw evidence.

## CF-C05 — Provider off, swap, and removal

### Off test

Disable an optional provider. Native Search, ripgrep, and Git must remain available, and the result ceiling must narrow explicitly.

### Swap test

Replace one graph/index provider with another through the same capability contract. Profiles must receive the same normalized schema and must not depend on provider-native fields.

### Removal test

Retire/unbind and remove a deployment/index. Verify:

- no hidden runtime dependency remains;
- historical evidence bundles still resolve to retained receipts;
- provider caches are identified and removed safely;
- profile binding is revoked rather than silently rerouted;
- fallback/native selection reason is recorded.

## CF-C06 — Thin dispatcher decision

Do not build a router merely because multiple providers are listed. First measure:

- repeated manual selection burden;
- query/provider matching stability;
- contract normalization cost;
- routing failure modes;
- expected maintenance savings.

If justified, the dispatcher remains thin: contract validation, eligibility matching, invocation, normalization, and receipts only. Review sequencing, source-control actions, provider installation, and final verdicts remain outside it.

## CF-C07 — Joern/Kythe trigger review

These providers stay on a watchlist. A campaign begins only when a real, prioritized query family remains unsupported after validating current providers and the expected benefit exceeds supply-chain, indexing, and maintenance cost.

The decision record must include the unmet queries, alternatives considered, expected evidence ceiling, resource budget, and removal plan.

## Campaign governance

Every campaign must create a new run directory with immutable inputs and receipts. A failed or blocked campaign is still a valid result. It must not be rewritten as success, deleted to make the report cleaner, or generalized beyond its exact corpus/build profile.

Only verified outputs may update provider lifecycle or profile-binding records. This roadmap itself never changes a provider state.
