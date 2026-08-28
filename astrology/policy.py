"""Public, serialisable methodology policy for reproducible calculations."""
from __future__ import annotations

from typing import Dict

from .config import (
    ANGLE_CLAIM_MAX_UNCERTAINTY_MINUTES, ANGLE_ORB, APPLYING_SAMPLE_MINUTES, ASPECTS,
    CAZIMI_ORB, COMBUST_ORB, DEFAULT_ORBS, DETRIMENTS, EXALTATIONS, FALLS,
    EPHEMERIS_END_YEAR, EPHEMERIS_START_YEAR, METHODOLOGY_VERSION,
    HOUSE_CLAIM_MAX_UNCERTAINTY_MINUTES, LUMINARY_ORB_BONUS, SCHEMA_VERSION,
    SEMANTIC_SUPPORT_THRESHOLDS, SIGN_RULERS, STATIONARY_SPEED_BY_BODY,
    UNDER_BEAMS_ORB, UNKNOWN_TIME_STABLE_BODY_SPAN, SENSITIVITY_STRESS_TEST_MINUTES,
)


def policy_manifest() -> Dict[str, object]:
    """Return every convention that can materially alter an interpretation."""
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "schema_version": SCHEMA_VERSION,
        "semantic_registry_version": "4.0.0-boundaries",
        "timing_version": "4.0.0",
        "report_template_version": "4.0.0-signature-led",
        "zodiac": "tropical",
        "reference_frame": "geocentric",
        "ephemeris_range": [EPHEMERIS_START_YEAR, EPHEMERIS_END_YEAR],
        "node_variant": "true_node",
        "lilith_variant": "mean_lunar_apogee",
        "house_policy": {
            "topical": "whole_sign",
            "spatial": "placidus",
            "angles_independent": True,
            "cusp_qualifier_orb_degrees": 3.0,
            "cusp_qualifier_metric": "Placidus continuous house-position fraction converted to 30-degree equivalent; zodiacal longitude distance retained separately",
            "anti_cherry_picking": True,
            "integration_states": ["robust_same_house", "whole_topic_placidus_qualifier", "complementary_emphases", "material_divergence", "placidus_unavailable"],
            "adjacent_house_is_qualifier": True,
            "opposite_house_pairs_are_complementary": True,
        },
        "aspects": dict(ASPECTS),
        "natal_orbs": dict(DEFAULT_ORBS),
        "luminary_orb_bonus": LUMINARY_ORB_BONUS,
        "angle_orb": ANGLE_ORB,
        "applying_sample_minutes": APPLYING_SAMPLE_MINUTES,
        "stationary_speed_by_body": dict(STATIONARY_SPEED_BY_BODY),
        "solar_condition_orbs": {"cazimi": CAZIMI_ORB, "combust": COMBUST_ORB, "under_beams": UNDER_BEAMS_ORB},
        "solar_condition_bodies": ["mercury", "venus", "mars", "jupiter", "saturn"],
        "time_stability": {
            "unknown_time_stable_body_span_degrees": UNKNOWN_TIME_STABLE_BODY_SPAN,
            "house_claim_max_uncertainty_minutes": HOUSE_CLAIM_MAX_UNCERTAINTY_MINUTES,
            "angle_claim_max_uncertainty_minutes": ANGLE_CLAIM_MAX_UNCERTAINTY_MINUTES,
            "unknown_time_endpoint_policy": "local_00:01_and_23:59_intersection",
            "sensitivity_stress_test_minutes": list(SENSITIVITY_STRESS_TEST_MINUTES),
            "stress_test_policy": "counterfactual stress tests are separate from declared uncertainty; a Whole Sign boundary is a conditional disclosure, never silent house evidence",
        },
        "traditional_rulership": True,
        "sign_rulers": dict(SIGN_RULERS),
        "essential_dignities": {"exaltations": dict(EXALTATIONS), "detriments": dict(DETRIMENTS), "falls": dict(FALLS)},
        "essential_dignity_policy": "traditional_domicile_exaltation_detriment_fall_v2",
        "lots": {"enabled": ["fortune", "spirit"], "formula_policy": "sect-dependent traditional formulas"},
        "secondary_points_core_semantics": False,
        "secondary_points_timing": {"true_node": ["conjunction", "opposition"], "chiron": ["conjunction"], "lilith_mean": []},
        "semantic_support_thresholds": dict(SEMANTIC_SUPPORT_THRESHOLDS),
        "counterweight_policy": "same-body, orb<=4deg, max_one_harmonic_and_one_challenging",
        "configuration_policy": "primary bodies only; exact configured natal aspects; absorb T-squares in grand crosses and grand trines in kites; stellium means 3+ primary bodies in one sign or one Whole Sign house, reported as distinct bases",
        "balance_policy": "element, modality and polarity compensation uses Sun through Saturn; outer planets are disclosed separately and do not drive scarcity hypotheses",
        "retrograde_friction_policy": "Mercury through Saturn may add friction; outer-planet retrogradation is disclosed but does not increase friction scoring",
        "report_design_policy": "portable Markdown; executive/deep/technical separation; signature-led human-first prose with 3–4 non-forced core themes; evidence-led examples; Whole Sign and Placidus differences named only when material; timing translated before technical labels; distinct introduction and synthesis; no decorative animation",
        "timing_orbs": {"major_transits": 1.0, "directed_contacts": 1.0, "life_cycles": 0.7},
        "profection_date_policy": "evaluate birthday in the declared natal local timezone or explicit fixed offset",
    }
