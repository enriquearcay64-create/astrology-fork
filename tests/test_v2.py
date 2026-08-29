from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from astrology.config import FALLS
from astrology.consultation import answer_question
from astrology.engine import _house_integration_state, angular_distance, calculate_chart
from astrology.models import Aspect, BirthData, LocalizationProfile
from astrology.models import Claim
from astrology.pipeline import analyse_birth_chart, consult
from astrology.privacy import opaque_id, redact_for_logs
from astrology.semantics import _claim_from_aspect, verify_claims
from astrology.timing import life_timeline, major_transits


def birth() -> BirthData:
    return BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333)


def test_traditional_fall_table_does_not_contradict_moon_exaltation():
    assert FALLS.get("Scorpio") == "moon"
    assert FALLS.get("Taurus") != "moon"


def test_dst_ambiguity_requires_explicit_fold_and_nonexistent_time_is_rejected():
    ambiguous = BirthData("2021-11-07T01:30:00", "America/New_York", 40.7128, -74.0060)
    with pytest.raises(ValueError, match="dst_fold"):
        calculate_chart(ambiguous)
    first = calculate_chart(BirthData(**{**ambiguous.__dict__, "dst_fold": 0}))
    second = calculate_chart(BirthData(**{**ambiguous.__dict__, "dst_fold": 1}))
    assert first.utc_datetime != second.utc_datetime
    with pytest.raises(ValueError, match="non-existent"):
        calculate_chart(BirthData("2021-03-14T02:30:00", "America/New_York", 40.7128, -74.0060))


def test_generic_pair_semantics_are_order_invariant():
    chart = calculate_chart(birth(), include_secondary=False)
    left = Aspect("a", "moon", "mars", "square", 90, 90, 1, True)
    right = Aspect("b", "mars", "moon", "square", 90, 90, 1, True)
    assert _claim_from_aspect(left, 1, "en-US").theme == _claim_from_aspect(right, 1, "en-US").theme
    assert _claim_from_aspect(left, 1, "en-US").authorized_motifs == _claim_from_aspect(right, 1, "en-US").authorized_motifs


def test_applying_state_uses_short_instantaneous_sample():
    chart = calculate_chart(BirthData("2000-01-01T12:00:00", "UTC", 0, 0), include_secondary=False)
    for aspect in chart.aspects:
        if aspect.applying is None:
            continue
        left = chart.positions[aspect.left]
        right = chart.positions[aspect.right]
        now = abs(angular_distance(left.longitude, right.longitude) - aspect.angle)
        minute = 1 / 1440
        soon = abs(angular_distance(left.longitude + left.speed_longitude * minute, right.longitude + right.speed_longitude * minute) - aspect.angle)
        assert aspect.applying is (soon < now)


def test_dispositor_cycles_are_unique_and_self_reception_is_not_emitted():
    chart = calculate_chart(birth())
    cycles = [factor for factor in chart.factors if factor.kind in ("final_dispositor", "dispositor_cycle")]
    assert len({tuple(factor.data["cycle"]) for factor in cycles}) == len(cycles)
    assert all(len(set(factor.bodies)) == 2 for factor in chart.factors if factor.kind == "mutual_reception")


def test_dual_house_policy_exposes_all_material_states():
    assert _house_integration_state(10, 10, None)[0] == "robust_same_house"
    assert _house_integration_state(10, 9, {"distance_degrees": 5})[0] == "whole_topic_placidus_qualifier"
    assert _house_integration_state(4, 10, {"distance_degrees": 10})[0] == "complementary_emphases"
    assert _house_integration_state(2, 5, {"distance_degrees": 10})[0] == "material_divergence"
    assert _house_integration_state(2, None, None)[0] == "placidus_unavailable"


