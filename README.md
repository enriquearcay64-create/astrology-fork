# Interpretar Mapa Astrológico — Fork V2.1 (Production-Hardened & Audited)

This repository contains the experimental, production-hardened **Fork V2.1** of the `interpretar-mapa-astrologico` skill.

For complete audit instructions, technical architecture, and verification steps for an independent AI reviewer, please read:
👉 **[`AUDIT_GUIDE.md`](./AUDIT_GUIDE.md)**

## Quick Start
```bash
# Run test suite (203 tests)
python3 -m pytest

# Run deterministic chart calculation
python3 scripts/astrology_skill.py <input.json>

# Run end-to-end canonical premium pipeline
python3 scripts/run_canonical_premium_pipeline.py --help
```
