from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from astrology.models import BirthData
from astrology.validation import counterfactual_distinguishability, qa_snapshot, run_ablations, run_synthetic_natal_pilot
from astrology.pipeline import analyse_birth_chart


def birth():
    return BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333)


def test_ablation_records_do_not_claim_extra_evidence():
    result = run_ablations(birth())
    assert result["placidus_only"]["status"] == "canonical natal mode"
    assert result["without_feedback"]["status"] == "no core change expected"
    assert result["without_localization"]["theme_ids"] == result["baseline"]["theme_ids"]
    assert result["semantic_motif_ablation"]["removed_family"] in result["baseline"]["evidence_families"]
    assert result["semantic_motif_ablation"]["removed_family"] not in result["semantic_motif_ablation"]["evidence_families"]
    assert result["whole_sign_only"]["claim_count"] < result["baseline"]["claim_count"]


def test_counterfactual_and_qa_are_explicit_about_scope():
    counterfactual = counterfactual_distinguishability(birth())
    assert counterfactual["pass"]
    assert "not a blind human-matching study" in counterfactual["limit"]
    qa = qa_snapshot(birth())
    assert qa["technical_truth"]["positions"]
    assert qa["narrative_quality"]["contains_limit"]


def test_same_input_same_versions_and_same_as_of_produce_same_payload():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    first = analyse_birth_chart(birth(), as_of=as_of, horizon_days=30)
    second = analyse_birth_chart(birth(), as_of=as_of, horizon_days=30)
    assert first["chart"] == second["chart"]
    assert first["claims"] == second["claims"]
    assert first["timing"] == second["timing"]
    assert first["report"] == second["report"]


def test_synthetic_pilot_is_explicitly_not_human_validation():
    pilot = run_synthetic_natal_pilot()
    assert pilot["quality_gate"]["pass"]
    assert "No human participants" in pilot["limit"]