def test_natal_hierarchy_is_invariant_to_timing_horizon():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    short = analyse_birth_chart(birth(), as_of=as_of, horizon_days=30)
    long = analyse_birth_chart(birth(), as_of=as_of, horizon_days=730)
    assert short["hierarchy"] == long["hierarchy"]
    assert short["current_hierarchy"] != long["current_hierarchy"] or short["timing"] != long["timing"]


def test_consultation_never_falls_back_to_arbitrary_claims_or_sensitive_advice():
    unknown = consult(birth(), "Tell me something completely unspecified", LocalizationProfile(preferred_language="en-US"), datetime(2026, 8, 27, tzinfo=timezone.utc))
    assert unknown["consultation"]["claims"] == []
    sensitive = consult(birth(), "Will I get a medical diagnosis?", LocalizationProfile(preferred_language="en-US"), datetime(2026, 8, 27, tzinfo=timezone.utc))
    assert sensitive["consultation"]["claims"] == []
    assert "do not use astrology" in sensitive["consultation"]["answer"]


def test_english_report_is_actually_english_and_deep_report_has_no_placeholder():
    as_of = datetime(2026, 8, 27, tzinfo=timezone.utc)
    english = analyse_birth_chart(birth(), LocalizationProfile(preferred_language="en-US"), include_timing=False)
    assert english["report"].startswith("# Executive Reading")
    assert "Leitura Executiva" not in english["report"]
    deep = analyse_birth_chart(birth(), report_depth="deep", as_of=as_of, horizon_days=30)
    assert "a ser preenchido" not in deep["report"]
    assert "Dinâmicas que organizam o mapa" in deep["report"]


def test_technical_json_blocks_are_valid_json():
    report = analyse_birth_chart(birth(), report_depth="technical", include_timing=False)["report"]
    blocks = report.split("```json")[1:]
    assert blocks
    for block in blocks:
        json.loads(block.split("```", 1)[0])


def test_life_cycles_exclude_natal_baseline_and_group_passes():
    chart = calculate_chart(birth())
    timeline = life_timeline(chart)
    activations = [item for phase in timeline for item in phase["activations"]]
    assert activations
    birth_instant = datetime.fromisoformat(chart.utc_datetime)
    assert all((datetime.fromisoformat(item["exact_at"] or item["closest_approach_at"]) - birth_instant).days > 365 for item in activations)
    assert all("passes" in item and item["window_start"] <= item["window_end"] for item in activations)


def test_policy_schema_current_phase_and_directed_contacts_are_structured():
    result = analyse_birth_chart(birth(), as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=30)
    assert result["chart"]["schema_version"] == "4.1.0"
    assert result["chart"]["policy"]["anti_cherry_picking"] if "anti_cherry_picking" in result["chart"]["policy"] else result["chart"]["policy"]["house_policy"]["anti_cherry_picking"]
    assert result["timing"]["current_phase"]["traditional_focus"]["time_lord"]
    assert "contacts" in result["progressions"] and "contacts" in result["solar_arcs"]
    assert result["chart_structure"]["spatial_distribution"]["quadrants"]


def test_naive_timing_reference_is_rejected():
    with pytest.raises(ValueError, match="UTC offset"):
        major_transits(calculate_chart(birth()), datetime(2026, 8, 27), 10)


def test_privacy_ids_require_secret_and_log_redaction_is_recursive():
    payload = {"birth": {"local_datetime": "1990-01-01", "latitude": 1.0}, "label": "x"}
    with pytest.raises(ValueError):
        opaque_id("birth", payload, b"short")
    first = opaque_id("birth", payload, b"a" * 32)
    assert first == opaque_id("birth", payload, b"a" * 32)
    assert first != opaque_id("birth", payload, b"b" * 32)
    redacted = redact_for_logs(payload)
    assert redacted["birth"]["local_datetime"] == "[redacted]"
    assert redacted["birth"]["latitude"] == "[redacted]"


