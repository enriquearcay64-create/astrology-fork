# Premium Complete Report Contract V4.1.4

## Version boundary

This release publishes package/product `4.1.4`, report template `4.1.4-whole-person`, and Premium handoff contract `1.4`. It preserves methodology `4.1.3`, factual schema `4.1.1`, semantic registry `2.6.0`, and timing methodology `4.0.1`. Policy rules, facts, scoring, and astrological calculations remain unchanged; the manifest reports the new template and current handoff-contract metadata. Contract `1.3` is frozen for validation/replay only; new preparation always emits `1.4`.

## Prospective Author flow

The Author reads the complete domain manifest, constructs the `ReaderSelectionPlan` prospectively, decides every legal path as represented, merged with a represented path, or omitted with a rationale, constructs the required approved syntheses, and only then writes the reader-facing blocks. The plan cannot be a retrospective explanation of already-written prose. Legal-path order is serialization only; it is not priority or centrality. Premium Complete must not erase a distinct human mechanism merely because its factor is secondary to the `ChartSignature`.

The Reviewer decides semantic adequacy. A represented path must have its distinct human mechanism materially expressed in coverage-eligible content. A merge must preserve material distinct contribution rather than rely on a shared planet, house ruler, reasoning class, operation, or broad topic. An omission is valid only when the Reviewer attests that no distinct human consequence remains.

## Narrative block grammar

The closed line-aware parser recognizes paragraphs, ordered/unordered list items, sourced H3 subheadings, canonical H2 headings, and exact unavailable notices. It rejects nested lists, tables, blockquotes, HTML blocks, code fences, separators, metadata, and H4+. Bullets attached to a paragraph without a blank line become independent list-item blocks. H3 must be non-empty, belong to an available domain, cite only legally pertinent approved syntheses, and be followed by a paragraph or list item before the next H3/H2.

The single `canonical_narrative_block_payload()` function is used by parsing, templates, guards, tests, and audit:

```json
{"kind":"paragraph","content":"..."}
{"kind":"list_item","list_style":"ordered","content":"..."}
{"kind":"subheading","content":"..."}
```

Normalization changes only CRLF/CR line endings, trailing spaces, syntactic continuation indentation, and outer whitespace. Inline Markdown and text are preserved. The resulting `narrative_block_sha256` identifies semantic/provenance content; `final_report_sha256` continues to bind the exact final Markdown string.

## Closed bundle and ownership shape

Author and Reviewer bundles accept only their contract-defined fields. Unknown fields, legacy paragraph fields, and mixed-version payloads fail. Source rows use exactly `narrative_block_sha256`, `synthesis_ids`, `claim_ids`, and `timing_ids`. Every authored paragraph, list item, and H3 has exactly one row and appears in physical order in `reader_sections`. Opening/integration sections contain only `narrative_block_sha256s`; domain sections contain only `domain_id` and `narrative_block_sha256s`. Unavailable domains contain only their exact notice and no authored blocks, ownership, or source rows.

Paragraphs and list items are coverage-eligible. H3 source rows are synthesis-only and coverage-ineligible: H3 cannot satisfy mandatory coverage, domain coverage, reader-selection provenance, or a represented/merged path by itself. The fixed reader introduction, H2 headings, and unavailable notices remain deterministic product structure outside Author astrological provenance.

## Set-level synthesis legality

For each represented target, the validator forms a cluster from the represented path, all paths directly merged into it, and the target's declared synthesis set. Each cluster path must be matched by at least one synthesis that individually satisfies `_synthesis_matches_reader_path`; partial claims, factors, operations, or reasoning classes distributed across syntheses never fabricate a path. Every declared synthesis must match at least one path, be approved, be physically sourced in the same domain, and appear in a final coverage-eligible block. Timing IDs retain exact cluster-level equality and local ancestry rules.

## Guard sequence

After authenticating the authoritative prepared handoff, Author provenance, and Reviewer plan/hash, Publication Guard performs a final canonical parse, exact ownership check, source-map integrity check, block-local legality check, mandatory coverage check, and complete ReaderSelectionPlan revalidation using paragraphs/list items only. Removing the authored paragraph/list item and leaving a sourced H3 must fail. Reviewer layout edits require updated hashes, ownership, and source rows.

Python proves deterministic invariants only: shape, order, IDs, hashes, approved syntheses, physical provenance, individual synthesis legality, timing ancestry/sets, ownership, and coverage. The Reviewer judges meaning, convergence, redundancy, material expression, orientation, scanability, and whether the writing has become cookbook astrology.

## Readability and audit

Depth is adaptive. A simple domain may remain brief; a rich domain may expand as needed. Compress repetition and overhead before authorized distinct meaning. H3, bullets, micro-scenes, and synthesis paragraphs are options, not a template. Do not put counts of paragraphs, mechanisms, bullets, subsections, examples, words, minutes, or pages in the reader-facing report. Length alone is never a gate.

`ux_editorial_audit.py` selects its parser from the artifact's Premium contract version. For `1.4`, semantic depth and coverage count paragraphs plus list items; H3 is counted separately, while jargon, Barnum, genericity, language, and reader-visible word metrics include H3. Layout signatures such as `P-H3-L-L-P` are descriptive inspection signals; high uniformity is never an automatic error. The audit sidecar retains its established structure and technical content.
