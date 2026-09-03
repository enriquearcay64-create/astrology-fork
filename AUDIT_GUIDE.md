# Independent AI Audit Guide — Astrology Fork V2.1

Welcome, Reviewer / Auditor AI.

This document is the official **Audit Guide and Ground Truth Reference** for the local repository:
`/Users/user/.gemini/antigravity/scratch/astrology-fork`

---

## 1. System Overview & Lineage

- **Original Baseline Skill**: `/Users/user/.codex/skills/interpretar-mapa-astrologico` (Untouched, read-only baseline).
- **Fork V1 Historical Benchmark**: `/Users/user/.gemini/antigravity/scratch/interpretar-mapa-astrologico-fork` (First iteration, preserved as benchmark evidence).
- **Fork V2.1 (This Repository)**: `/Users/user/.gemini/antigravity/scratch/astrology-fork` (Calibrated, production-hardened version with verified guardrails and epistemic calibration).

### Architectural Philosophy
1. **Deterministic Separation of Concerns**: Astronomical positions, house cusps, angular contacts, and timing activations are calculated strictly by `pyswisseph` (Swiss Ephemeris / IAU SOFA) and serialised into cryptographic contracts.
2. **Immutable Technical Data**: The LLM is prohibited from recalculating or inventing mathematical degrees, minutes, orbs, or dates in prose. All exact astronomical facts are deterministically rendered in the **Canonical Technical Appendix**.
3. **Guardrails & Provenance**:
   - **Contract 1.4 Handoff**: `prepare_premium_handoff(...)` generates deterministic sha256 hashes binding `chart_signature`, `signature_synthesis`, `reader_domain_manifest`, and `synthesis_bundle`.
   - **Provenance Guard (`validate_premium_author_bundle`)**: Parses the author narrative using a closed line-aware block parser, verifying that every single paragraph and list item has physical provenance from an approved, evidence-bounded `ReasonedSynthesis` without unapproved extrapolation.
   - **Publication Guard (`validate_premium_narrative`)**: Verifies the lineage between the reviewed draft and final report, ensuring that reviewer corrections maintain hash integrity and attest semantic validity.
   - **Editorial QA Lints (`astrology/editorial_qa.py`)**: Automated heuristic pattern matchers for Barnum phrasing, grandiosity/flattery, and medicalization/physiological claims.

---

## 2. Quick Verification Instructions for the Auditor

### Step 1: Run the Complete Automated Test Suite
From the repository root (`/Users/user/.gemini/antigravity/scratch/astrology-fork`):
```bash
python3 -m pytest
```
*Expected Result*: **203 passed** in ~3.5 minutes with 0 errors.

### Step 2: Check Codebase Hygiene
```bash
git diff --check
```
*Expected Result*: Clean output (0 whitespace or syntax issues).

### Step 3: Run the Canonical Premium Pipeline
To execute a reproducible canonical run for any birth chart:
```bash
python3 scripts/run_canonical_premium_pipeline.py \
  --date "1989-11-01T12:08:00" \
  --tz "America/Caracas" \
  --lat 10.1620 \
  --lon -68.0077 \
  --lang "pt-BR" \
  --out "/tmp/audit_test_run"
```

Or using the installed skill CLI:
```bash
# Stage 1: Prepare Deterministic Handoff
python3 scripts/astrology_skill.py input.json --premium-stage prepare > handoff.json

# Stage 2: Validate Author Bundle (Provenance Guard)
python3 scripts/astrology_skill.py input.json --premium-stage validate-synthesis \
  --premium-handoff handoff.json \
  --premium-synthesis author_bundle.json > provenance.json

# Stage 3: Validate Reviewer Bundle (Publication Guard)
python3 scripts/astrology_skill.py input.json --premium-stage validate-narrative \
  --premium-handoff handoff.json \
  --premium-synthesis author_bundle.json \
  --premium-narrative reviewer_bundle.json > publication.json
```

---

## 3. Patches Applied in V2.1