def test_ephemeris_assets_match_integrity_manifest():
    manifest = {}
    for line in (SKILL_ROOT / "assets" / "ephe" / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split()
        manifest[name] = digest
    for name, expected in manifest.items():
        assert hashlib.sha256((SKILL_ROOT / "assets" / "ephe" / name).read_bytes()).hexdigest() == expected


def test_unknown_birth_time_never_invents_angles_houses_sect_or_lots():
    unknown = BirthData("1990-07-12", "America/Sao_Paulo", -23.5505, -46.6333, birth_time_known=False)
    chart = calculate_chart(unknown)
    assert chart.angles == {}
    assert chart.house_placements == {}
    assert chart.lots == {}
    assert not any(factor.kind == "sect" for factor in chart.factors)
    result = analyse_birth_chart(unknown, report_depth="deep", as_of=datetime(2026, 8, 27, tzinfo=timezone.utc), horizon_days=10)
    assert "Ângulos e casas indisponíveis" in result["report"]
    assert result["timing"]["traditional_stream"]["status"] == "unavailable"


def test_outer_planets_are_not_stationary_merely_for_being_slow():
    chart = calculate_chart(birth())
    conditions = {factor.bodies[0]: factor.data["conditions"] for factor in chart.factors if factor.kind == "planetary_condition"}
    assert "stationary" not in conditions.get("uranus", [])


def test_semantic_verifier_checks_authorization_and_bilingual_biography():
    chart = calculate_chart(birth())
    aspect = next(item for item in chart.aspects if item.left not in {"true_node", "chiron", "lilith_mean"} and item.right not in {"true_node", "chiron", "lilith_mean"})
    claim = Claim(
        id="attack", theme="care", type="symbolic_tendency", statement="This proves an absent father.",
        evidence=[aspect.id], evidence_families=["attack"], counterweights=[], allowed_specificity="behavioral_possibility",
        allowed_examples=[], prohibited_inferences=["absent father"], astrological_support="light", authorized_motifs=["invented_motif"],
    )
    verified = verify_claims([claim], chart)[0]
    assert verified.status == "blocked"
    assert "unauthorized_motif_for_evidence" in verified.verification_errors
    assert "prohibited_semantic_inference" in verified.verification_errors


def test_input_models_reject_invalid_uncertainty_and_language():
    with pytest.raises(ValueError):
        BirthData("1990-01-01", "UTC", 0, 0, time_uncertainty_minutes=-1)
    with pytest.raises(ValueError):
        LocalizationProfile(preferred_language="fr-FR")
    with pytest.raises(ValueError, match="wall time"):
        calculate_chart(BirthData("1990-01-01T12:00:00+00:00", "UTC", 0, 0))
    with pytest.raises(ValueError, match="Gregorian"):
        calculate_chart(BirthData("1990-01-01T12:00:00", "UTC", 0, 0, calendar="julian"))


def test_timing_rejects_prebirth_progression_and_unbounded_timeline():
    from astrology.timing import current_progressions
    chart = calculate_chart(birth())
    with pytest.raises(ValueError, match="precede birth"):
        current_progressions(chart, datetime(1980, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="max_age"):
        life_timeline(chart, 121)


def test_unknown_time_withholds_aspects_that_do_not_survive_the_day():
    unknown = BirthData("1990-07-12", "America/Sao_Paulo", -23.5505, -46.6333, birth_time_known=False)
    result = analyse_birth_chart(unknown, include_timing=False)
    unstable = set(result["chart"]["stability"]["unstable_aspect_ids"])
    rendered_evidence = {evidence for claim in result["claims"] if claim["status"] == "allowed" for evidence in claim["evidence"]}
    assert unstable
    assert not unstable & rendered_evidence
    assert result["chart"]["stability"]["allow_house_claims"] is False


def test_large_time_uncertainty_is_an_enforced_gate_not_only_a_warning():
    uncertain = BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333, time_uncertainty_minutes=780)
    result = analyse_birth_chart(uncertain, include_timing=False)
    allowed = [claim for claim in result["claims"] if claim["status"] == "allowed"]
    # A sign-level nodal or aspect configuration may remain available, but
    # canonical Placidus house and angle evidence is withheld at this gate.
    assert not any(any(item.startswith("house.placidus.") for item in claim["evidence"]) for claim in allowed)
    assert not any(item in {"ascendant.natal", "chart_ruler.natal"} for claim in allowed for item in claim["evidence"])


def test_semantic_contract_blocks_forged_theme_family_support_and_text():
    chart = calculate_chart(birth())
    aspect = next(item for item in chart.aspects if item.left not in {"true_node", "chiron", "lilith_mean"} and item.right not in {"true_node", "chiron", "lilith_mean"})
    canonical = _claim_from_aspect(aspect, 1, "pt-BR")
    forged = Claim(
        id="forged", theme="pleasure", type=canonical.type, statement="Você talvez prefira mesas organizadas.",
        evidence=canonical.evidence, evidence_families=["invented_family"], counterweights=[],
        allowed_specificity=canonical.allowed_specificity, allowed_examples=[], prohibited_inferences=[],
        astrological_support="unsupported", authorized_motifs=canonical.authorized_motifs,
    )
    checked = verify_claims([forged], chart)[0]
    assert checked.status == "blocked"
    assert {"noncanonical_evidence_family", "theme_not_authorized_by_evidence", "statement_not_registry_rendered", "invalid_astrological_support"} <= set(checked.verification_errors)


def test_technical_secondary_points_do_not_change_primary_hierarchy():
    from astrology.hierarchy import calculate_hierarchy
    with_secondary = calculate_hierarchy(calculate_chart(birth(), include_secondary=True))
    without_secondary = calculate_hierarchy(calculate_chart(birth(), include_secondary=False))
    assert {body: with_secondary[body] for body in without_secondary} == without_secondary


def test_timeline_builds_only_valid_dynamic_age_containers():
    ranges = [item["range"] for item in life_timeline(calculate_chart(birth()), 50)]
    assert ranges == ["0–9", "10–19", "20–29", "30–39", "40–49", "50–50"]


def test_solar_conditions_do_not_mix_outer_planets_into_traditional_stream():
    chart = calculate_chart(BirthData("1990-01-01T12:00:00", "UTC", 0, 0))
    conditions = {factor.bodies[0]: factor.data["conditions"] for factor in chart.factors if factor.kind == "planetary_condition"}
    for body in ("uranus", "neptune", "pluto", "chiron"):
        assert not {"cazimi", "combust", "under_beams"} & set(conditions.get(body, []))


def test_portuguese_deep_report_localizes_planets_elements_and_configurations():
    deep = analyse_birth_chart(birth(), report_depth="deep", include_timing=False)["report"]
    technical = analyse_birth_chart(birth(), report_depth="technical", include_timing=False)["report"]
    assert "## Onde isso pode ganhar forma concreta" in deep
    assert "## Estrutura e configurações" in technical
    assert "## Hierarquia dinâmica" in technical
    assert "Lilith média" in technical and "VERTEX" in technical and "fortune" in technical
    assert "- fire:" not in deep and "- air:" not in deep
    assert "Moon organiza" not in deep and "Sun organiza" not in deep


def test_house_consultation_returns_direct_system_comparison():
    result = consult(birth(), "Compare Placidus e Signo Inteiro", as_of=datetime(2026, 8, 27, tzinfo=timezone.utc))["consultation"]
    assert "Placidus é a referência natal" in result["answer"]
    assert result["house_comparison"]


def test_compound_privacy_keys_are_redacted():
    redacted = redact_for_logs({"contact_email": "x@example.com", "birth_coordinates": [1, 2], "safe": "ok"})
    assert redacted == {"contact_email": "[redacted]", "birth_coordinates": "[redacted]", "safe": "ok"}
