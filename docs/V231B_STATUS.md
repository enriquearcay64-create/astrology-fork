# V2.3.1b engineering checkpoint — implementation ready for independent review

M1 now includes captured execution and an offline end-to-end protocol fixture. This is not a completed product or an independent benchmark-ready declaration. Work remains on `v2.3.1-candidate`, based on `36e807e3340b802ac5dd355141de8837928d3e00`. No new model generation, premium benchmark, merge, push, installation or usage-reset redemption was performed.

## Implemented

- Prospective Selection requires packet lineage and rejects missing/extra/duplicate domains and paths, malformed decision fields, missing catalog/basis, altered catalogs, invalid ancestry and all-omitted available domains.
- Production planning no longer stamps composed syntheses as allowed or silently accepts handoff/legacy Selection bypasses. The explicit conservative fixture path remains test-only and is validated.
- Final 1.4 Selection validation requires packet ID and checks it against the authoritative packet. Legacy 1.3 dispatch remains separate.
- `astrology/premium_workflow.py` centralizes Selection prompts, frozen parameters and Author preparation; the installed CLI exposes `prepare-selection`, `validate-selection`, `prepare-author` with `--premium-handoff` and `--premium-selection`.
- Frozen input identity is checked without recalculating the chart on resume. Non-default horizons and timing flags are preserved; a deliberately null reading instant remains allowed for timing-disabled snapshots.
- PT/EN paragraph quotas removed. The Author is told the attached plan is already frozen.
- Historical run `run_20260905_052000` is machine-readably invalidated; prose files remain unchanged. Invalidated runs cannot pass current replay/promotion helpers.
- Replay requires an explicit CLI run directory, compares full plans, appendix, original bundles, guards and QA; no heading-only equivalence. Original Reviewer correction metadata is preserved rather than invented by replay.
- Artifact verification rejects missing/changed files, empty inventories, duplicate JSON keys and path escapes. Real tampering still fails under optimized Python.
- Contamination checks reject exact unrelated historical prose and hold near copies. They are connected to benchmark Author/Reviewer acceptance in the harness for the explicit family/runs layout; replay fixtures are not presented as fresh evidence.
- Blind commitment helpers bind nonce, mapping, report hashes, run, rubric and truth; structured score totals and wins/ties are computed. Trace inventory/schema helpers were added. These helpers alone do not enforce execution isolation or chronology.
- Publication-file assembly now requires successful publication, technical fidelity and editorial results; previously the harness wrote that file even after a failed guard.

## Continuation completed on 2026-09-07

- Tool-free, stateless Gemini API transport with explicit model configuration; no filesystem-capable generative agent, tools, inherited history or cache is supplied.
- Raw request/response capture, stable canonical prompts, parsed-response verification, append-only hash-linked events, exclusive writes and code/input/model checks on resume. Failed attempts are preserved rather than silently retried.
- Persistent blind commitment, controlled technical truth, frozen evaluator scores and separate reveal. Runtime inputs and generation-time source/commit metadata enter the portable trace.
- Selection 1.1 requires Author-owned opening/integration sections. Python no longer chooses their sources or splits mandatory material in the production compiler.
- The captured Author/Reviewer declare sources per block. Rendering validates those declarations and Reviewer authority; it does not use the lexical/positional binder. Legacy binding remains diagnostic only.
- Shared Author/preflight prompt assembly and strict frozen block-plan checks in standalone resume helpers.
- Official CLI exposes captured preparation, execution, evaluation, reveal and replay. See `docs/CAPTURED_PREMIUM.md`.
- Versioned offline fixture recipe `python3 -m tests.captured_fixture --out <new-directory>` and full fixture `runs/synthetic_protocol_20260907`. Its reports and scores are explicitly synthetic test evidence and cannot be promoted.
- Full suite: **289 passed in 359.98s**. Captured execution tests after final request/prompt checks: **9 passed in 22.75s**. No live API request or premium model run occurred.

## Remaining release gates

1. Independent M2 audit of this exact candidate and source fingerprint. A JSON audit record is an operator attestation, not independently authenticated reviewer identity. The implementation must not self-award benchmark-ready status.
2. Configure the actual model runtime. No Gemini/OpenAI API key was present when checked. Gemini API support is implemented but has only offline contract tests so far; live provider/model availability has not been demonstrated.
3. After those gates: fresh Chart 3, blind evidence-backed evaluation, 5–6 unseen charts, operator/client deliverable and rendering checks. No new quality score or commercial readiness is claimed.
4. Semantic fidelity remains a constrained model/reviewer responsibility supported by technical guards. Explicit source declarations prove structural authority, not every psychological implication of free prose. Storage/orchestrator owners remain trusted; local hashes are not external attestation.

## Test migration rationale

Historical fixtures omit packet IDs and a validated catalog. They cannot remain valid production inputs under the requested strict contract. `tests/legacy_fixture_adapter.py` re-prepares authoritative data for structural regression tests only, and tests attach the resulting packet ID to their in-memory synthetic plans. No historical file is rewritten, no approval is stamped, and these tests make no freshness claim. Old replay tests now assert rejection of insufficient historical evidence while preserving real file-tampering coverage. The 1.4 fixture helper now explicitly carries its packet ID; 1.3 fixtures retain their legacy schema.

## Verification

Baseline full suite passed before edits. The first post-change full run exposed the expected old-fixture compatibility failures; these were fixed without relaxing production requirements. Latest full-suite results are recorded in `docs/evidence/v231b/final-tests.log` once complete. Focused and optimized-Python evidence are stored alongside it. Read the actual results rather than treating this checkpoint as PASS.

## Next action

Obtain independent M2 review of the captured execution candidate and configure the chosen runtime. Keep live generation disabled until the engineering audit clears it. Do not reuse the invalidated run as promotion evidence or claim the 159/170 historical score validates this patch.

Final verification: 279 passed in 337.31s (0:05:37). The final contamination/ancestry and delivery-gate delta checks also passed (3 passed). `git diff --check`, compilation, official CLI Selection/Author smoke checks and actual tampering under `python -O` passed. The implementation is saved on the candidate branch for review; no remote CI result is claimed for this revision.

Persisted synthetic trace replay: exit code 0, 74 artifact hashes verified. The offline fixture remains ineligible for promotion. Live provider checks and installed-package deployment validation are still part of the remaining release work.
