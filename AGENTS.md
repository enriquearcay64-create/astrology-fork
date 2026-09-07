# Astrology fork engineering

Read `docs/ARCHITECTURAL_INVARIANTS.md` and `docs/V231B_STATUS.md` before editing the premium pipeline.

- Python owns deterministic legality and provenance; the Author owns reader-value decisions.
- Never fabricate approval or execution metadata, copy historical prose into a fresh run, or call a replay/fixture a premium generation.
- Preserve invalidated benchmark evidence. Keep subjects isolated.
- V2.3.1b remains engineering-only until independent benchmark-ready review. No new generative benchmark or merge while that gate is pending.