| Patch | Area | Description |
| :--- | :--- | :--- |
| **Patch 1** | Pipeline Validation | Enforces canonical execution of `validate_premium_author_bundle` and `validate_premium_narrative` with real cryptographic validation. |
| **Patch 2** | Technical Immutability | Prohibits LLM mathematical guesswork. Narrative refers to placements qualitatively; exact degrees, minutes, and orbs are placed in a deterministic technical appendix. |
| **Patch 3** | Anti-Grandiosity / Anti-Flattery | Expanded pattern matchers in `editorial_qa.py` to detect paraphrased praise/heroic inflation; Reviewer acts as primary semantic defense. |
| **Patch 4** | Non-Medicalization of Body | Chapter 9 focuses strictly on symbolic rhythm, workload, daily routine, pauses, sustainability, and subjective effort without physiological or somatic claims. |
| **Patch 5** | Organic Micro-scenes | Mandate for 3–5 embedded 2–4 sentence hypothetical everyday scenes illustrating abstract mechanisms without mechanical quotas or tags. |
| **Patch 6** | Epistemic Calibration | Replaces categorical claims (`você costuma...`, `dificilmente...`, `você foi desenhado para...`) with testable self-observation hypotheses. |
| **Patch 7** | Nodal Axis & Timing | South Node = familiar repertoire / comfort zone; North Node = autonomous individuation direction. Timing includes explicit techniques and dates without guaranteed event prophecies. |
| **Final Integration** | Chapter 19 | Concrete higher-order synthesis organizing the whole person without abstract clichés, concluding with a single reflective question. |

---

## 4. Benchmark Smoke Test & Mathematical Proof

Located in `docs/benchmark_reports/`:
- `01-handoff.json`: Deterministic handoff packet with contract version 1.4.
- `02-author-bundle.json`: Canonical AuthorBundle with narrative block sources.
- `03-provenance-guard.json`: Provenance Guard validation output (`approved: true`).
- `04-reviewer-bundle.json`: Canonical ReviewerBundle with reviewed report.
- `05-publication-guard.json`: Publication Guard validation output (`approved: true`).
- `06-editorial-qa.json`: Editorial QA results (`barnum_risk: 0.0`, `grandiosity_risk: 0.0`, `medicalization_risk: 0.0`).
- `relatorio_publicacao_valencia_v21.md`: Complete 19-chapter publication report with the canonical technical appendix.

### Astronomical Ground Truth for Valencia Chart (01/11/1989 12:08 Local, UTC-4:00)
- **Sun**: 09°13' Scorpio (219.2219°)
- **Saturn**: 09°22' Capricorn (279.3786°)
- **Neptune**: 10°04' Capricorn (280.0792°)
- **Jupiter**: 10°51' Cancer (100.8578°)
- **ASC**: 28°58' Capricorn | **MC**: 07°16' Scorpio
- **Sun sextile Saturn**: Orb = $|279.3786^\circ - (219.2219^\circ + 60^\circ)| = 0.1567^\circ \approx 0.16^\circ$ ($00^\circ09'$).
- **Sun sextile Neptune**: Orb = $|280.0792^\circ - (219.2219^\circ + 60^\circ)| = 0.8573^\circ \approx 0.86^\circ$ ($00^\circ51'$).
- **Saturn conjunct Neptune**: Orb = $0.70^\circ$ ($00^\circ42'$).
- **Jupiter opposite Neptune**: Orb = $0.78^\circ$ ($00^\circ47'$).
- **Jupiter opposite Saturn**: Orb = $1.48^\circ$ ($01^\circ29'$).

---

## 5. Audit Checklist for Reviewers

- [ ] Confirm original skill at `/Users/user/.codex/skills/interpretar-mapa-astrologico` is unmodified.
- [ ] Run `python3 -m pytest` in this repository and verify 203 passing tests.
- [ ] Inspect `astrology/pipeline.py`, `astrology/reasoning.py`, `astrology/editorial_qa.py`, and `astrology/semantics.py`.
- [ ] Verify `validate_premium_author_bundle` and `validate_premium_narrative` enforce cryptographic block hashes and provenance.
- [ ] Verify the publication report in `docs/benchmark_reports/relatorio_publicacao_valencia_v21.md`.
