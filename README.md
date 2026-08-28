# Astrology Engine Skill

Local Codex skill for reproducible astrological calculation and human-readable,
evidence-traceable natal reports.

## Core principle

**Hard facts, soft synthesis, hard verification.**

- Deterministic calculation: ephemerides, timezone/DST, houses, angles,
  aspects, conditions, timing and stability tests.
- Constrained synthesis: a closed factual packet lets a high-reasoning model
  compose chart-specific interpretations without inventing factors.
- Strict verification: unsafe house topology, unsupported claims, diagnoses,
  biographical assertions and deterministic event claims are blocked.

It supports Whole Sign plus Placidus, independent angles, transits,
profections, progressions, solar arcs, life intervals, technical appendices and
consultation prompts in Portuguese or English.

## Safety architecture

The raw chart is never handed directly to report rendering. It first passes
through a stability gate into a SafeInterpretiveChart. If birth-time sensitivity
changes the Whole Sign topology, house-dependent statements, topical rulers,
Lots and profections are withheld or explicitly conditional.

## Quick start

Install with Python 3.9+:

~~~bash
pip install .
astrology-skill input.json --depth deep --format report
~~~

For Codex use, follow [SKILL.md](SKILL.md). The full v3 review is in
[AUDITORIA_V3.md](AUDITORIA_V3.md).

## Development checks

~~~bash
python3 -m pytest -q
python3 scripts/ux_editorial_audit.py --stage after --output /path/to/output
~~~

This software makes no scientific claim that astrology can determine
personality or future events. Reports are symbolic prompts for reflection, not
diagnoses or predictions.
