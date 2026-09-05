# Architectural Invariants & Reproducibility Standards

## 1. Single Authoritative Calculation Snapshot & Strict Lineage Equality
- **One Source of Truth**: All pipeline stages (handoff, candidate catalog, author selection, prospective block plan, author prose, reviewer pass, and technical appendix) must derive from a single authoritative calculation snapshot.
- **Strict Lineage Invariant**:
  ```python
  handoff["packet_id"] == selection_plan["packet_id"] == block_plan["packet_id"] == reasoning_packet["packet_id"]
  ```
  Any desynchronization between packets must fail closed prior to prose drafting.
- **Frozen Temporal Configuration**: `effective_as_of` is resolved exactly once at the entry point and persisted. Resumptions reload the persisted snapshot and never recalculate "now".

## 2. Genuine Agent Selection Ownership & Validated Candidate Catalog
- **Author-Owned Selection**: The Author explicitly evaluates candidate legal paths and produces the `ReaderSelectionPlan` (deciding `represented`, `merged_with_represented`, or `omitted_no_distinct_reader_value`).
- **Validated Candidate Catalog**: The Author receives the complete domain manifest along with a validated `SelectionCandidateCatalog` containing all legal coverage paths, human-readable observations, primary factors, and authorized synthesis IDs.
- **Coverage Contract**: Every available domain must have at least one path marked `represented`. Mass omissions that leave an available domain with zero represented paths fail closed during validation.
- **Zero Python Editorial Ranking**: Python never re-ranks paths, injects domain special cases, or decides semantic relevance.
- **Fail-Closed in Production**: Production execution strictly fails closed without a validated `author_selection_plan`. A conservative fallback (100% represented, 0 merged, 0 omitted) exists exclusively for headless/test runs via explicit flag (`allow_conservative_fallback=True`).

## 3. Reviewer Authority Boundary & Materialized Provenance
- **Three Separate Source States**:
  1. *Permitted Sources*: All syntheses available in the chart's candidate catalog.
  2. *Planned Sources*: The specific subset allocated to narrative blocks in the prospective block plan.
  3. *Materialized Sources*: The subset of planned sources actually articulated and materialized in prose by the Author.
- **Reviewer Bounded by Author Authority**: The Reviewer may polish, clarify, and integrate prose within the authority materialized by the Author. The Reviewer CANNOT:
  - Introduce new astrological attributions or synthesize placements not present in the Author's materialized prose.
  - Borrow sources from other domains or candidate paths.
  - Claim planned sources that the Author failed to materialize.
- **Deterministic Provenance Guard**: If the Author fails to materialize mandatory coverage items or violates block-level bindings, the pipeline fails closed prior to the Reviewer.

## 4. Strict Semantic Field & Timing Integrity
- **Exact Perfection vs. Closest Approach**: Any field named `exact_*` (such as `exact_peak` or `exact_at`) must strictly evaluate to an exact mathematical perfection timestamp.
- **Non-Contamination**: When an aspect only achieves a near-exact closest approach (e.g. within orb without mathematical perfection), `exact_peak` and `exact_at` must evaluate to `""` (empty string) and never fall back to `closest_approach_at` or `peak_date`.
- **Astronomical Precision**: Planetary positions, orbs, and timing windows are computed deterministically via ephemeris calculations and must never be rounded or altered by generative models in prose.

## 5. Benchmark Immutability, Tamper Detection & Replay Standards
- **Versioned Immutable Traces**: Every benchmarked chart maintains its complete, auditable execution trace in `benchmarks/<chart_id>/`:
  - `benchmark_manifest.json` containing SHA-256 hashes of all artifacts.
  - Prompts, raw drafts, reviewed reports, appendices, and guard validation records.
- **Deterministic Replay**: The replay runner verifies cryptographic hashes, snapshot lineage, block plan compilation, technical appendix rendering, and publication guards directly from versioned files.
- **Explicit Error Types**: Integrity checks must raise explicit exceptions (such as `BenchmarkIntegrityError`) rather than bare `assert` statements, guaranteeing tamper detection remains active even under optimized execution (`python -O`).
- **Honest Traceability**: Benchmarks distinguish deterministic replay from generative non-determinism. Frozen artifacts pass deterministic replay; LLM editorial ratings reflect the specific versioned run and are preserved as historical evidence.
