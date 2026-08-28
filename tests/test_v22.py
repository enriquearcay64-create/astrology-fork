from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from astrology.engine import _house_integration_state, calculate_chart
from astrology.interpretation import build_compensation_hypotheses
from astrology.models import Aspect, BirthData, LocalizationProfile
from astrology.pipeline import analyse_birth_chart, consult
from astrology.semantics import _claim_from_aspect
from astrology.structure import chart_structure
from astrology.config import THEME_LABELS_PT
from astrology.synthesis import POLARITY_THEME_PROFILES, SINGLE_THEME_PROFILES


def birth() -> BirthData:
    return BirthData("1990-07-12T14:30:00", "America/Sao_Paulo", -23.5505, -46.6333)


def test_report_uses_progressive_disclosure_tables_intro_and_final_synthesis():
    report = analyse_birth_chart(birth(), report_depth="deep", include_timing=False)["report"]
    assert "## A arquitetura da pessoa" in report
    assert "## Integração" in report
    assert "| Área | Fatores centrais | Pergunta prática |" in report
    assert "<summary><strong>Ver as doze áreas</strong></summary>" in report
    assert report.count("<details>") == report.count("</details>") >= 4
    assert "recurso, sombra e integração" in report
    assert report.count("> **Na prática:**") == 3


def test_report_balances_logos_and_eros_and_puts_human_meaning_first():
    deep = analyse_birth_chart(birth(), report_depth="deep", include_timing=False)["report"]
    technical = analyse_birth_chart(birth(), report_depth="technical", include_timing=False)["report"]
    assert deep.index("## Temas centrais") < deep.index("## Onde isso pode ganhar forma concreta") < deep.index("## Integração")
    assert "Uma distorção possível" in deep or "Em momentos de maior carga" in deep
    assert "## Claims" not in deep and "## Claims" in technical
    assert "Whole Sign" not in deep.split("## Onde isso pode ganhar forma concreta", 1)[0]
    assert "## Aspectos" in technical and "## Hierarquia dinâmica" in technical


def test_introduction_and_conclusion_do_different_jobs():
    report = analyse_birth_chart(birth(), report_depth="deep", include_timing=False)["report"]
    opening = report.split("## A arquitetura da pessoa", 1)[1].split("## Temas centrais", 1)[0].strip()
    closing = report.split("## Integração", 1)[1].split("## Profundidade opcional", 1)[0].strip()
    assert opening != closing
    assert "A integração mais promissora" in closing


def test_consultation_has_a_human_report_in_addition_to_structured_data():
    result = consult(birth(), "O que o mapa sugere sobre carreira?", as_of=datetime(2026, 8, 27, tzinfo=timezone.utc))
    assert result["consultation"]["claims"]
    assert result["report"].startswith("# Consulta Astrológica")
    assert "## Resposta direta" in result["report"]
    assert "## Síntese e próximo passo" in result["report"]
    assert "## Luz, tensão e integração" in result["report"]
    assert "**Experimento:**" in result["report"]
    assert "Escolha duas opções reais de carreira" in result["report"]
    families = [item["evidence_family"] for item in result["consultation"]["relevant_timing"]]
    assert len(families) == len(set(families))


def test_relationship_consultation_does_not_inject_an_unselected_polarity():
    result = consult(birth(), "O que preciso compreender nos meus relacionamentos?", as_of=datetime(2026, 8, 27, tzinfo=timezone.utc))
    selected = {item["id"] for item in result["consultation"]["focus"]}
    assert selected == {"transformation", "care"}
    assert "necessidade de proximidade e uma de autonomia" not in result["report"]
    assert result["consultation"]["focus"][0]["expressions"]["integrated"] in result["report"]


def test_aspect_kind_is_part_of_generic_motif_and_evidence_family():
    square = _claim_from_aspect(Aspect("a", "moon", "mars", "square", 90, 90, 1, True), 1, "pt-BR")
    trine = _claim_from_aspect(Aspect("b", "moon", "mars", "trine", 120, 120, 1, True), 2, "pt-BR")
    assert square.authorized_motifs != trine.authorized_motifs
    assert square.evidence_families != trine.evidence_families
    assert "Lua" in square.statement and "Marte" in square.statement


def test_same_house_near_cusp_is_qualified_instead_of_overstated():
    assert _house_integration_state(5, 5, {"distance_degrees": 2.5})[0] == "whole_topic_placidus_qualifier"
    assert _house_integration_state(5, 5, {"distance_degrees": 3.5})[0] == "convergence_strong"


def test_balance_uses_sun_through_saturn_and_stellium_basis_is_explicit():
    structure = chart_structure(calculate_chart(birth()))
    assert sum(structure["core_elements"].values()) == 7
    assert sum(structure["all_primary_elements"].values()) == 10
    assert all(item.get("basis") for item in structure["configurations"] if item["kind"].startswith("stellium"))
    hypotheses = build_compensation_hypotheses(structure)
    assert {item["element"] for item in hypotheses} == {element for element in ("fire", "earth", "air", "water") if structure["core_elements"].get(element, 0) <= 1}


def test_portuguese_report_localizes_stellium_basis_and_generic_examples():
    report = analyse_birth_chart(birth(), report_depth="technical", include_timing=False)["report"]
    assert "stellium por signo (Capricórnio)" in report
    assert "stellium por signo (Capricorn)" not in report
    assert "## Hierarquia dinâmica" in report


def test_every_known_theme_has_differentiated_bilingual_editorial_profile():
    for language in ("pt", "en"):
        profiles = {**SINGLE_THEME_PROFILES[language], **POLARITY_THEME_PROFILES[language]}
        assert set(THEME_LABELS_PT) == set(profiles)
        assert all(profile.get("lived_example") for profile in profiles.values())
        constructive = [profile["constructive"] for profile in profiles.values()]
        defensive = [profile["defensive"] for profile in profiles.values()]
        assert len(constructive) == len(set(constructive))
        assert len(defensive) == len(set(defensive))


def test_english_deep_report_never_uses_generic_editorial_fallback_for_known_themes():
    report = analyse_birth_chart(
        birth(), LocalizationProfile(preferred_language="en-US"), report_depth="deep", include_timing=False
    )["report"]
    assert "through context, practice and clear boundaries" not in report
    assert "trainable capacity without demanding perfection" not in report


def test_house_claims_name_both_topologies_when_they_diverge():
    result = analyse_birth_chart(birth(), include_timing=False)
    house_claims = [item for item in result["claims"] if item["type"] == "topical_tendency" and item["status"] == "allowed"]
    divergent = [item for item in house_claims if any(evidence.startswith("house.placidus.") for evidence in item["evidence"]) and "Placidus" in item["statement"]]
    assert divergent
