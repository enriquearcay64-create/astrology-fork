# Astrology Fork — Repository Instructions

## Purpose

Build clear, deep, humane astrology reports from deterministic calculations and constrained interpretation. Prioritize whole-chart synthesis and insight per paragraph, not placement counts. Interpretations are hypotheses, not established psychological facts, diagnoses or invented biography.

Python owns calculation, factual legality and structural provenance. The Author owns editorial selection and narrative synthesis. The Reviewer improves prose within the Author's materialized source authority and may withhold approval.

## Start here

Establish the actual branch, commit and working-tree state. Preserve existing changes. Do not assume a previous conversation describes the current checkout; retain the user's current instructions and prior authorizations.

Read:

1. `docs/ARCHITECTURAL_INVARIANTS.md` for architectural constraints.
2. The superseding notice and applicable status in `docs/V231B_STATUS.md`; older entries are historical evidence, not current instructions.
3. Only the implementation, tests and documentation relevant to the task.

For captured execution or benchmarks, additionally read `docs/CAPTURED_PREMIUM.md`. Locate the affected path before reading large modules; do not load the entire pipeline by default.

## Requirements and evidence

Within the applicable system and developer instructions, follow the user's task, explicit scope and existing authorizations. Use architectural invariants and applicable release requirements to establish intended behavior; use current code, tests and artifacts to establish observed behavior.

Tests establish checked behavior, not permission to override an invariant. Historical artifacts are evidence, not specifications. Neither green tests nor documentation alone proves correctness. When sources disagree, verify the discrepancy before editing; do not treat a status summary as authority to weaken an invariant or disregard a demonstrated defect.

## Boundaries

- Keep editorial selection Author-owned. Do not encode semantic rankings, placement quotas or chart-specific prose choices in Python.
- Preserve packet lineage, frozen preparation parameters and the distinction between permitted, planned and materialized sources.
- Captured live prose uses explicit source declarations. Do not restore lexical provenance inference or attach sources retrospectively to make validation pass.
- The Reviewer cannot acquire authority the Author failed to materialize. Approval may include no corrections; do not require unnecessary rewriting.
- Preserve the distinction between exact timing events and closest approaches.
- Do not weaken provenance, publication or execution guards to improve scores or make tests pass.
- Change deterministic calculations, Selection semantics, Contract semantics or `PAIR_RULES` only for a demonstrated defect or an explicitly scoped requirement. Validate the affected invariant.

Version-specific contracts and release gates belong in the referenced documents and implementation, not duplicated here.

## Report quality work

Use the current Author/Reviewer prompts and editorial checks as the operational entry points. Favor interacting mechanisms, internal tensions, concrete hypothetical manifestations and useful integration. Do not turn these into a compulsory paragraph template.

Write for an intelligent adult: clear, specific, nuanced and non-diagnostic. Avoid flattery, inevitability, generic personality claims and unnecessary jargon. Retain uncertainty where warranted.

Benchmark generations must not receive known biography, previous reports, expected traits or other subjects' context. Keep production prompts general; do not tune them to make one known chart appear successful. A client-context feature requires explicit scope and must distinguish supplied information from chart-derived interpretation.

Editing this file does not change the prompts sent to stateless model calls. Implement intended runtime behavior in the existing prompt/contract path and verify it there. Do not create a separate editorial document unless it serves a demonstrated need with a clear authoritative role.

## Engineering workflow

Verify the issue and its reachable execution path before editing. Prefer the smallest root-cause fix, including deletion of an unsafe path where appropriate. Avoid unrelated cleanup, speculative abstractions, duplicate validation layers and silent compatibility fallbacks.

Be token-efficient: search narrowly, avoid rereading unchanged material or restating established context, and load only what the task needs. More machinery is not more assurance.

Use focused tests during development. For protocol changes, exercise observable invalid-evidence paths and failure behavior, not just helper outputs. When stable, run the full suite, inspect the final diff and run `git diff --check`. Repeat checks when subsequent changes or failures warrant it; use proportionate checks for documentation-only work.

Preserve failure artifacts and historical evidence. Do not alter benchmark prose to improve scores. Never label synthetic output as fresh generation or premium-quality evidence.

## Execution and release gates

Do not make paid model calls or run a real benchmark without explicit user authorization and the applicable recorded engineering clearance. Existing authorization remains valid within its scope; do not ask again unnecessarily.

Before benchmark generation, freeze the experiment identity. Tie subsequent requests and evaluation to that identity. Do not derive promotion authority from user-declared flags, empty checks or synthetic fixtures. Follow the current supported comparison modes and promotion restrictions in `docs/CAPTURED_PREMIUM.md` and the implementation.

Passing CI means the executed checks passed; it does not prove exhaustive correctness, editorial quality or product superiority. A checkpoint, descriptor or local hash is not independent attestation.

Do not self-award independent clearance for a patch you authored. Do not merge, publish, install or push unless authorized by the task. Do not modify `main` when the task specifies a candidate branch.

## Completion

Report the result, material changes, relevant files, validation and limitations concisely. For code work, include branch/SHA and exact remote CI status when checked. Distinguish full-suite success from partial checks, corrected failures and pending verification.

Stop when the requested scope is complete and verified. State remaining gates honestly; do not expand the task or declare the product finished merely because the patch passes tests.
