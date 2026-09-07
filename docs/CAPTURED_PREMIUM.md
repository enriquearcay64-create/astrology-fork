# Captured Premium execution

The live path uses stateless Gemini `generateContent` requests with one supplied context, no tools and no cached conversations. The provider receives text/JSON only; no agent is launched with repository or filesystem access. The actual model ID is an explicit operator setting. `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) belongs in the local environment, never in chat, prompts, Git or receipts. API reference: https://ai.google.dev/api/generate-content.

## Contracts

Selection 1.1 adds required `editorial_sections`: `opening` and `integration` each contain Author-chosen objects with `synthesis_ids` and `intended_mechanism`. There is no numeric block quota. Domain decisions retain the existing exact path schema. Production compilation refuses Selection 1.0. Structural 1.0 validation and the lexical prose binder remain for historical diagnostics/tests; the live captured path does not use that binder.

Author and Reviewer return `packet_id` and `blocks`. Every block explicitly declares `section_id`, `kind`, `content`, `synthesis_ids`, `claim_ids` and `timing_ids`. The renderer handles canonical headings, hashes and ownership. It does not infer sources from keywords, position or neighboring paragraphs. Reviewer source declarations must be a subset of the Author's structurally validated materialized source set in that section. This proves source boundaries; it does not prove every semantic implication of free prose. Technical guards and subsequent evidence-based editorial evaluation still matter.

The run directory records code SHA/source fingerprint before generation, prepared inputs, exact requests, raw provider responses, parsed output, runtime metadata and append-only hash-linked events. Parsing and rendering can be replayed to prove output derivation. Only the orchestrator writes artifacts. The local orchestrator and storage owner remain trusted: hashes are not external attestation against an owner rewriting the entire history.

Completed stages resume without another call when inputs and code match. Changed inputs/models, pending failed calls and malformed responses never overwrite prior attempts. A failed incomplete attempt requires a new run ID; automatic paid retries are deliberately absent. Raw failures remain evidence.

## Operator commands

Use a clean, committed candidate that has received independent benchmark-ready review. The audit JSON must contain `verdict: "benchmark-ready"`, the reviewed `commit_sha` and `source_sha256` from `astrology.isolated_execution.code_context`. Do not fabricate this record. Supplying a record is the operator's attestation of independent review, not a cryptographic identity proof.

```bash
python3 scripts/astrology_skill.py input.json --premium-stage prepare-run --run-dir /absolute/path/to/runs/new_run --audit-record /absolute/path/to/independent-audit.json --as-of 2026-09-07T12:00:00+00:00
python3 scripts/astrology_skill.py input.json --premium-stage run-captured --run-dir /absolute/path/to/runs/new_run --model ACTUAL_CONFIGURED_MODEL_ID
```

Selection, Author, Provenance Guard, Reviewer, Publication Guard and deterministic QA run in sequence. A failed gate prevents the next model call or delivery artifact. Birth/profile changes cannot resume another packet.

For Chart 3 comparison, provide a compatible champion and a rubric JSON with 17 `dimensions`. The evaluator receives only anonymous Alpha/Beta prose, sanitized technical truth, and the frozen rubric. Neither prior scores nor the mapping enters its prompt. The code commits nonce + mapping + report/rubric/truth hashes before invocation. Reveal is a separate command after raw response and structured scores are frozen:

```bash
python3 scripts/astrology_skill.py input.json --premium-stage evaluate-captured --run-dir /absolute/path/to/runs/new_run --model ACTUAL_CONFIGURED_MODEL_ID --champion-report /absolute/path/to/champion.md --rubric /absolute/path/to/rubric.json
python3 scripts/astrology_skill.py input.json --premium-stage reveal-captured --run-dir /absolute/path/to/runs/new_run
python3 scripts/run_chart3_pipeline.py --run-dir /absolute/path/to/runs/new_run
```

Scores are model judgments, not objective psychometric measurements. Verify snapshot compatibility of the champion before comparison. No command automatically promotes a champion, merges code, installs the skill or sends a report to a client.

## Offline reproducibility

```bash
python3 -m tests.captured_fixture --out /tmp/astrology-captured-fixture
python3 scripts/run_chart3_pipeline.py --run-dir /tmp/astrology-captured-fixture
```

This versioned recipe deliberately reuses historical prose as test data, supplies synthetic model envelopes and zero-valued protocol scores, and marks the manifest `synthetic_test_fixture`. It is not premium generation and cannot be promoted. It exercises request/response capture, guards, replay, commitment and reveal without API access.

## Release boundary

Engineering tests do not establish live provider reliability, report quality, unseen-chart generalization or commercial readiness. The next gates are independent code review, configured runtime, genuinely fresh Chart 3, 5–6 unseen charts and the client deliverable/rendering checks in the master plan. The installed astrology skill and main branch remain untouched.


## Narrow closure after cdc0fe442

Champion capture authentication is deferred: `--champion-run` was removed. Descriptors are historical compatibility claims only; all comparisons are `historical_legacy` / `legacy_weaker`, and promotion is disabled even if manifest flags claim approval. This supports regression signals, not a causal architecture comparison or final promotion evidence.

For a benchmark, `prepare-run` accepts `--champion-report`, `--champion-descriptor`, `--rubric`, explicit candidate/evaluator models and thinking levels, and repeatable `--contamination-file` paths inside the repository. An external `--benchmark-spec` must also declare a non-promotable historical comparison. Empty contamination corpora produce a failed/insufficient check, never PASS. Ordinary non-benchmark generation remains independent of this check.

The prepared handoff is reused to build the spec. Later `run-captured` and `evaluate-captured` load model, thinking, temperature and token limits from that spec; omit redundant model/thinking arguments, or supply matching values. Evaluator evidence must quote the corresponding anonymous report verbatim. Quote validation establishes textual anchoring, not the semantic adequacy of a judgment.
