# Benchmark and adjudication protocol

Status: **DESIGNED**  
Campaign status: **NOT_RUN**

The original provider exploration proposed Native, Lite, and Full comparisons. This protocol keeps that useful idea but turns it into a reproducible experiment. It does not claim any existing measurements.

## 1. Questions the benchmark must answer

The benchmark is designed to determine:

- which query families each provider set can support;
- whether added providers improve correctness, coverage, or only convenience;
- cold and warm cost distributions;
- failure visibility and false-confidence risk;
- behavior when a provider is absent, stale, or replaced;
- whether a thin provider router is justified;
- whether any provider merits a named profile binding.

It is not a popularity contest and does not reward the largest tool set.

## 2. Comparison cohorts

Names describe experiment cohorts, not permanent product tiers.

| Cohort | Designed composition | Validation state |
|---|---|---|
| Native | native-search + ripgrep + Git | `NOT_RUN` |
| Semantic local | Native + clangd | `NOT_RUN` |
| Indexed candidate | Native + one selected graph/index provider | `NOT_RUN` |
| Combined candidate | Native + validated semantic/index candidates | `NOT_RUN` |

External candidates must be tested one at a time before combined runs, otherwise the source of gains and errors is unknowable.

## 3. Frozen benchmark package

Every campaign freezes:

- repository/workspace content ID and provenance ID;
- repository list, revisions, dirty patches, submodules, LFS, generated inputs;
- build targets and build context;
- provider artifact, deployment, index, and configuration identities;
- query set and expected-answer version;
- adjudicator guide;
- hardware/resource class and concurrency;
- network policy;
- timeout policy;
- warm/cold cache policy;
- measurement scripts and report version.

If a material item changes, the result belongs to a new campaign ID.

## 4. Query set

Use real-project questions with an independently curated truth set:

1. exact definition and active declaration;
2. references inside and outside a repository;
3. include candidates versus active target inclusion;
4. call path candidates;
5. build target membership;
6. macro/conditional-compile behavior;
7. generated header/source dependency;
8. change history and ownership evidence;
9. cross-repository producer/consumer path;
10. deliberately absent symbol or dependency;
11. stale-index and wrong-target traps;
12. incomplete workspace and provider-failure traps.

The set must include positive, negative, ambiguous, and configuration-blocked cases. Negative cases count only when exhaustive coverage is independently demonstrable.

## 5. Ground truth and adjudication

Expected answers are prepared separately from provider outputs. Each case includes:

- bounded claim(s);
- authoritative source(s) for the claim;
- permitted partial answers;
- known ambiguity;
- required evidence locations;
- minimum scope/coverage needed for an absence claim.

Two reviewers independently label each provider response:

- `CORRECT_COMPLETE`;
- `CORRECT_PARTIAL`;
- `INCONCLUSIVE_EXPLICIT`;
- `INCORRECT`;
- `FALSE_CONFIDENCE`;
- `UNSCORABLE_ENVIRONMENT`.

Disagreements are resolved by a third adjudication pass with the reason recorded. Provider names are hidden from adjudicators when practical.

## 6. Repetition and cache policy

For each provider/query cohort:

- run at least 3 cold repetitions after documented cache/index reset;
- run at least 5 warm repetitions against the same frozen index;
- randomize query order within the policy constraints;
- record initialization/indexing separately from query latency;
- record timeouts and failures as outcomes, not discarded samples;
- stop only under the predeclared resource/safety limit.

Report median, p90 where sample size permits, range, failure count, and uncertainty. Do not present a single best run as representative.

## 7. Metrics

### Evidence quality

- adjudicated correctness;
- complete and partial recall by query family;
- false-positive and false-negative counts;
- false-confidence rate;
- location/provenance completeness;
- coverage/freshness receipt completeness;
- disagreement rate between providers.

### Cost and operability

- cold setup/index time;
- warm query latency;
- CPU, memory, disk, and index size;
- network dependency;
- deployment and maintenance effort;
- failure observability;
- deterministic repeat rate;
- real-project configuration effort.

### Replaceability

- provider-off behavior;
- replacement provider compatibility with the same public contract;
- evidence bundle stability;
- removal cleanup and audit retention;
- profile behavior when a binding is revoked.

## 8. Timeouts and uncertainty

Timeout values must be declared before runs and tailored to query class. A timeout produces `PROVIDER_ERROR` or `INCONCLUSIVE`; it is never reclassified as “not found.”

If the environment, truth set, or corpus is incomplete, mark the sample `UNSCORABLE_ENVIRONMENT`. Do not average it into a success rate. Report confidence intervals or, for small samples, explicit numerator/denominator and caution.

## 9. Admission decision

A provider may move only to a future scoped profile-binding candidate when:

- artifact and deployment receipts exist;
- required query families meet predeclared evidence-quality thresholds;
- false-confidence cases are zero for designated hard-gate queries, or the provider is barred from those queries;
- failures are observable and fail closed;
- cold/warm cost fits the profile budget;
- removal/replacement tests pass;
- the profile records ceilings and revalidation triggers.

The decision is query-family-specific. A provider may be accepted for lexical acceleration and rejected for semantic absence claims.

## 10. Required report shape

Publish raw samples, adjudication records, environment receipts, failed cases, and a concise decision matrix. The conclusion must separate:

- measured fact;
- reviewer judgment;
- unresolved uncertainty;
- recommendation;
- decision/approval.

Until a campaign report with those artifacts exists, all benchmark status remains `NOT_RUN`.
