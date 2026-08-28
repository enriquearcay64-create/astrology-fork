"""Internal QA, ablation and counterfactual helpers.

These checks evaluate technical integrity and report differentiation.  They do
not claim to validate astrology scientifically or substitute human blind tests.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
from hashlib import sha256
from itertools import combinations
from typing import Dict, List, Optional

from .engine import calculate_chart
from .models import BirthData, Factor, LocalizationProfile
from .pipeline import analyse_birth_chart
from .semantics import build_claims, verify_claims
from .synthesis import synthesize_themes


def _summary(claims, themes) -> Dict[str, object]:
    return {
        "claim_count": len([claim for claim in claims if claim.status == "allowed"]),
        "theme_ids": [theme["id"] for theme in themes],
        "evidence_families": sorted({family for claim in claims for family in claim.evidence_families}),
    }


def run_ablations(birth: BirthData, profile: Optional[LocalizationProfile] = None) -> Dict[str, object]:
    chart = calculate_chart(birth)
    language = profile.preferred_language if profile else "pt-BR"
    baseline_claims = verify_claims(build_claims(chart, language=language), chart)
    baseline_themes = synthesize_themes(baseline_claims, language)
    no_placidus_placements = {key: replace(value, placidus_house=None, placidus_position=None, house_system_robustness="unavailable", cusp_proximity=None, integration_state="placidus_unavailable", integration_rationale="Whole Sign remains topical; no Placidus inference is available.") for key, value in chart.house_placements.items()}
    retained_factors = [factor for factor in chart.factors if factor.kind not in {"placidus_house", "house_system_robustness"}]
    retained_factors.extend(
        Factor(f"house.robustness.{key}", "house_synthesis", "house_system_robustness", [key], {"state": "placidus_unavailable", "legacy_state": "unavailable", "whole_sign_house": placement.whole_sign_house, "placidus_house": None, "rationale": placement.integration_rationale})
        for key, placement in no_placidus_placements.items()
    )
    no_placidus = replace(chart, placidus_available=False, house_cusps_placidus=None, house_placements=no_placidus_placements, factors=retained_factors)
    whole_claims = verify_claims(build_claims(no_placidus, language=language), no_placidus)
    whole_themes = synthesize_themes(whole_claims, language)
    without_angles = [claim for claim in baseline_claims if claim.type != "structural_prominence"]
    angle_claims = [claim for claim in baseline_claims if claim.type == "structural_prominence"]
    angle_themes = synthesize_themes(angle_claims, language)
    with_secondary_claims = verify_claims(build_claims(chart, include_secondary_semantics=True, language=language), chart)
    no_secondary_claims = verify_claims(build_claims(chart, include_secondary_semantics=False, language=language), chart)
    no_secondary_themes = synthesize_themes(no_secondary_claims, language)
    motif_family = next((family for claim in baseline_claims for family in claim.evidence_families if family.endswith("_dynamic")), None)
    no_selected_motif = [claim for claim in baseline_claims if motif_family not in claim.evidence_families] if motif_family else list(baseline_claims)
    return {
        "baseline": _summary(baseline_claims, baseline_themes),
        "whole_sign_only": _summary(whole_claims, whole_themes),
        "placidus_only": {"status": "not a supported synthesis mode", "reason": "Whole Sign is the pre-declared topical frame; Placidus-only is retained as technical comparison rather than a silently equivalent reading."},
        "angular_only": _summary(angle_claims, angle_themes),
        "without_angles": _summary(without_angles, synthesize_themes(without_angles, language)),
        "with_modern_secondary_points": _summary(with_secondary_claims, synthesize_themes(with_secondary_claims, language)),
        "without_modern_secondary_points": _summary(no_secondary_claims, no_secondary_themes),
        "without_chiron_lilith_vertex": {"status": "no core change expected", "reason": "These points are technical-only by default."},
        "without_localization": {"theme_ids": [theme["id"] for theme in synthesize_themes(baseline_claims, "en-US")], "reason": "Changing language must not change core theme identifiers."},
        "without_feedback": {"status": "no core change expected", "reason": "Manifestation feedback is not astrological support."},
        "semantic_motif_ablation": {"removed_family": motif_family, **_summary(no_selected_motif, synthesize_themes(no_selected_motif, language))},
        "interpretation": "Ablations expose marginal contribution; they do not establish scientific validity.",
    }


def counterfactual_distinguishability(birth: BirthData, shift_hours: int = 4) -> Dict[str, object]:
    baseline = analyse_birth_chart(birth, include_timing=False)
    shifted_dt = datetime.fromisoformat(birth.local_datetime) + timedelta(hours=shift_hours)
    shifted = replace(birth, local_datetime=shifted_dt.isoformat())
    alternative = analyse_birth_chart(shifted, include_timing=False)
    baseline_houses = {key: value["whole_sign_house"] for key, value in baseline["chart"]["house_placements"].items()}
    alternative_houses = {key: value["whole_sign_house"] for key, value in alternative["chart"]["house_placements"].items()}
    changed_houses = [key for key in baseline_houses if baseline_houses[key] != alternative_houses[key]]
    baseline_themes = set(item["id"] for item in baseline["themes"])
    alternative_themes = set(item["id"] for item in alternative["themes"])
    return {
        "shift_hours": shift_hours,
        "changed_whole_sign_houses": changed_houses,
        "theme_jaccard": round(len(baseline_themes & alternative_themes) / max(1, len(baseline_themes | alternative_themes)), 4),
        "report_identical": baseline["report"] == alternative["report"],
        "pass": bool(changed_houses) and baseline["report"] != alternative["report"],
        "limit": "This is a differentiation guard, not a blind human-matching study.",
    }


def qa_snapshot(birth: BirthData, profile: Optional[LocalizationProfile] = None) -> Dict[str, object]:
    result = analyse_birth_chart(birth, profile, include_timing=False)
    blocked = [claim["id"] for claim in result["claims"] if claim["status"] != "allowed"]
    unknown_evidence = [claim["id"] for claim in result["claims"] if "unknown_evidence" in claim.get("verification_errors", [])]
    return {
        "technical_truth": {"positions": bool(result["chart"]["positions"]), "angles": bool(result["chart"]["angles"]), "methodology_version": result["chart"]["methodology_version"]},
        "methodological_integrity": {"blocked_claims": blocked, "unknown_evidence": unknown_evidence, "robustness_records": len([factor for factor in result["chart"]["factors"] if factor["kind"] == "house_system_robustness"])},
        "narrative_quality": {"report_length": len(result["report"]), "theme_count": len(result["themes"]), "contains_limit": "não diagnostica" in result["report"].casefold()},
    }


def run_synthetic_natal_pilot() -> Dict[str, object]:
    """Run a non-human technical pilot over diverse synthetic birth inputs.

    It deliberately disables localization and timing.  This is a software QA
    surface for crashes, determinism and genericity—not evidence for astrology
    and not a substitute for blind human report matching.
    """
    locations = [
        ("America/Sao_Paulo", -23.5505, -46.6333), ("Europe/Amsterdam", 52.3676, 4.9041),
        ("Asia/Tokyo", 35.6762, 139.6503), ("America/New_York", 40.7128, -74.0060),
        ("Australia/Sydney", -33.8688, 151.2093), ("Africa/Johannesburg", -26.2041, 28.0473),
    ]
    reports: List[str] = []
    theme_sets: List[set] = []
    blocked = 0
    failures: List[str] = []
    for index in range(24):
        zone, latitude, longitude = locations[index % len(locations)]
        year = 1962 + index * 2
        month = index % 12 + 1
        day = min(26, index + 1)
        hour = (index * 5 + 3) % 24
        birth = BirthData(f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:17:00", zone, latitude, longitude, source="synthetic_pilot")
        try:
            result = analyse_birth_chart(birth, report_depth="executive", include_timing=False)
        except Exception as error:  # record, do not conceal a pilot failure
            failures.append(f"case_{index}: {error}")
            continue
        reports.append(result["report"])
        theme_sets.append(set(item["id"] for item in result["themes"]))
        blocked += sum(claim["status"] != "allowed" for claim in result["claims"])
    hashes = {sha256(report.encode("utf-8")).hexdigest() for report in reports}
    similarities = [len(left & right) / max(1, len(left | right)) for left, right in combinations(theme_sets, 2)]
    mean_similarity = sum(similarities) / len(similarities) if similarities else 1.0
    return {
        "type": "synthetic_technical_pilot", "cases_requested": 24, "cases_completed": len(reports), "failures": failures,
        "unique_report_hashes": len(hashes), "blocked_claims": blocked, "mean_theme_jaccard": round(mean_similarity, 4),
        "quality_gate": {
            "pass": len(reports) == 24 and not failures and len(hashes) == 24 and blocked == 0 and mean_similarity < 0.75,
            "criteria": "all cases run; reports differ; no blocked claim reaches rendering; mean theme Jaccard < 0.75",
        },
        "limit": "No human participants, biographies, feedback, report-swap matching or scientific validation were used.",
    }
