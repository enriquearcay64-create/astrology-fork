"""Single orchestration entrypoint with strict fact-to-language boundaries."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Dict, Iterable, List, Optional

from .consultation import answer_question, classify_question, render_consultation
from .config import (
    LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
    PREMIUM_HANDOFF_CONTRACT_VERSION,
)
from .exceptions import (
    LineageMismatchError,
    SelectionPlanValidationError,
    BenchmarkIntegrityError,
    ReviewerAuthorityBoundaryError,
)
from .engine import calculate_chart
from .hierarchy import calculate_hierarchy
from .interpretation import build_compensation_hypotheses, build_paradoxes
from .localization import localization_audit
from .models import BirthData, Claim, LocalizationProfile, ReasonedSynthesis, to_primitive
from .privacy import record_boundaries
from .report import render_report, technical_appendix
from .reasoning import build_chart_signature, build_narrative_plan, build_natal_timing_interactions, build_reader_domain_manifest, build_reasoning_packet, compose_reasoned_syntheses, humanization_instructions, humanization_verifier_instructions, llm_reasoning_instructions, validate_reasoned_syntheses
from .safe_view import build_safe_interpretive_view
from .semantics import build_claims, verify_claims
from .structure import chart_structure
from .synthesis import synthesize_themes
from .timing import cross_technique_timing, developmental_intervals, life_timeline, upcoming_eclipses


def analyse_birth_chart(
    birth: BirthData,
    profile: Optional[LocalizationProfile] = None,
    report_depth: str = "executive",
    include_timing: bool = True,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
    question_topics: Iterable[int] = (),
    *,
    premium_contract_version: str = PREMIUM_HANDOFF_CONTRACT_VERSION,
) -> Dict[str, object]:
    language = profile.preferred_language if profile else "pt-BR"
    raw_chart = calculate_chart(birth)
    packet_id = _packet_id(
        birth, profile, raw_chart.policy, as_of, horizon_days, include_timing,
        premium_contract_version=premium_contract_version,
    )
    chart = build_safe_interpretive_view(raw_chart)
    semantic_chart = chart.semantic_chart()
    structure = chart_structure(semantic_chart)
    natal_hierarchy = calculate_hierarchy(semantic_chart)
    claims = verify_claims(build_claims(semantic_chart, language=language), semantic_chart)
    # Coverage facts make every required component available to Premium
    # Complete, but they must not mechanically inflate thematic support or
    # flatten hierarchy.  Existing aspect/house/angle synthesis remains the
    # prominence selector; the Author can add a coverage synthesis where it is
    # needed and its paragraph provenance then verifies it.
    thematic_claims = [
        claim for claim in claims
        if claim.id.startswith(("claim.aspect.", "claim.house.", "claim.angle."))
    ]
    themes = synthesize_themes(thematic_claims, language)
    paradoxes = build_paradoxes(themes, language)
    compensations = build_compensation_hypotheses(structure, language)
    timing = cross_technique_timing(semantic_chart, as_of, horizon_days) if include_timing else None
    active_bodies = timing["current_phase"]["active_bodies"] if timing else []
    current_hierarchy = calculate_hierarchy(semantic_chart, question_topics=question_topics, active_bodies=active_bodies) if timing or question_topics else natal_hierarchy
    timeline = life_timeline(semantic_chart) if include_timing and report_depth in ("deep", "technical") else None
    intervals = developmental_intervals(semantic_chart, timeline) if timeline else None
    reasoned_syntheses = compose_reasoned_syntheses(chart, themes, thematic_claims, natal_hierarchy, language)
    chart_signature = build_chart_signature(chart, natal_hierarchy, structure, reasoned_syntheses, language)
    natal_timing_interactions = build_natal_timing_interactions(chart, natal_hierarchy, claims, themes, timing)
    if timing:
        timing["current_phase"]["natal_timing_interactions"] = natal_timing_interactions[:6]
    reasoning_packet = build_reasoning_packet(chart, natal_hierarchy, claims, timing, timeline, intervals, language, profile, packet_id)
    reader_domain_manifest = build_reader_domain_manifest(
        chart, claims, reasoned_syntheses, chart_signature,
        reasoning_packet["facts"]["timing_evidence"], language,
    )
    reasoning_packet["facts"]["reader_domain_manifest"] = reader_domain_manifest
    narrative_plan = build_narrative_plan(themes, reasoned_syntheses, language, chart, chart_signature)
    report = render_report(report_depth, chart, claims, themes, natal_hierarchy, timing, timeline, paradoxes, compensations, structure, profile, reasoned_syntheses, narrative_plan, intervals, chart_signature)
    return {
        "packet_id": packet_id, "premium_handoff_contract_version": premium_contract_version,
        "chart": raw_chart.as_dict(), "safe_interpretive_view": to_primitive(chart), "hierarchy": natal_hierarchy, "current_hierarchy": current_hierarchy,
        "chart_structure": structure, "claims": to_primitive(claims), "themes": themes,
        "paradoxes": paradoxes, "compensation_hypotheses": compensations,
        "reasoned_synthesis": reasoned_syntheses, "chart_signature": chart_signature, "narrative_plan": narrative_plan, "reader_domain_manifest": reader_domain_manifest,
        "reasoning_packet": reasoning_packet, "llm_reasoning_instructions": llm_reasoning_instructions(), "humanization_instructions": humanization_instructions(language),
        "humanization_verifier_instructions": humanization_verifier_instructions(language),
        "timing": timing, "timeline": timeline, "developmental_intervals": intervals,
        "progressions": timing["modern_stream"]["progressions"] if timing else None,
        "solar_arcs": timing["modern_stream"]["solar_arcs"] if timing else None,
        "upcoming_eclipses": upcoming_eclipses(as_of, 4) if include_timing else None,
        "report_mode": "deterministic_fallback", "localization_audit": localization_audit(profile), "privacy_boundaries": record_boundaries(), "report": report,
    }


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(to_primitive(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


_PARAGRAPH_SOURCE_FIELDS = ("paragraph_sha256", "synthesis_ids", "claim_ids", "timing_ids")
_NARRATIVE_BLOCK_SOURCE_FIELDS = ("narrative_block_sha256", "synthesis_ids", "claim_ids", "timing_ids")
_LEGACY_PREMIUM_FIELDS = frozenset({
    "paragraph_sources", "paragraph_sha256", "paragraph_sha256s",
})
_NARRATIVE_PREMIUM_FIELDS = frozenset({
    "narrative_block_sources", "narrative_block_sha256", "narrative_block_sha256s",
})


# This is product copy, not an astrological interpretation. It deliberately
# stays outside the physical prose universe that requires paragraph provenance.
PREMIUM_READER_INTRODUCTIONS = {
    "pt": """### Como entrar nesta leitura

Antes de começar, talvez valha deixar uma coisa de lado: a ideia de que este relatório precisa dizer exatamente quem você é.

Um mapa natal não é uma definição. Ele é mais parecido com um espelho — um jeito de observar algumas das forças, necessidades e contradições que podem existir dentro de você e perceber como elas se encontram na sua forma particular de viver.

Ao longo destas páginas, algumas coisas talvez tragam uma sensação imediata de reconhecimento. Outras podem tocar um lugar que você ainda não tinha colocado em palavras. E algumas simplesmente podem não fazer sentido agora. Não há nada de errado nisso. Você não precisa se encaixar na leitura; é a leitura que precisa encontrar alguma verdade na sua experiência.

Também é natural encontrar aparentes contradições. Podemos querer proximidade e liberdade, segurança e movimento, reconhecimento e silêncio. Essas partes não precisam se anular. Muitas vezes, conhecer-se melhor começa justamente quando deixamos de tentar escolher qual delas é a “verdadeira” e começamos a perceber como todas encontram espaço dentro da mesma pessoa.

Por isso, tente não ler este relatório com a sensação de que precisa entender, concordar ou resolver tudo de uma vez. Dê um pouco de espaço às palavras. Perceba onde algo desperta curiosidade, onde existe identificação, onde surge resistência ou até onde você sente vontade de parar por um momento.

À medida que avançar, talvez alguns temas comecem a aparecer de formas diferentes em áreas diferentes da sua vida. É aí que esta leitura ganha profundidade. Mais do que uma coleção de características, o objetivo é ajudar você a perceber os fios que conectam sua maneira de sentir, pensar, amar, escolher, criar, trabalhar e encontrar direção.

E, acima de tudo, lembre-se de que nenhuma interpretação conhece sua história melhor do que você.

A astrologia pode oferecer uma linguagem para enxergar algo por outro ângulo, mas você continua sendo a pessoa que sabe o que viveu, o que sente e o que faz sentido para a sua vida.

Leia com abertura, mas também com liberdade.

Fique com aquilo que ilumina alguma coisa em você. O restante pode simplesmente permanecer como uma pergunta.""",
    "en": """### How to enter this reading

Before you begin, it may be worth setting one idea aside: that this report needs to tell you exactly who you are.

A natal chart is not a definition. It is more like a mirror — a way to observe some of the forces, needs, and contradictions that may exist within you and notice how they meet in your particular way of living.

As you move through these pages, some things may bring an immediate sense of recognition. Others may touch something you had not yet put into words. And some may simply not make sense right now. There is nothing wrong with that. You do not need to fit the reading; the reading needs to find some truth in your experience.

It is also natural to encounter apparent contradictions. We can want closeness and freedom, safety and movement, recognition and silence. These parts do not need to cancel one another out. Often, knowing ourselves better begins precisely when we stop trying to choose which one is the “real” part and start noticing how all of them can find space within the same person.

So try not to read this report with the feeling that you need to understand, agree with, or resolve everything at once. Give the words a little room. Notice where something sparks curiosity, where there is recognition, where resistance appears, or even where you feel like pausing for a moment.

As you continue, some themes may begin to appear in different forms across different areas of your life. That is where this reading gains depth. More than a collection of traits, its purpose is to help you notice the threads connecting how you feel, think, love, choose, create, work, and find direction.

And above all, remember that no interpretation knows your story better than you do.

Astrology can offer a language for seeing something from another angle, but you remain the person who knows what you have lived, what you feel, and what makes sense for your life.

Read with openness, but also with freedom.

Keep what sheds light on something within you. The rest can simply remain as a question.""",
}
# Backwards-compatible name for the established default locale.
PREMIUM_READER_INTRODUCTION = PREMIUM_READER_INTRODUCTIONS["pt"]


def _premium_reader_introduction(locale: object) -> str:
    normalized_locale = str(locale or "pt-BR").casefold()
    return PREMIUM_READER_INTRODUCTIONS["pt" if normalized_locale.startswith("pt") else "en"]


def _premium_handoff_contract_v13() -> Dict[str, object]:
    """Frozen V4.1.3 contract body used only for legacy replay."""
    return {
        "version": LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
        "author_bundle_required_fields": [
            "packet_id", "premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256",
            "prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256",
            "reasoned_syntheses", "draft_report", "paragraph_sources", "reader_sections", "reader_selection_plan", "reader_selection_plan_sha256",
            "synthesis_bundle_sha256", "draft_report_sha256",
        ],
        "reviewer_bundle_required_fields": [
            "packet_id", "premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256",
            "prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256",
            "synthesis_bundle_sha256", "reviewed_draft_sha256", "verdict", "corrections_made", "remaining_warnings",
            "final_report", "final_report_sha256", "paragraph_sources", "reader_sections", "reader_selection_plan", "reader_selection_plan_sha256", "regeneration_request",
        ],
        "paragraph_source_required_fields": list(_PARAGRAPH_SOURCE_FIELDS),
        "paragraph_source_rules": {
            "synthesis_mode": "one_or_more_approved_synthesis_ids_and_empty_claim_ids",
            "direct_claim_mode": "exactly_one_allowed_direct_paragraph_renderable_claim_id_and_empty_synthesis_ids_and_timing_ids",
            "direct_claim_semantic_boundary": "atomic_placidus_house_ruler_route_only; ruler_context_or_other_composition_requires_approved_reasoned_synthesis",
        },
        "reasoned_synthesis_fields": list(ReasonedSynthesis.__dataclass_fields__),
        "reader_section_rules": {
            "shape": "opening_plus_exactly_16_canonical_domains_plus_integration",
            "ownership": "one_physical_prose_hash_belongs_to_exactly_one_section",
            "unavailable": "exact_deterministic_notice_and_no_prose_hashes",
            "non_prose": "headings_tables_lists_metadata_and_separators_never_satisfy_coverage",
            "fixed_reader_introduction": {
                "sha256_by_language": {
                    language: _canonical_hash(introduction)
                    for language, introduction in PREMIUM_READER_INTRODUCTIONS.items()
                },
                "selection": "reader_domain_manifest_locale",
                "location": "after_an_optional_single_document_title_and_before_the_canonical_opening",
                "provenance": "fixed_product_copy_excluded_from_paragraph_sources_and_reader_section_ownership",
            },
        },
        "timing_domain_rule": "row_timing_ids_equal_cited_synthesis_timing_ids_and_each_id_matches_a_satisfied_timing_natal_path",
        "reader_selection_rule": "every_available_legal_path_is_accounted_once_by_represented_merged_with_represented_or_omitted_no_distinct_reader_value; selection_unions_are_provenance_only",
        "prepared_signature_rule": "pre_domain_chart_signature_and_its_deterministic_synthesis_basis_are_frozen",
        "publication_authority_rule": "original_prepared_handoff_binds_packet_signature_synthesis_basis_manifest_and_materialized_timing_parameters",
    }


def _premium_handoff_contract() -> Dict[str, object]:
    """The current serialized Premium 1.4 source-map contract."""
    return {
        "version": PREMIUM_HANDOFF_CONTRACT_VERSION,
        "author_bundle_required_fields": [
            "packet_id", "premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256",
            "prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256",
            "reasoned_syntheses", "draft_report", "narrative_block_sources", "reader_sections", "reader_selection_plan", "reader_selection_plan_sha256",
            "synthesis_bundle_sha256", "draft_report_sha256",
        ],
        "reviewer_bundle_required_fields": [
            "packet_id", "premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256",
            "prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256",
            "synthesis_bundle_sha256", "reviewed_draft_sha256", "verdict", "corrections_made", "remaining_warnings",
            "final_report", "final_report_sha256", "narrative_block_sources", "reader_sections", "reader_selection_plan", "reader_selection_plan_sha256", "regeneration_request",
        ],
        "author_bundle_exact_shape": True,
        "reviewer_bundle_exact_shape": True,
        "source_row_required_fields": list(_NARRATIVE_BLOCK_SOURCE_FIELDS),
        "paragraph_source_fields": "legacy_replay_only",
        "narrative_block_source_rules": {
            "paragraph": "one source row; direct Claim or synthesis mode; coverage-eligible",
            "list_item": "one source row; ordered or unordered; direct Claim or synthesis mode; coverage-eligible",
            "subheading": "one approved synthesis-only source row; timing IDs must belong to cited syntheses; coverage-ineligible",
        },
        "reader_block_parser": {
            "recognised": ["paragraph", "list_item", "subheading", "canonical_h2", "unavailable_notice"],
            "list_styles": ["ordered", "unordered"],
            "forbidden": ["nested_list", "table", "blockquote", "html_block", "code_fence", "separator", "metadata", "h4_plus"],
            "attached_bullets": "split into independent list_item blocks",
        },
        "reasoned_synthesis_fields": list(ReasonedSynthesis.__dataclass_fields__),
        "reader_section_rules": {
            "shape": "opening_plus_exactly_16_canonical_domains_plus_integration",
            "ownership": "every authored paragraph, list item and subheading hash belongs to exactly one section in physical order",
            "opening_and_integration_fields": ["narrative_block_sha256s"],
            "domain_fields": ["domain_id", "narrative_block_sha256s"],
            "unavailable": "exact_deterministic_notice and no authored blocks or source rows",
            "non_prose": "headings, unavailable notices, tables, metadata and separators never satisfy coverage",
            "fixed_reader_introduction": {
                "sha256_by_language": {
                    language: _canonical_hash(introduction)
                    for language, introduction in PREMIUM_READER_INTRODUCTIONS.items()
                },
                "selection": "reader_domain_manifest_locale",
                "location": "after_an_optional_single_document_title_and_before_the_canonical_opening",
                "provenance": "fixed_product_copy_excluded_from_narrative_block_sources_and_reader_section_ownership",
            },
        },
        "timing_domain_rule": "paragraph_and_list_item timing_ids equal the cited timing synthesis IDs and each ID matches a satisfied timing_natal path; subheading timing IDs belong to cited syntheses",
        "reader_selection_rule": "every_available_legal_path_is_accounted_once_by_represented_merged_with_represented_or_omitted_no_distinct_reader_value; only paragraph and list_item provenance participates",
        "reader_selection_plan_version": "1.0",
        "prepared_signature_rule": "pre_domain_chart_signature_and_its_deterministic_synthesis_basis_are_frozen",
        "publication_authority_rule": "original_prepared_handoff_binds_packet_signature_synthesis_basis_manifest_and_materialized_timing_parameters",
    }


def _premium_handoff_contract_for_version(version: str) -> Dict[str, object]:
    if version == PREMIUM_HANDOFF_CONTRACT_VERSION:
        return _premium_handoff_contract()
    if version == LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION:
        return _premium_handoff_contract_v13()
    raise ValueError(f"unsupported Premium handoff contract version: {version}")


def _packet_id(
    birth: BirthData,
    profile: Optional[LocalizationProfile],
    policy: Dict[str, object],
    as_of: Optional[datetime],
    horizon_days: int,
    include_timing: bool,
    *,
    premium_contract_version: str = PREMIUM_HANDOFF_CONTRACT_VERSION,
) -> str:
    """Identity for one methodologically meaningful premium calculation."""
    if premium_contract_version not in {
        PREMIUM_HANDOFF_CONTRACT_VERSION,
        LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
    }:
        raise ValueError(f"unsupported Premium handoff contract version: {premium_contract_version}")
    return _canonical_hash({
        "birth": to_primitive(birth), "localization_profile": to_primitive(profile) if profile else None,
        "versions": {
            **{key: policy.get(key) for key in ("methodology_version", "schema_version", "semantic_registry_version", "timing_version")},
            "premium_handoff_contract_version": premium_contract_version,
        },
        "as_of": as_of.isoformat() if as_of else None, "horizon_days": horizon_days, "include_timing": include_timing,
    })


def consult(birth: BirthData, question: str, profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None) -> Dict[str, object]:
    intent = classify_question(question)
    core = analyse_birth_chart(birth, profile, "executive", True, as_of, question_topics=intent["houses"])
    language = profile.preferred_language if profile else "pt-BR"
    answer = answer_question(question, [Claim(**claim) for claim in core["claims"]], language, core["timing"], core["current_hierarchy"], core["safe_interpretive_view"], core["themes"], core["reasoned_synthesis"], core["chart_signature"])
    return {"question": question, "consultation": answer, "report": render_consultation(question, answer, language), "methodology_version": core["chart"]["methodology_version"], "query_hierarchy": core["current_hierarchy"], "timing": core["timing"]}


def prepare_premium_handoff(birth: BirthData, profile: Optional[LocalizationProfile] = None, report_depth: str = "deep", include_timing: bool = True, as_of: Optional[datetime] = None, horizon_days: int = 366) -> Dict[str, object]:
    """Debug handoff; normal Codex use follows the same stages internally."""
    _require_premium_birth_time(birth)
    if report_depth != "deep":
        raise ValueError("Premium Complete preparation requires report_depth='deep'.")
    effective_as_of = as_of
    if include_timing and effective_as_of is None:
        effective_as_of = datetime.now(timezone.utc)
    core = analyse_birth_chart(birth, profile, "deep", include_timing, effective_as_of, horizon_days)
    handoff_chart = build_safe_interpretive_view(calculate_chart(birth))
    handoff_contract = _premium_handoff_contract()
    handoff_contract_hash = _canonical_hash(handoff_contract)
    prepared_signature_hash = _canonical_hash(core["chart_signature"])
    prepared_synthesis_hash = _canonical_hash(core["reasoned_synthesis"])
    manifest = core["reader_domain_manifest"]
    manifest_hash = _canonical_hash(manifest)
    reader_introduction = _premium_reader_introduction(manifest.get("locale"))

    # Authentically validate composed domain syntheses against chart claims
    facts = core["reasoning_packet"].get("facts", {})
    claims_list = (
        facts.get("allowed_claims")
        or core.get("claims")
        or []
    )
    claims_dict = {str(item["id"]): item for item in claims_list if isinstance(item, dict)}
    coverage = facts.get("coverage", {})
    composed_synths, _, _ = compose_canonical_domain_syntheses(claims_dict, manifest, coverage)
    synth_items = [
        ReasonedSynthesis(**{k: v for k, v in item.items() if k in set(ReasonedSynthesis.__dataclass_fields__)})
        for item in composed_synths
    ]
    timing_ids = [item["id"] for item in facts.get("timing_evidence", [])]
    claims_objs = [Claim(**item) for item in claims_dict.values()]
    validated_synths = validate_reasoned_syntheses(synth_items, handoff_chart, claims_objs, timing_ids)
    approved_domain_synths = [to_primitive(item) for item in validated_synths if item.status == "allowed"]

    seen_ids = set()
    approved_reasoned_syntheses = []
    for item in [*approved_domain_synths, *core["reasoned_synthesis"]]:
        if isinstance(item, dict) and item.get("id") not in seen_ids:
            seen_ids.add(item.get("id"))
            approved_reasoned_syntheses.append(item)

    candidate_catalog = build_selection_candidate_catalog(
        manifest=manifest,
        approved_syntheses=approved_reasoned_syntheses,
        packet_id=core["packet_id"],
    )

    return {
        "stage": "reasoning_packet_ready",
        "premium_report_depth": "deep",
        "packet_id": core["packet_id"],
        "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION,
        "premium_handoff_contract": handoff_contract,
        "premium_handoff_contract_sha256": handoff_contract_hash,
        "preparation_parameters": {
            "effective_as_of": effective_as_of.isoformat() if effective_as_of else None,
            "horizon_days": horizon_days,
            "include_timing": include_timing,
        },
        "prepared_chart_signature_sha256": prepared_signature_hash,
        "prepared_signature_synthesis_sha256": prepared_synthesis_hash,
        "prepared_signature_syntheses": core["reasoned_synthesis"],
        "approved_reasoned_syntheses": approved_reasoned_syntheses,
        "candidate_catalog": candidate_catalog,
        "candidate_catalog_sha256": candidate_catalog["catalog_sha256"],
        "reader_domain_manifest": manifest,
        "reader_domain_manifest_sha256": manifest_hash,
        "reader_introduction": reader_introduction,
        "reader_introduction_sha256": _canonical_hash(reader_introduction),
        "premium_required_for_publication": True,
        "deterministic_fallback_notice": "The local fallback is useful for tests and debugging. Do not label it as the premium report without the two High review passes.",
        "workflow": [
            "1. deterministic calculation and packet identity", "2. Premium Author creates one AuthorBundle", "3. Deterministic Provenance Guard",
            "4. independent Premium Reviewer edits to ReviewerBundle", "5. Publication Guard", "6. publish only if both guards pass",
        ],
        "reasoning_packet": core["reasoning_packet"],
        "chart_signature": core["chart_signature"],
        "narrative_plan": core["narrative_plan"],
        "timing": core["timing"],
        "timeline": core["timeline"],
        "developmental_intervals": core["developmental_intervals"],
        # The client appendix is concise deterministic reference data; the
        # established full technical renderer remains an internal audit sidecar.
        "technical_appendix": technical_appendix(handoff_chart, core["hierarchy"], [], core["timing"], core["chart_structure"], profile),
        "audit_sidecar": render_report("technical", handoff_chart, [], [], core["hierarchy"], core["timing"], core["timeline"], [], [], core["chart_structure"], profile, [], core["narrative_plan"], core["developmental_intervals"], core["chart_signature"]),
        "reasoned_synthesis_schema": list(ReasonedSynthesis.__dataclass_fields__),
        "author_bundle_contract": {"packet_id": core["packet_id"], "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": handoff_contract, "premium_handoff_contract_sha256": handoff_contract_hash, "prepared_chart_signature_sha256": prepared_signature_hash, "prepared_signature_synthesis_sha256": prepared_synthesis_hash, "reader_domain_manifest_sha256": manifest_hash, "reasoned_syntheses": "list[ReasonedSynthesis]", "draft_report": "string", "narrative_block_sources": [{"narrative_block_sha256": "sha256", "synthesis_ids": ["reasoned.id"], "claim_ids": ["claim.id"], "timing_ids": ["timing.activation.id"]}], "reader_sections": "opening + canonical domains + integration", "reader_selection_plan": "canonical ReaderSelectionPlan", "reader_selection_plan_sha256": "sha256", "synthesis_bundle_sha256": "sha256", "draft_report_sha256": "sha256"},
        "reviewer_bundle_contract": {"packet_id": core["packet_id"], "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": handoff_contract, "premium_handoff_contract_sha256": handoff_contract_hash, "prepared_chart_signature_sha256": prepared_signature_hash, "prepared_signature_synthesis_sha256": prepared_synthesis_hash, "reader_domain_manifest_sha256": manifest_hash, "synthesis_bundle_sha256": "sha256", "reviewed_draft_sha256": "sha256", "verdict": "approved|regenerate_author|blocked", "corrections_made": ["string"], "remaining_warnings": ["string"], "final_report": "string", "final_report_sha256": "sha256", "narrative_block_sources": "same mapping contract", "reader_sections": "same ownership contract", "reader_selection_plan": "same validated canonical ReaderSelectionPlan", "reader_selection_plan_sha256": "sha256", "regeneration_request": "null or canonical regeneration request"},
        "sol_high_instruction": llm_reasoning_instructions(),
        "author_voice_instruction": core["humanization_instructions"],
        "narrative_judge_instruction": humanization_verifier_instructions(profile.preferred_language if profile else "pt-BR"),
    }


def validate_premium_syntheses(
    birth: BirthData,
    synthesis_payload: Iterable[Dict[str, object]],
    profile: Optional[LocalizationProfile] = None,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
    include_timing: bool = True,
    *,
    premium_contract_version: str = PREMIUM_HANDOFF_CONTRACT_VERSION,
) -> Dict[str, object]:
    """Deterministically gate manually authored High syntheses; no API call."""
    core = analyse_birth_chart(
        birth, profile, "deep", include_timing, as_of, horizon_days,
        premium_contract_version=premium_contract_version,
    )
    allowed_fields = set(ReasonedSynthesis.__dataclass_fields__)
    items = [ReasonedSynthesis(**{key: value for key, value in item.items() if key in allowed_fields}) for item in synthesis_payload]
    chart = build_safe_interpretive_view(calculate_chart(birth))
    timing_ids = [item["id"] for item in core["reasoning_packet"]["facts"]["timing_evidence"]]
    checked = validate_reasoned_syntheses(items, chart, [Claim(**claim) for claim in core["claims"]], timing_ids)
    approved = [to_primitive(item) for item in checked if item.status == "allowed"]
    reader_introduction = _premium_reader_introduction(core["reader_domain_manifest"].get("locale"))
    return {
        "stage": "provenance_syntheses_checked", "packet_id": core["packet_id"],
        "premium_handoff_contract_version": premium_contract_version,
        "approved": len(approved) == len(checked),
        "reasoned_synthesis": [to_primitive(item) for item in checked], "approved_reasoned_syntheses": approved,
        "synthesis_bundle_sha256": _canonical_hash(approved),
        # Selection is frozen before Author coverage synthesis.  Approved
        # Author material remains usable for interpretation and provenance but
        # never becomes a new structural vote.
        "chart_signature": core["chart_signature"], "narrative_plan": core["narrative_plan"],
        "prepared_chart_signature_sha256": _canonical_hash(core["chart_signature"]),
        "prepared_signature_synthesis_sha256": _canonical_hash(core["reasoned_synthesis"]),
        "prepared_signature_syntheses": core["reasoned_synthesis"],
        "reader_domain_manifest": core["reader_domain_manifest"],
        "reader_domain_manifest_sha256": _canonical_hash(core["reader_domain_manifest"]),
        "reader_introduction": reader_introduction,
        "reader_introduction_sha256": _canonical_hash(reader_introduction),
        "premium_handoff_contract": _premium_handoff_contract_for_version(premium_contract_version),
        "premium_handoff_contract_sha256": _canonical_hash(_premium_handoff_contract_for_version(premium_contract_version)),
        "timing_evidence_ids": timing_ids,
        "allowed_claims": [claim for claim in core["claims"] if claim.get("status") == "allowed"],
        "coverage": core["reasoning_packet"]["facts"]["coverage"],
        "next_step": "A Premium Reviewer may use only approved syntheses and typed timing IDs; prepared centrality is frozen.",
    }


def _substantive_paragraphs(report: str) -> List[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", report) if block.strip()]
    skipped = ("#", "---", "*leitura simbólica", "*symbolic reading", "> **percurso", "> **path")
    result = []
    for block in blocks:
        folded = block.casefold()
        if folded.startswith(skipped) or block.startswith("|") or all(line.lstrip().startswith("-") for line in block.splitlines()):
            continue
        if len(re.findall(r"\w+", block)) >= 12:
            result.append(block)
    return result


def _parse_premium_narrative_v13(report: object, manifest: object) -> Dict[str, object]:
    """Frozen V4.1.3 paragraph parser used only for legacy replay."""
    if not isinstance(report, str) or not report.strip():
        return {"errors": ["missing_final_report"], "prose": [], "sections": {}}
    if not isinstance(manifest, dict) or not isinstance(manifest.get("domains"), list):
        return {"errors": ["missing_reader_domain_manifest"], "prose": [], "sections": {}}
    expected = [
        ("opening", str(manifest.get("opening", {}).get("heading", ""))),
        *[(str(item.get("id")), str(item.get("heading", ""))) for item in manifest["domains"]],
        ("integration", str(manifest.get("integration", {}).get("heading", ""))),
    ]
    heading_to_key = {heading: key for key, heading in expected}
    notice_to_domain = {
        str(item["unavailable_notice"]["text"]): str(item["id"])
        for item in manifest["domains"] if item.get("unavailable_notice")
    }
    sections = {key: {"heading": heading, "prose": [], "notices": []} for key, heading in expected}
    blocks = [block.strip() for block in re.split(r"\n\s*\n", report) if block.strip()]
    errors: List[str] = []
    reader_introduction = _premium_reader_introduction(manifest.get("locale"))
    introduction_blocks = tuple(
        block.strip() for block in re.split(r"\n\s*\n", reader_introduction) if block.strip()
    )
    introduction_start = 0
    if blocks and blocks[0].startswith("# ") and len(blocks[0].splitlines()) == 1:
        introduction_start = 1
    introduction_end = introduction_start + len(introduction_blocks)
    if tuple(blocks[introduction_start:introduction_end]) == introduction_blocks:
        blocks = blocks[introduction_end:]
    else:
        # The introduction may not be authored, edited, duplicated, or
        # preceded by arbitrary prose. Retain the previous outside-reader
        # signal so this narrow grammar cannot create a pre-opening escape hatch.
        expected_intro_later = any(
            tuple(blocks[index:index + len(introduction_blocks)]) == introduction_blocks
            for index in range(introduction_start + 1, len(blocks))
        )
        known_introduction_headings = {
            introduction.splitlines()[0] for introduction in PREMIUM_READER_INTRODUCTIONS.values()
        }
        starts_intro_heading = bool(
            blocks[introduction_start:introduction_start + 1]
            and blocks[introduction_start].splitlines()[0] in known_introduction_headings
        )
        if expected_intro_later:
            errors.append("invalid_premium_document_preamble")
        elif starts_intro_heading:
            errors.append("invalid_premium_reader_introduction")
        elif blocks[introduction_start:introduction_start + 1] and not blocks[introduction_start].startswith("## "):
            errors.extend(["invalid_premium_document_preamble", "reader_prose_outside_canonical_section"])
        else:
            errors.append("missing_premium_reader_introduction")
        # Continue parsing physical blocks to surface all structural failures.
        blocks = blocks[introduction_start:]
    current: Optional[str] = None
    seen_headings: List[str] = []
    all_hashes: set[str] = set()
    prose = []
    metadata_prefixes = ("*leitura simbólica", "*symbolic reading", "> **percurso", "> **path")
    for block in blocks:
        lines = block.splitlines()
        if lines[0].startswith("## "):
            if len(lines) != 1:
                errors.append("premium_heading_must_be_isolated")
                continue
            heading = lines[0][3:].strip()
            key = heading_to_key.get(heading)
            if key is None:
                errors.append("unknown_reader_section_heading")
                current = None
                continue
            if key in seen_headings:
                errors.append("duplicate_reader_section_heading")
            seen_headings.append(key)
            current = key
            continue
        if lines[0].startswith("#"):
            errors.append("noncanonical_heading_inside_reader_section" if current is not None else "noncanonical_narrative_block")
            continue
        if block == "---":
            if current is not None:
                errors.append("nonprose_content_inside_reader_section")
            else:
                errors.append("noncanonical_narrative_block")
            continue
        folded = block.casefold()
        if folded.startswith(metadata_prefixes):
            if current is not None:
                errors.append("metadata_inside_reader_section")
            continue
        is_table = lines[0].lstrip().startswith("|")
        is_list = bool(re.match(r"^\s*(?:[-*+] |\d+[.)] )", lines[0]))
        if is_table or is_list:
            if current is not None:
                errors.append("nonprose_content_inside_reader_section")
            continue
        notice_domain = notice_to_domain.get(block)
        if notice_domain is not None:
            if current != notice_domain:
                errors.append("unavailable_notice_in_wrong_section")
            elif current is not None:
                sections[current]["notices"].append({"text": block, "sha256": hashlib.sha256(block.encode("utf-8")).hexdigest()})
            continue
        if current is None:
            errors.append("reader_prose_outside_canonical_section")
            continue
        paragraph_hash = _canonical_hash(block)
        if paragraph_hash in all_hashes:
            errors.append("duplicate_narrative_paragraph_hash")
        all_hashes.add(paragraph_hash)
        entry = {"text": block, "sha256": paragraph_hash, "section": current}
        sections[current]["prose"].append(entry)
        prose.append(entry)
    expected_keys = [key for key, _heading in expected]
    if seen_headings != expected_keys:
        if set(seen_headings) != set(expected_keys):
            errors.append("missing_reader_section_heading")
        else:
            errors.append("reader_section_heading_order_mismatch")
    return {
        "errors": list(dict.fromkeys(errors)),
        "reader_introduction": {"text": reader_introduction, "sha256": _canonical_hash(reader_introduction)},
        "prose": prose,
        "sections": sections,
    }


def _normalize_narrative_block_content(content: str) -> str:
    """Normalize only transport whitespace and Markdown continuation indent."""
    if not isinstance(content, str):
        raise TypeError("narrative block content must be a string")
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ""
    lines[0] = lines[0].lstrip(" \t")
    lines[-1] = lines[-1].rstrip(" \t")
    for index in range(1, len(lines)):
        # Indentation on continuation lines is Markdown syntax.  Inline
        # Markdown and all non-leading text remain byte-for-byte meaningful.
        lines[index] = re.sub(r"^[ \t]+", "", lines[index])
    return "\n".join(lines).strip()


def canonical_narrative_block_payload(kind: str, content: str, list_style: Optional[str] = None) -> Dict[str, object]:
    """Return the one canonical payload used to identify a 1.4 narrative block."""
    if kind not in {"paragraph", "list_item", "subheading"}:
        raise ValueError(f"unsupported narrative block kind: {kind}")
    normalized = _normalize_narrative_block_content(content)
    if not normalized:
        raise ValueError("narrative block content cannot be empty")
    if kind == "list_item":
        if list_style not in {"ordered", "unordered"}:
            raise ValueError("list_item requires list_style ordered or unordered")
        return {"kind": "list_item", "list_style": list_style, "content": normalized}
    if list_style is not None:
        raise ValueError(f"{kind} cannot include list_style")
    return {"kind": kind, "content": normalized}


def _narrative_block_entry(kind: str, content: str, section: str, list_style: Optional[str] = None) -> Dict[str, object]:
    payload = canonical_narrative_block_payload(kind, content, list_style)
    block_hash = _canonical_hash(payload)
    return {
        "kind": kind,
        **({"list_style": list_style} if kind == "list_item" else {}),
        "content": payload["content"],
        # ``text`` and ``sha256`` are parser conveniences only.  Contract 1.4
        # source rows and ownership use the explicit narrative names below.
        "text": payload["content"],
        "narrative_block_sha256": block_hash,
        "sha256": block_hash,
        "section": section,
    }


def _narrative_nonblank_blocks(lines: List[str]) -> List[Dict[str, object]]:
    blocks: List[Dict[str, object]] = []
    current: List[str] = []
    start = 0
    for index, line in enumerate(lines):
        if not line.strip():
            if current:
                blocks.append({"lines": current, "start": start, "end": index})
                current = []
            continue
        if not current:
            start = index
        current.append(line.rstrip(" \t"))
    if current:
        blocks.append({"lines": current, "start": start, "end": len(lines)})
    return blocks


def _narrative_heading_kind(line: str) -> Optional[str]:
    stripped = line.strip()
    if re.match(r"^#{4,}(?:\s|$)", stripped):
        return "h4_plus"
    if re.match(r"^###(?:\s|$)", stripped):
        return "h3"
    if re.match(r"^##(?:\s|$)", stripped):
        return "h2"
    if re.match(r"^#(?:\s|$)", stripped):
        return "h1"
    return None


def _narrative_list_marker(line: str) -> Optional[tuple[str, str, str]]:
    match = re.match(r"^(\s*)([-+*]|\d+[.)])(?:\s+)(.*)$", line)
    if not match:
        return None
    indent, marker, content = match.groups()
    style = "ordered" if marker[0].isdigit() else "unordered"
    return indent, style, content


def _narrative_forbidden_kind(line: str) -> Optional[str]:
    stripped = line.strip()
    folded = stripped.casefold()
    if re.match(r"^(?:```+|~~~+)", stripped):
        return "code_fence"
    if stripped in {"---", "***", "___"}:
        return "separator"
    if stripped.startswith(">"):
        return "blockquote"
    if stripped.startswith("|") or re.match(r"^\|?\s*:?-{3,}:?\s*(?:\||$)", stripped):
        return "table"
    if folded.startswith(("<!--", "<details", "</details", "<summary", "*leitura simbólica", "*symbolic reading", "yaml:", "metadata:")):
        return "metadata" if not folded.startswith("<") else "html_block"
    if stripped.startswith("<") and re.match(r"^</?[A-Za-z][^>]*>|^<!--", stripped):
        return "html_block"
    return None


def _parse_premium_narrative(report: object, manifest: object) -> Dict[str, object]:
    """Parse the closed, line-aware Premium 1.4 narrative block universe."""
    if not isinstance(report, str) or not report.strip():
        return {"errors": ["missing_final_report"], "prose": [], "authored": [], "subheadings": [], "sections": {}}
    if not isinstance(manifest, dict) or not isinstance(manifest.get("domains"), list):
        return {"errors": ["missing_reader_domain_manifest"], "prose": [], "authored": [], "subheadings": [], "sections": {}}

    expected = [
        ("opening", str(manifest.get("opening", {}).get("heading", ""))),
        *[(str(item.get("id")), str(item.get("heading", ""))) for item in manifest["domains"]],
        ("integration", str(manifest.get("integration", {}).get("heading", ""))),
    ]
    heading_to_key = {heading: key for key, heading in expected}
    domain_by_id = {str(item.get("id")): item for item in manifest["domains"] if isinstance(item, dict)}
    notice_to_domain = {
        str(item["unavailable_notice"]["text"]): str(item["id"])
        for item in manifest["domains"]
        if isinstance(item, dict) and item.get("unavailable_notice")
    }
    sections: Dict[str, Dict[str, object]] = {
        key: {"heading": heading, "authored": [], "prose": [], "subheadings": [], "notices": []}
        for key, heading in expected
    }
    errors: List[str] = []
    all_hashes: set[str] = set()
    authored: List[Dict[str, object]] = []
    eligible: List[Dict[str, object]] = []
    subheadings: List[Dict[str, object]] = []

    def add_error(value: str) -> None:
        errors.append(value)

    normalized_report = report.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip(" \t") for line in normalized_report.split("\n")]
    blocks = _narrative_nonblank_blocks(lines)
    reader_introduction = _premium_reader_introduction(manifest.get("locale"))
    introduction_blocks = _narrative_nonblank_blocks(
        [line.rstrip(" \t") for line in reader_introduction.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    )

    def block_text(block: Dict[str, object]) -> str:
        return _normalize_narrative_block_content("\n".join(block["lines"]))

    intro_texts = [block_text(block) for block in introduction_blocks]
    intro_start = 0
    title_end = 0
    if blocks and _narrative_heading_kind(str(blocks[0]["lines"][0])) == "h1" and len(blocks[0]["lines"]) == 1:
        intro_start = 1
        title_end = int(blocks[0]["end"])
    candidate = [block_text(block) for block in blocks[intro_start:intro_start + len(intro_texts)]]
    if candidate == intro_texts and len(candidate) == len(intro_texts):
        intro_end = int(blocks[intro_start + len(intro_texts) - 1]["end"]) if intro_texts else title_end
        main_lines = lines[intro_end:]
    else:
        expected_intro_later = any(
            [block_text(block) for block in blocks[index:index + len(intro_texts)]] == intro_texts
            for index in range(intro_start + 1, len(blocks))
        )
        known_headings = {introduction.splitlines()[0] for introduction in PREMIUM_READER_INTRODUCTIONS.values()}
        starts_intro_heading = bool(
            blocks[intro_start:intro_start + 1]
            and str(blocks[intro_start]["lines"][0]) in known_headings
        )
        if expected_intro_later:
            add_error("invalid_premium_document_preamble")
        elif starts_intro_heading:
            add_error("invalid_premium_reader_introduction")
        elif blocks[intro_start:intro_start + 1] and not str(blocks[intro_start]["lines"][0]).startswith("## "):
            errors.extend(["invalid_premium_document_preamble", "reader_prose_outside_canonical_section"])
        else:
            add_error("missing_premium_reader_introduction")
        main_lines = lines[title_end:]

    current: Optional[str] = None
    seen_headings: List[str] = []
    pending_subheading: Optional[Dict[str, object]] = None

    def finish_pending() -> None:
        nonlocal pending_subheading
        if pending_subheading is not None:
            add_error("subheading_requires_child_narrative_block")
            pending_subheading = None

    def report_forbidden(kind: str) -> None:
        add_error(f"prohibited_narrative_{kind}")
        if current is not None:
            add_error("nonprose_content_inside_reader_section")
        else:
            add_error("noncanonical_narrative_block")

    def add_authored(kind: str, content: str, list_style: Optional[str] = None) -> None:
        nonlocal pending_subheading
        if current is None:
            add_error("reader_prose_outside_canonical_section")
            return
        try:
            entry = _narrative_block_entry(kind, content, current, list_style)
        except (TypeError, ValueError):
            add_error("empty_narrative_block")
            return
        block_hash = str(entry["narrative_block_sha256"])
        if block_hash in all_hashes:
            add_error("duplicate_narrative_block_hash")
        all_hashes.add(block_hash)
        sections[current]["authored"].append(entry)
        authored.append(entry)
        if kind in {"paragraph", "list_item"}:
            sections[current]["prose"].append(entry)
            eligible.append(entry)
            if pending_subheading is not None:
                pending_subheading = None
        else:
            sections[current]["subheadings"].append(entry)
            subheadings.append(entry)
            pending_subheading = entry

    def add_paragraph_or_notice(content: str) -> None:
        normalized = _normalize_narrative_block_content(content)
        if not normalized:
            return
        notice_domain = notice_to_domain.get(normalized)
        if notice_domain is not None:
            notice_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            if current != notice_domain:
                add_error("unavailable_notice_in_wrong_section")
            elif current is not None:
                sections[current]["notices"].append({"text": normalized, "sha256": notice_hash})
            return
        add_authored("paragraph", normalized)

    def is_heading_at(index: int) -> bool:
        return _narrative_heading_kind(main_lines[index]) is not None

    def is_top_level_list(line: str) -> bool:
        marker = _narrative_list_marker(line)
        return bool(marker and not marker[0])

    index = 0
    while index < len(main_lines):
        line = main_lines[index]
        if not line.strip():
            index += 1
            continue

        heading_kind = _narrative_heading_kind(line)
        if heading_kind is not None:
            finish_pending()
            isolated = (
                (index == 0 or not main_lines[index - 1].strip())
                and (index + 1 >= len(main_lines) or not main_lines[index + 1].strip())
            )
            if not isolated:
                add_error("premium_heading_must_be_isolated")
            if heading_kind == "h2":
                heading = line.strip()[3:].strip()
                key = heading_to_key.get(heading)
                if key is None:
                    add_error("unknown_reader_section_heading")
                    current = None
                else:
                    if key in seen_headings:
                        add_error("duplicate_reader_section_heading")
                    seen_headings.append(key)
                    current = key
            elif heading_kind == "h3":
                match = re.match(r"^###(?:\s+(.*))?$", line.strip())
                content = (match.group(1) if match else "") or ""
                if not content.strip():
                    add_error("empty_subheading")
                if current is None:
                    add_error("subheading_outside_canonical_section")
                elif current in {"opening", "integration"}:
                    add_error("subheading_not_allowed_in_layer")
                elif domain_by_id.get(current, {}).get("availability") != "available":
                    add_error(f"subheading_in_unavailable_reader_domain:{current}")
                add_authored("subheading", content or "_")
            elif heading_kind == "h4_plus":
                report_forbidden("h4_plus")
            else:
                add_error("noncanonical_heading_inside_reader_section" if current is not None else "noncanonical_narrative_block")
            index += 1
            continue

        forbidden = _narrative_forbidden_kind(line)
        if forbidden is not None:
            report_forbidden(forbidden)
            if forbidden == "code_fence":
                fence = re.match(r"^\s*(`{3,}|~{3,})", line)
                fence_token = fence.group(1)[0] if fence else "`"
                index += 1
                while index < len(main_lines):
                    if re.match(rf"^\s*{re.escape(fence_token)}{{3,}}", main_lines[index]):
                        index += 1
                        break
                    index += 1
            else:
                index += 1
            continue

        marker = _narrative_list_marker(line)
        if marker and not marker[0]:
            _indent, style, content = marker
            if not content.strip():
                add_error("empty_list_item")
            item_lines = [content]
            index += 1
            while index < len(main_lines) and main_lines[index].strip():
                if is_heading_at(index) or is_top_level_list(main_lines[index]):
                    break
                continuation_marker = _narrative_list_marker(main_lines[index])
                if continuation_marker and continuation_marker[0]:
                    report_forbidden("nested_list")
                    index += 1
                    continue
                continuation_forbidden = _narrative_forbidden_kind(main_lines[index])
                if continuation_forbidden is not None:
                    report_forbidden(continuation_forbidden)
                    index += 1
                    continue
                item_lines.append(main_lines[index])
                index += 1
            add_authored("list_item", "\n".join(item_lines), style)
            continue

        paragraph_lines: List[str] = []
        while index < len(main_lines) and main_lines[index].strip():
            if is_heading_at(index) or is_top_level_list(main_lines[index]):
                break
            continuation_marker = _narrative_list_marker(main_lines[index])
            if continuation_marker and continuation_marker[0]:
                report_forbidden("nested_list")
                index += 1
                continue
            continuation_forbidden = _narrative_forbidden_kind(main_lines[index])
            if continuation_forbidden is not None:
                break
            paragraph_lines.append(main_lines[index])
            index += 1
        if paragraph_lines:
            add_paragraph_or_notice("\n".join(paragraph_lines))
        elif index < len(main_lines):
            # The next loop iteration reports the forbidden/structural line.
            continue

    finish_pending()
    expected_keys = [key for key, _heading in expected]
    if seen_headings != expected_keys:
        if set(seen_headings) != set(expected_keys):
            add_error("missing_reader_section_heading")
        else:
            add_error("reader_section_heading_order_mismatch")
    return {
        "errors": list(dict.fromkeys(errors)),
        "reader_introduction": {"text": reader_introduction, "sha256": _canonical_hash(reader_introduction)},
        "prose": eligible,
        "eligible": eligible,
        "authored": authored,
        "subheadings": subheadings,
        "sections": sections,
    }


def _validated_narrative_block_sources(
    report: object,
    narrative_block_sources: object,
    approved_ids: set[str],
    allowed_claims: Dict[str, Claim],
    timing_ids: set[str],
    parsed: Optional[Dict[str, object]] = None,
) -> tuple[List[str], List[Dict[str, object]]]:
    if not isinstance(report, str) or not report.strip():
        return ["missing_final_report"], []
    if not isinstance(narrative_block_sources, list):
        return ["missing_narrative_block_source_map"], []
    expected_entries = list(parsed.get("authored", [])) if isinstance(parsed, dict) else []
    expected_hashes = [str(item.get("narrative_block_sha256")) for item in expected_entries if isinstance(item, dict)]
    errors: List[str] = []
    by_hash: Dict[str, Dict[str, object]] = {}
    for source in narrative_block_sources:
        if not isinstance(source, dict):
            errors.append("invalid_narrative_block_source_map")
            continue
        missing = set(_NARRATIVE_BLOCK_SOURCE_FIELDS) - set(source)
        unknown = set(source) - set(_NARRATIVE_BLOCK_SOURCE_FIELDS)
        if missing:
            errors.append("premium_handoff_narrative_block_source_missing_field")
        if unknown:
            errors.append("premium_handoff_narrative_block_source_unknown_field")
        if missing or unknown:
            if _PARAGRAPH_SOURCE_FIELDS[0] in source:
                errors.append("legacy_paragraph_source_field_present")
            continue
        block_hash = source.get("narrative_block_sha256")
        if not isinstance(block_hash, str):
            errors.append("invalid_narrative_block_source_hash")
            continue
        if block_hash in by_hash:
            errors.append("duplicate_narrative_block_source_map")
            if by_hash[block_hash] != source:
                errors.append("conflicting_duplicate_narrative_block_source_map")
            continue
        by_hash[block_hash] = source
    expected_hash_set = set(expected_hashes)
    source_hashes = set(by_hash)
    if len(expected_hashes) != len(expected_hash_set):
        errors.append("duplicate_narrative_block_hash")
    if expected_hash_set - source_hashes:
        errors.append("narrative_block_without_source_map")
    if source_hashes - expected_hash_set:
        errors.append("orphan_narrative_block_source_map")
    if list(by_hash) != expected_hashes:
        errors.append("narrative_block_source_order_mismatch")

    approved = {str(item) for item in approved_ids}
    entry_by_hash = {str(item.get("narrative_block_sha256")): item for item in expected_entries if isinstance(item, dict)}
    for block_hash in expected_hash_set.intersection(source_hashes):
        source = by_hash[block_hash]
        synthesis_values = source.get("synthesis_ids")
        claim_values = source.get("claim_ids")
        timing_values = source.get("timing_ids")
        if not all(isinstance(item, list) and all(isinstance(value, str) for value in item) for item in (synthesis_values, claim_values, timing_values)):
            errors.append("invalid_narrative_block_source_references")
            continue
        synthesis_ids, claim_ids, timing_refs = set(synthesis_values), set(claim_values), set(timing_values)
        if len(synthesis_ids) != len(synthesis_values) or len(claim_ids) != len(claim_values) or len(timing_refs) != len(timing_values):
            errors.append("duplicated_narrative_block_source_reference")
        kind = str(entry_by_hash.get(block_hash, {}).get("kind"))
        if kind == "subheading":
            if not synthesis_ids or claim_ids:
                errors.append("subheading_requires_synthesis_source")
        elif synthesis_ids:
            if claim_ids or not synthesis_ids.issubset(approved):
                errors.append("untraceable_narrative_block_source")
        elif claim_ids:
            if (
                len(claim_values) != 1
                or timing_refs
                or any(claim_id not in allowed_claims or not allowed_claims[claim_id].direct_paragraph_renderable for claim_id in claim_ids)
            ):
                errors.append("invalid_direct_claim_narrative_block_source")
        else:
            errors.append("untraceable_narrative_block_source")
        if not timing_refs.issubset(timing_ids):
            errors.append("invented_or_unapproved_timing_evidence")
    if errors:
        return list(dict.fromkeys(errors)), []
    return errors, [by_hash[item] for item in expected_hashes]


def narrative_block_source_template(report: str, reader_domain_manifest: Dict[str, object]) -> List[Dict[str, object]]:
    """Return one empty 1.4 source row for every authored narrative block."""
    parsed = _parse_premium_narrative(report, reader_domain_manifest)
    if parsed["errors"]:
        raise ValueError("Invalid Premium narrative: " + ", ".join(parsed["errors"]))
    return [
        {"narrative_block_sha256": str(item["narrative_block_sha256"]), "synthesis_ids": [], "claim_ids": [], "timing_ids": []}
        for item in parsed.get("authored", [])
    ]


def _validated_paragraph_sources_v13(report: object, paragraph_sources: object, approved_ids: set[str], allowed_claims: Dict[str, Claim], timing_ids: set[str], parsed: Optional[Dict[str, object]] = None) -> tuple[List[str], List[Dict[str, object]]]:
    if not isinstance(report, str) or not report.strip():
        return ["missing_final_report"], []
    if not isinstance(paragraph_sources, list):
        return ["missing_paragraph_source_map"], []
    expected_hashes = (
        [str(item["sha256"]) for item in parsed.get("prose", [])]
        if parsed is not None else
        list(dict.fromkeys(_canonical_hash(paragraph) for paragraph in _substantive_paragraphs(report)))
    )
    expected_hash_set = set(expected_hashes)
    by_hash: Dict[str, Dict[str, object]] = {}
    errors = []
    for source in paragraph_sources:
        if not isinstance(source, dict):
            errors.append("invalid_paragraph_source_map")
            continue
        if any(field not in source for field in _PARAGRAPH_SOURCE_FIELDS):
            errors.append("premium_handoff_source_row_missing_field")
            continue
        paragraph_hash = str(source.get("paragraph_sha256"))
        if paragraph_hash in by_hash:
            errors.append("duplicate_paragraph_source_map")
            if by_hash[paragraph_hash] != source:
                errors.append("conflicting_duplicate_paragraph_source_map")
            continue
        by_hash[paragraph_hash] = source
    source_hashes = set(by_hash)
    if expected_hash_set - source_hashes:
        errors.append("interpretive_paragraph_without_source_map")
    if source_hashes - expected_hash_set:
        errors.append("orphan_paragraph_source_map")
    for paragraph_hash in expected_hash_set.intersection(source_hashes):
        source = by_hash[paragraph_hash]
        synthesis_values, claim_values, timing_values = source.get("synthesis_ids"), source.get("claim_ids"), source.get("timing_ids")
        if not all(isinstance(item, list) and all(isinstance(value, str) for value in item) for item in (synthesis_values, claim_values, timing_values)):
            errors.append("invalid_paragraph_source_references")
            continue
        synthesis_ids, claim_ids, timing_refs = set(synthesis_values), set(claim_values), set(timing_values)
        if len(synthesis_ids) != len(synthesis_values) or len(claim_ids) != len(claim_values) or len(timing_refs) != len(timing_values):
            errors.append("duplicated_paragraph_source_reference")
        if synthesis_ids:
            if claim_ids or not synthesis_ids.issubset(approved_ids):
                errors.append("untraceable_paragraph_source")
        elif claim_ids:
            if (
                len(claim_values) != 1
                or timing_refs
                or any(claim_id not in allowed_claims or not allowed_claims[claim_id].direct_paragraph_renderable for claim_id in claim_ids)
            ):
                errors.append("invalid_direct_claim_paragraph_source")
        else:
            errors.append("untraceable_paragraph_source")
        if not timing_refs.issubset(timing_ids):
            errors.append("invented_or_unapproved_timing_evidence")
    errors = list(dict.fromkeys(errors))
    return errors, ([] if errors else [by_hash[item] for item in expected_hashes])


def _validate_paragraph_sources(report: object, paragraph_sources: object, approved_ids: set[str], allowed_claims: Dict[str, Claim], timing_ids: set[str]) -> List[str]:
    return _validated_paragraph_sources_v13(report, paragraph_sources, approved_ids, allowed_claims, timing_ids)[0]


def _validate_mandatory_coverage_v13(report: object, paragraph_sources: object, approved_syntheses: Iterable[Dict[str, object]], coverage: object) -> List[str]:
    """Verify Premium Complete targets through existing paragraph provenance.

    This intentionally adds no parallel coverage framework: the existing
    source map is the contract, and a target is covered only when a substantive
    paragraph cites a synthesis that cites its deterministic evidence.
    """
    if not isinstance(paragraph_sources, list) or not isinstance(coverage, dict):
        return ["missing_mandatory_coverage_map"]
    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict)}
    sourced_ids = {
        str(synthesis_id)
        for source in paragraph_sources if isinstance(source, dict)
        for synthesis_id in source.get("synthesis_ids", [])
    }
    sourced_factors = {
        str(factor)
        for synthesis_id in sourced_ids
        for factor in approved.get(synthesis_id, {}).get("primary_factors", [])
    }
    errors = []
    for target, factors in coverage.get("required_evidence", {}).items():
        if not set(map(str, factors)).intersection(sourced_factors):
            errors.append(f"missing_mandatory_coverage:{target}")
    return errors


def _validate_mandatory_coverage_v14(
    report: object, narrative_block_sources: object,
    approved_syntheses: Iterable[Dict[str, object]], coverage: object,
    eligible_hashes: Optional[set[str]] = None,
) -> List[str]:
    """Verify mandatory targets through coverage-eligible 1.4 blocks only."""
    if not isinstance(narrative_block_sources, list) or not isinstance(coverage, dict):
        return ["missing_mandatory_coverage_map"]
    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict)}
    sourced_ids = {
        str(synthesis_id)
        for source in narrative_block_sources
        if isinstance(source, dict)
        and (eligible_hashes is None or str(source.get("narrative_block_sha256")) in eligible_hashes)
        for synthesis_id in source.get("synthesis_ids", [])
    }
    sourced_factors = {
        str(factor)
        for synthesis_id in sourced_ids
        for factor in approved.get(synthesis_id, {}).get("primary_factors", [])
    }
    errors = []
    for target, factors in coverage.get("required_evidence", {}).items():
        if not set(map(str, factors)).intersection(sourced_factors):
            errors.append(f"missing_mandatory_coverage:{target}")
    return errors


def paragraph_source_template(report: str, reader_domain_manifest: Optional[Dict[str, object]] = None) -> List[Dict[str, object]]:
    """Return the frozen V4.1.3 paragraph source template for replay/debug."""
    if reader_domain_manifest is not None:
        parsed = _parse_premium_narrative_v13(report, reader_domain_manifest)
        if parsed["errors"]:
            raise ValueError("Invalid Premium narrative: " + ", ".join(parsed["errors"]))
        hashes = [item["sha256"] for item in parsed["prose"]]
    else:
        hashes = list(dict.fromkeys(_canonical_hash(paragraph) for paragraph in _substantive_paragraphs(report)))
    return [
        {"paragraph_sha256": paragraph_hash, "synthesis_ids": [], "claim_ids": [], "timing_ids": []}
        for paragraph_hash in hashes
    ]


def _validate_reader_sections_v13(parsed: Dict[str, object], reader_sections: object, manifest: object) -> List[str]:
    errors = list(parsed.get("errors", []))
    if not isinstance(reader_sections, dict) or not isinstance(manifest, dict):
        return list(dict.fromkeys([*errors, "missing_reader_sections_contract"]))
    opening = reader_sections.get("opening")
    domains = reader_sections.get("domains")
    integration = reader_sections.get("integration")
    if not isinstance(opening, dict) or not isinstance(domains, list) or not isinstance(integration, dict):
        return list(dict.fromkeys([*errors, "invalid_reader_sections_contract"]))
    expected_domains = [str(item["id"]) for item in manifest.get("domains", [])]
    actual_domains = [str(item.get("domain_id")) for item in domains if isinstance(item, dict)]
    if actual_domains != expected_domains:
        if len(actual_domains) != len(set(actual_domains)):
            errors.append("duplicate_reader_domain_section")
        if set(actual_domains) - set(expected_domains):
            errors.append("unknown_reader_domain_section")
        if set(expected_domains) - set(actual_domains):
            errors.append("missing_reader_domain_section")
        if set(actual_domains) == set(expected_domains):
            errors.append("reader_domain_section_order_mismatch")
    section_map = parsed.get("sections", {})

    def declared_hashes(value: object) -> Optional[List[str]]:
        hashes = value.get("paragraph_sha256s") if isinstance(value, dict) else None
        if not isinstance(hashes, list) or not all(isinstance(item, str) for item in hashes) or len(hashes) != len(set(hashes)):
            return None
        return hashes

    opening_hashes = declared_hashes(opening)
    integration_hashes = declared_hashes(integration)
    if opening_hashes is None or integration_hashes is None:
        errors.append("invalid_reader_section_hashes")
    else:
        physical_opening = [item["sha256"] for item in section_map.get("opening", {}).get("prose", [])]
        physical_integration = [item["sha256"] for item in section_map.get("integration", {}).get("prose", [])]
        if opening_hashes != physical_opening:
            errors.append("reader_opening_ownership_mismatch")
        if integration_hashes != physical_integration:
            errors.append("reader_integration_ownership_mismatch")
        if not physical_opening:
            errors.append("empty_reader_opening")
        if not physical_integration:
            errors.append("empty_reader_integration")
    all_owned: List[str] = [*(opening_hashes or []), *(integration_hashes or [])]
    by_domain = {str(item.get("domain_id")): item for item in domains if isinstance(item, dict)}
    for domain in manifest.get("domains", []):
        domain_id = str(domain["id"])
        hashes = declared_hashes(by_domain.get(domain_id))
        if hashes is None:
            errors.append(f"invalid_reader_domain_hashes:{domain_id}")
            continue
        physical = [item["sha256"] for item in section_map.get(domain_id, {}).get("prose", [])]
        notices = section_map.get(domain_id, {}).get("notices", [])
        if hashes != physical:
            errors.append(f"reader_domain_ownership_mismatch:{domain_id}")
        if domain.get("availability") == "available":
            if not physical:
                errors.append(f"empty_available_reader_domain:{domain_id}")
            if notices:
                errors.append(f"notice_in_available_reader_domain:{domain_id}")
        else:
            expected_notice = domain.get("unavailable_notice") or {}
            if physical or hashes:
                errors.append(f"prose_in_unavailable_reader_domain:{domain_id}")
            if len(notices) != 1 or notices[0].get("text") != expected_notice.get("text") or notices[0].get("sha256") != expected_notice.get("sha256"):
                errors.append(f"invalid_unavailable_reader_notice:{domain_id}")
        all_owned.extend(hashes)
    if len(all_owned) != len(set(all_owned)):
        errors.append("reader_paragraph_owned_by_multiple_sections")
    physical_all = [item["sha256"] for item in parsed.get("prose", [])]
    if set(all_owned) != set(physical_all):
        errors.append("reader_section_ownership_not_exhaustive")
    return list(dict.fromkeys(errors))


def _synthesis_matches_reader_path(synthesis: Dict[str, object], path: Dict[str, object]) -> bool:
    """Use the manifest's existing structural legality for one synthesis."""
    return (
        set(map(str, path.get("source_claim_ids", []))).issubset(set(map(str, synthesis.get("source_claim_ids", []))))
        and set(map(str, path.get("primary_factor_ids", []))).issubset(set(map(str, synthesis.get("primary_factors", []))))
        and str(synthesis.get("reasoning_class")) == str(path.get("reasoning_class"))
        and set(map(str, path.get("composition_operations", []))).issubset(set(map(str, synthesis.get("composition_operations", []))))
    )


def build_selection_candidate_catalog(
    handoff: Optional[Dict[str, object]] = None,
    *,
    manifest: Optional[Dict[str, object]] = None,
    approved_syntheses: Optional[Iterable[Dict[str, object]]] = None,
    packet_id: Optional[str] = None,
) -> Dict[str, object]:
    """Return the structured SelectionCandidateCatalog containing all legal paths,
    observations, primary factors, and valid synthesis candidate IDs."""
    if handoff is not None:
        manifest = manifest or handoff.get("reader_domain_manifest", {})
        approved_syntheses = approved_syntheses or handoff.get("approved_reasoned_syntheses", [])
        packet_id = packet_id or handoff.get("packet_id")

    manifest = manifest or {}
    approved = list(approved_syntheses or [])

    catalog_domains = []
    for d in manifest.get("domains", []):
        if not isinstance(d, dict) or d.get("availability") != "available":
            continue
        d_id = str(d["id"])
        paths = d.get("legal_coverage_paths", [])
        path_entries = []
        for p in paths:
            p_id = str(p["id"])
            matching_sids = [
                str(s["id"]) for s in approved
                if isinstance(s, dict) and s.get("status") == "allowed" and _synthesis_matches_reader_path(s, p)
            ]
            path_entries.append({
                "path_id": p_id,
                "label": p.get("label") or p_id,
                "primary_factor_ids": list(map(str, p.get("primary_factor_ids", []))),
                "source_claim_ids": list(map(str, p.get("source_claim_ids", []))),
                "timing_ids": list(map(str, p.get("timing_ids", []))),
                "reasoning_class": str(p.get("reasoning_class", "")),
                "candidate_synthesis_ids": matching_sids,
            })
        catalog_domains.append({
            "domain_id": d_id,
            "domain_heading": d.get("heading"),
            "paths": path_entries,
        })

    catalog_payload = {
        "catalog_version": "1.0",
        "packet_id": packet_id,
        "domains": catalog_domains,
    }
    catalog_payload["catalog_sha256"] = _canonical_hash(catalog_payload)
    return catalog_payload



def _selection_synthesis_set_matches_path_v13(
    syntheses: Iterable[Dict[str, object]], path: Dict[str, object],
) -> tuple[bool, set[str]]:
    """Check a provenance-only synthesis union without creating a synthesis.

    The returned IDs identify members that contributed something required by
    this legal path.  It deliberately never enters scoring, ChartSignature,
    NarrativePlan preparation, or paragraph-local legality.
    """
    members = [item for item in syntheses if isinstance(item, dict) and item.get("status") == "allowed"]
    requirements = {
        "source_claim_ids": set(map(str, path.get("source_claim_ids", []))),
        "primary_factors": set(map(str, path.get("primary_factor_ids", []))),
        "composition_operations": set(map(str, path.get("composition_operations", []))),
    }
    unions = {
        field: set().union(*(set(map(str, item.get(field, []))) for item in members)) if members else set()
        for field in requirements
    }
    reasoning_class = str(path.get("reasoning_class"))
    matches = all(requirements[field].issubset(unions[field]) for field in requirements) and any(
        str(item.get("reasoning_class")) == reasoning_class for item in members
    )
    contributors = {
        str(item.get("id"))
        for item in members
        if (
            any(requirements[field].intersection(set(map(str, item.get(field, [])))) for field in requirements)
            or str(item.get("reasoning_class")) == reasoning_class
        )
    }
    return matches, contributors


def _validate_reader_selection_plan_v13(
    plan: object,
    plan_hash: object,
    parsed: Dict[str, object],
    paragraph_sources: Iterable[Dict[str, object]],
    approved_syntheses: Iterable[Dict[str, object]],
    manifest: object,
) -> tuple[List[str], Optional[Dict[str, object]], Optional[str]]:
    """Validate explicit reader-path accounting after physical provenance.

    This is an editorial-completeness contract.  Its set unions only show that
    independently valid syntheses collectively developed convergent legal
    paths in one domain; a union never authorizes a prose paragraph.
    """
    errors: List[str] = []
    if not isinstance(plan, dict):
        return ["missing_reader_selection_plan"], None, None
    if _canonical_hash(plan) != plan_hash:
        errors.append("reader_selection_plan_hash_mismatch")
    if not ({"version", "domains"}.issubset(set(plan)) and set(plan).issubset({"version", "domains", "packet_id"})) or plan.get("version") != "1.0" or not isinstance(plan.get("domains"), list):
        return [*errors, "invalid_reader_selection_plan"], None, None
    if not isinstance(manifest, dict):
        return [*errors, "missing_reader_domain_manifest"], None, None
    available = [item for item in manifest.get("domains", []) if item.get("availability") == "available"]
    if len(plan["domains"]) != len(available):
        errors.append("reader_selection_domain_mismatch")
    actual_domain_ids = [item.get("domain_id") for item in plan["domains"] if isinstance(item, dict)]
    expected_domain_ids = [item.get("id") for item in available]
    if actual_domain_ids != expected_domain_ids:
        if len(actual_domain_ids) != len(set(actual_domain_ids)):
            errors.append("duplicate_reader_selection_domain")
        errors.append("reader_selection_domain_mismatch")

    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict) and item.get("status") == "allowed"}
    source_by_hash = {str(item.get("paragraph_sha256")): item for item in paragraph_sources if isinstance(item, dict)}
    domain_sources: Dict[str, set[str]] = {}
    for domain in available:
        domain_id = str(domain["id"])
        hashes = [str(item.get("sha256")) for item in parsed.get("sections", {}).get(domain_id, {}).get("prose", [])]
        domain_sources[domain_id] = {
            str(synthesis_id)
            for paragraph_hash in hashes
            for synthesis_id in source_by_hash.get(paragraph_hash, {}).get("synthesis_ids", [])
        }

    plan_by_domain = {str(item.get("domain_id")): item for item in plan["domains"] if isinstance(item, dict)}
    for domain in available:
        domain_id = str(domain["id"])
        entry = plan_by_domain.get(domain_id)
        if not isinstance(entry, dict) or set(entry) != {"domain_id", "paths"} or not isinstance(entry.get("paths"), list):
            errors.append(f"invalid_reader_selection_domain:{domain_id}")
            continue
        paths = domain.get("legal_coverage_paths", [])
        expected_path_ids = [str(path.get("id")) for path in paths]
        actual_path_ids = [item.get("path_id") for item in entry["paths"] if isinstance(item, dict)]
        if actual_path_ids != expected_path_ids:
            if len(actual_path_ids) != len(set(actual_path_ids)):
                errors.append(f"duplicate_reader_selection_path:{domain_id}")
            errors.append(f"reader_selection_path_mismatch:{domain_id}")
        entry_by_path = {str(item.get("path_id")): item for item in entry["paths"] if isinstance(item, dict)}
        path_by_id = {str(path.get("id")): path for path in paths}
        for path_id in expected_path_ids:
            decision = entry_by_path.get(path_id)
            path = path_by_id[path_id]
            required = {"path_id", "decision", "synthesis_ids", "merged_with_path_id", "rationale"}
            if not isinstance(decision, dict) or set(decision) != required:
                errors.append(f"invalid_reader_selection_path:{path_id}")
                continue
            kind = decision.get("decision")
            synthesis_ids = decision.get("synthesis_ids")
            merge_target = decision.get("merged_with_path_id")
            rationale = decision.get("rationale")
            if kind not in {"represented", "merged_with_represented", "omitted_no_distinct_reader_value"}:
                errors.append(f"invalid_reader_selection_decision:{path_id}")
                continue
            if not isinstance(synthesis_ids, list) or not all(isinstance(item, str) for item in synthesis_ids) or len(synthesis_ids) != len(set(synthesis_ids)):
                errors.append(f"invalid_reader_selection_synthesis_ids:{path_id}")
                continue
            if kind == "represented":
                if not synthesis_ids or merge_target is not None or rationale is not None:
                    errors.append(f"invalid_reader_selection_represented:{path_id}")
                for synthesis_id in synthesis_ids:
                    if synthesis_id not in approved:
                        errors.append(f"reader_selection_unapproved_synthesis:{path_id}")
                    elif synthesis_id not in domain_sources[domain_id]:
                        errors.append(f"reader_selection_synthesis_missing_domain_provenance:{path_id}")
            elif kind == "merged_with_represented":
                if synthesis_ids or not isinstance(merge_target, str) or not merge_target or not isinstance(rationale, str) or not rationale.strip():
                    errors.append(f"invalid_reader_selection_merge:{path_id}")
            else:
                if synthesis_ids or merge_target is not None or not isinstance(rationale, str) or not rationale.strip():
                    errors.append(f"invalid_reader_selection_omission:{path_id}")

        # Validate direct same-domain merges then validate every represented
        # target with the full cluster of paths that points directly to it.
        for path_id in expected_path_ids:
            decision = entry_by_path.get(path_id, {})
            if not isinstance(decision, dict) or decision.get("decision") != "merged_with_represented":
                continue
            target_id = decision.get("merged_with_path_id")
            target = entry_by_path.get(str(target_id))
            if not isinstance(target, dict) or str(target_id) not in path_by_id or target.get("decision") != "represented":
                errors.append(f"invalid_reader_selection_merge_target:{path_id}")
        for target_id, target in entry_by_path.items():
            if not isinstance(target, dict) or target.get("decision") != "represented" or target_id not in path_by_id:
                continue
            cluster_ids = [target_id, *[
                path_id for path_id, item in entry_by_path.items()
                if isinstance(item, dict) and item.get("decision") == "merged_with_represented" and item.get("merged_with_path_id") == target_id
            ]]
            synthesis_ids = target.get("synthesis_ids", [])
            members = [approved[item] for item in synthesis_ids if item in approved]
            contributing: set[str] = set()
            for cluster_path_id in cluster_ids:
                matched, contributors = _selection_synthesis_set_matches_path_v13(members, path_by_id[cluster_path_id])
                if not matched:
                    errors.append(f"reader_selection_insufficient_set_ancestry:{cluster_path_id}")
                contributing.update(contributors)
            if set(synthesis_ids) - contributing:
                errors.append(f"reader_selection_noncontributing_synthesis_padding:{target_id}")
            if domain_id == "active_life_chapter":
                synthesis_timing = {
                    str(factor) for member in members for factor in member.get("primary_factors", []) if str(factor).startswith("timing.")
                }
                path_timing = {
                    str(timing_id) for cluster_path_id in cluster_ids
                    for timing_id in path_by_id[cluster_path_id].get("timing_ids", [])
                }
                if synthesis_timing != path_timing:
                    errors.append(f"reader_selection_timing_cluster_mismatch:{target_id}")
    return list(dict.fromkeys(errors)), plan, _canonical_hash(plan)


def _validate_reader_domain_coverage_v13(
    parsed: Dict[str, object], reader_sections: object, paragraph_sources: List[Dict[str, object]],
    approved_syntheses: Iterable[Dict[str, object]], manifest: object,
) -> List[str]:
    if not isinstance(reader_sections, dict) or not isinstance(manifest, dict):
        return ["missing_reader_domain_coverage_contract"]
    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict) and item.get("status") == "allowed"}
    by_hash = {str(item.get("paragraph_sha256")): item for item in paragraph_sources if isinstance(item, dict)}
    domains = {str(item.get("domain_id")): item for item in reader_sections.get("domains", []) if isinstance(item, dict)}
    errors: List[str] = []

    def relational_section_has_synthesis(section_key: str) -> bool:
        hashes = [item["sha256"] for item in parsed.get("sections", {}).get(section_key, {}).get("prose", [])]
        for paragraph_hash in hashes:
            source = by_hash.get(paragraph_hash, {})
            for synthesis_id in source.get("synthesis_ids", []):
                synthesis = approved.get(str(synthesis_id))
                if not synthesis:
                    continue
                if synthesis.get("reasoning_class") not in {"integrated_pattern", "theme_interaction"}:
                    continue
                if any(str(claim_id).startswith("claim.house_ruler.placidus.") for claim_id in synthesis.get("source_claim_ids", [])):
                    continue
                return True
        return False

    if not relational_section_has_synthesis("opening"):
        errors.append("reader_opening_requires_relational_synthesis")
    if not relational_section_has_synthesis("integration"):
        errors.append("reader_integration_requires_relational_synthesis")

    for domain in manifest.get("domains", []):
        domain_id = str(domain["id"])
        if domain.get("availability") != "available":
            continue
        hashes = domains.get(domain_id, {}).get("paragraph_sha256s", [])
        covered = False
        for paragraph_hash in hashes:
            source = by_hash.get(str(paragraph_hash), {})
            timing_refs = set(map(str, source.get("timing_ids", [])))
            if domain_id == "active_life_chapter" and timing_refs:
                cited_timing_syntheses = [approved.get(str(item)) for item in source.get("synthesis_ids", [])]
                if not any(
                    synthesis
                    and synthesis.get("reasoning_class") == "natal_timing_interaction"
                    and timing_refs.issubset(set(map(str, synthesis.get("primary_factors", []))))
                    for synthesis in cited_timing_syntheses
                ):
                    errors.append("reader_timing_source_not_linked_to_cited_synthesis")
            paragraph_covered = False
            for synthesis_id in source.get("synthesis_ids", []):
                synthesis = approved.get(str(synthesis_id))
                if not synthesis:
                    continue
                matched_paths = [
                    path for path in domain.get("legal_coverage_paths", [])
                    if _synthesis_matches_reader_path(synthesis, path)
                ]
                if domain_id == "active_life_chapter":
                    synthesis_factors = set(map(str, synthesis.get("primary_factors", [])))
                    synthesis_timing = {factor for factor in synthesis_factors if factor.startswith("timing.")}
                    matched_timing = {
                        timing_id
                        for path in matched_paths
                        for timing_id in map(str, path.get("timing_ids", []))
                    }
                    if (
                        synthesis.get("reasoning_class") == "natal_timing_interaction"
                        and timing_refs
                        and timing_refs == synthesis_timing
                        and synthesis_timing == matched_timing
                        and any(not factor.startswith("timing.") for factor in synthesis_factors)
                    ):
                        paragraph_covered = True
                    if paragraph_covered:
                        break
                    continue
                for path in matched_paths:
                    paragraph_covered = True
                    break
                if paragraph_covered:
                    break
            # An atomic direct Claim may accompany substantive coverage only
            # when that exact route belongs to this domain.  It remains
            # ancillary: only a matching synthesis can set ``covered``.
            direct_claim_ids = set(map(str, source.get("claim_ids", [])))
            direct_route_authorized = bool(direct_claim_ids) and any(
                direct_claim_ids.issubset(set(map(str, path.get("source_claim_ids", []))))
                for path in domain.get("legal_coverage_paths", [])
            )
            if not paragraph_covered and not direct_route_authorized:
                errors.append(f"reader_domain_paragraph_outside_legal_path:{domain_id}")
            covered = covered or paragraph_covered
        if not covered:
            errors.append(f"missing_reader_domain_coverage:{domain_id}")
    return list(dict.fromkeys(errors))


def _validate_reader_sections(
    parsed: Dict[str, object], reader_sections: object, manifest: object,
) -> List[str]:
    """Validate the exact 1.4 ownership shape against physical blocks.

    ``authored`` includes H3 subheadings while ``prose``/``eligible`` is
    deliberately limited to paragraphs and list items.  The distinction is
    important: a sourced H3 can orient a reader, but it can never keep a
    domain or a selection path alive by itself.
    """
    errors = list(parsed.get("errors", []))
    if not isinstance(reader_sections, dict) or not isinstance(manifest, dict):
        return list(dict.fromkeys([*errors, "missing_reader_sections_contract"]))
    expected_top = {"opening", "domains", "integration"}
    if set(reader_sections) != expected_top:
        errors.append("invalid_reader_sections_exact_shape")
    opening = reader_sections.get("opening")
    domains = reader_sections.get("domains")
    integration = reader_sections.get("integration")
    if not isinstance(opening, dict) or not isinstance(domains, list) or not isinstance(integration, dict):
        return list(dict.fromkeys([*errors, "invalid_reader_sections_contract"]))
    if set(opening) != {"narrative_block_sha256s"} or set(integration) != {"narrative_block_sha256s"}:
        errors.append("invalid_reader_layer_exact_shape")
    for item in domains:
        if not isinstance(item, dict) or set(item) != {"domain_id", "narrative_block_sha256s"}:
            errors.append("invalid_reader_domain_exact_shape")

    expected_domains = [str(item["id"]) for item in manifest.get("domains", []) if isinstance(item, dict)]
    actual_domains = [str(item.get("domain_id")) for item in domains if isinstance(item, dict)]
    if actual_domains != expected_domains:
        if len(actual_domains) != len(set(actual_domains)):
            errors.append("duplicate_reader_domain_section")
        if set(actual_domains) - set(expected_domains):
            errors.append("unknown_reader_domain_section")
        if set(expected_domains) - set(actual_domains):
            errors.append("missing_reader_domain_section")
        if set(actual_domains) == set(expected_domains):
            errors.append("reader_domain_section_order_mismatch")

    section_map = parsed.get("sections", {})

    def authored_hashes(section_key: str) -> List[str]:
        section = section_map.get(section_key, {}) if isinstance(section_map, dict) else {}
        return [str(item.get("narrative_block_sha256")) for item in section.get("authored", []) if isinstance(item, dict)]

    def eligible_hashes(section_key: str) -> List[str]:
        section = section_map.get(section_key, {}) if isinstance(section_map, dict) else {}
        return [str(item.get("narrative_block_sha256")) for item in section.get("prose", []) if isinstance(item, dict)]

    def declared_hashes(value: object) -> Optional[List[str]]:
        hashes = value.get("narrative_block_sha256s") if isinstance(value, dict) else None
        if not isinstance(hashes, list) or not all(isinstance(item, str) for item in hashes):
            return None
        if len(hashes) != len(set(hashes)):
            return None
        return hashes

    opening_hashes = declared_hashes(opening)
    integration_hashes = declared_hashes(integration)
    if opening_hashes is None or integration_hashes is None:
        errors.append("invalid_reader_section_hashes")
    else:
        physical_opening = authored_hashes("opening")
        physical_integration = authored_hashes("integration")
        if opening_hashes != physical_opening:
            errors.append("reader_opening_ownership_mismatch")
        if integration_hashes != physical_integration:
            errors.append("reader_integration_ownership_mismatch")
        if not eligible_hashes("opening"):
            errors.append("empty_reader_opening")
        if not eligible_hashes("integration"):
            errors.append("empty_reader_integration")

    all_owned: List[str] = [*(opening_hashes or [])]
    by_domain: Dict[str, Dict[str, object]] = {}
    for item in domains:
        if isinstance(item, dict):
            domain_id = str(item.get("domain_id"))
            if domain_id in by_domain:
                errors.append("duplicate_reader_domain_section")
            by_domain[domain_id] = item
    for domain in manifest.get("domains", []):
        if not isinstance(domain, dict):
            continue
        domain_id = str(domain["id"])
        section = by_domain.get(domain_id)
        hashes = declared_hashes(section)
        if hashes is None:
            errors.append(f"invalid_reader_domain_hashes:{domain_id}")
            continue
        physical = authored_hashes(domain_id)
        notices = section_map.get(domain_id, {}).get("notices", []) if isinstance(section_map, dict) else []
        if hashes != physical:
            errors.append(f"reader_domain_ownership_mismatch:{domain_id}")
        if domain.get("availability") == "available":
            if not eligible_hashes(domain_id):
                errors.append(f"empty_available_reader_domain:{domain_id}")
            if notices:
                errors.append(f"notice_in_available_reader_domain:{domain_id}")
        else:
            expected_notice = domain.get("unavailable_notice") or {}
            if physical or hashes:
                errors.append(f"prose_in_unavailable_reader_domain:{domain_id}")
            if len(notices) != 1 or notices[0].get("text") != expected_notice.get("text") or notices[0].get("sha256") != expected_notice.get("sha256"):
                errors.append(f"invalid_unavailable_reader_notice:{domain_id}")
        all_owned.extend(hashes)

    all_owned.extend(integration_hashes or [])

    if len(all_owned) != len(set(all_owned)):
        errors.append("reader_narrative_block_owned_by_multiple_sections")
    physical_all = [str(item.get("narrative_block_sha256")) for item in parsed.get("authored", []) if isinstance(item, dict)]
    if set(all_owned) != set(physical_all):
        errors.append("reader_section_ownership_not_exhaustive")
    if all_owned != physical_all:
        errors.append("reader_section_ownership_order_mismatch")
    return list(dict.fromkeys(errors))


def _selection_synthesis_set_matches_path(
    syntheses: Iterable[Dict[str, object]], path: Dict[str, object],
) -> tuple[bool, set[str]]:
    """Check each synthesis independently for one legal path.

    A cluster may use different approved syntheses for different paths, but a
    path is never manufactured by taking claims, factors, operations, or a
    reasoning class from separate synthesis records.
    """
    matched = {
        str(item.get("id"))
        for item in syntheses
        if isinstance(item, dict)
        and item.get("status") == "allowed"
        and _synthesis_matches_reader_path(item, path)
    }
    return bool(matched), matched


def _validate_reader_selection_plan(
    plan: object,
    plan_hash: object,
    parsed: Dict[str, object],
    narrative_block_sources: Iterable[Dict[str, object]],
    approved_syntheses: Iterable[Dict[str, object]],
    manifest: object,
) -> tuple[List[str], Optional[Dict[str, object]], Optional[str]]:
    """Validate the prospective 1.4 selection plan after physical provenance."""
    errors: List[str] = []
    if not isinstance(plan, dict):
        return ["missing_reader_selection_plan"], None, None
    if _canonical_hash(plan) != plan_hash:
        errors.append("reader_selection_plan_hash_mismatch")
    if not ({"version", "domains"}.issubset(set(plan)) and set(plan).issubset({"version", "domains", "packet_id"})) or plan.get("version") != "1.0" or not isinstance(plan.get("domains"), list):
        return [*errors, "invalid_reader_selection_plan"], None, None
    if not isinstance(manifest, dict):
        return [*errors, "missing_reader_domain_manifest"], None, None
    available = [item for item in manifest.get("domains", []) if isinstance(item, dict) and item.get("availability") == "available"]
    if len(plan["domains"]) != len(available):
        errors.append("reader_selection_domain_mismatch")
    actual_domain_ids = [item.get("domain_id") for item in plan["domains"] if isinstance(item, dict)]
    expected_domain_ids = [item.get("id") for item in available]
    if actual_domain_ids != expected_domain_ids:
        if len(actual_domain_ids) != len(set(actual_domain_ids)):
            errors.append("duplicate_reader_selection_domain")
        errors.append("reader_selection_domain_mismatch")

    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict) and item.get("status") == "allowed"}
    source_by_hash = {
        str(item.get("narrative_block_sha256")): item
        for item in narrative_block_sources if isinstance(item, dict)
    }
    domain_sources: Dict[str, set[str]] = {}
    for domain in available:
        domain_id = str(domain["id"])
        hashes = [
            str(item.get("narrative_block_sha256"))
            for item in parsed.get("sections", {}).get(domain_id, {}).get("prose", [])
            if isinstance(item, dict)
        ]
        domain_sources[domain_id] = {
            str(synthesis_id)
            for block_hash in hashes
            for synthesis_id in source_by_hash.get(block_hash, {}).get("synthesis_ids", [])
        }

    plan_by_domain = {str(item.get("domain_id")): item for item in plan["domains"] if isinstance(item, dict)}
    for domain in available:
        domain_id = str(domain["id"])
        entry = plan_by_domain.get(domain_id)
        if not isinstance(entry, dict) or set(entry) != {"domain_id", "paths"} or not isinstance(entry.get("paths"), list):
            errors.append(f"invalid_reader_selection_domain:{domain_id}")
            continue
        paths = domain.get("legal_coverage_paths", [])
        expected_path_ids = [str(path.get("id")) for path in paths]
        actual_path_ids = [item.get("path_id") for item in entry["paths"] if isinstance(item, dict)]
        if actual_path_ids != expected_path_ids:
            if len(actual_path_ids) != len(set(actual_path_ids)):
                errors.append(f"duplicate_reader_selection_path:{domain_id}")
            errors.append(f"reader_selection_path_mismatch:{domain_id}")
        entry_by_path = {str(item.get("path_id")): item for item in entry["paths"] if isinstance(item, dict)}
        path_by_id = {str(path.get("id")): path for path in paths}
        for path_id in expected_path_ids:
            decision = entry_by_path.get(path_id)
            required = {"path_id", "decision", "synthesis_ids", "merged_with_path_id", "rationale"}
            if not isinstance(decision, dict) or set(decision) != required:
                errors.append(f"invalid_reader_selection_path:{path_id}")
                continue
            kind = decision.get("decision")
            synthesis_ids = decision.get("synthesis_ids")
            merge_target = decision.get("merged_with_path_id")
            rationale = decision.get("rationale")
            if kind not in {"represented", "merged_with_represented", "omitted_no_distinct_reader_value"}:
                errors.append(f"invalid_reader_selection_decision:{path_id}")
                continue
            if not isinstance(synthesis_ids, list) or not all(isinstance(item, str) for item in synthesis_ids) or len(synthesis_ids) != len(set(synthesis_ids)):
                errors.append(f"invalid_reader_selection_synthesis_ids:{path_id}")
                continue
            if kind == "represented":
                if not synthesis_ids or merge_target is not None or rationale is not None:
                    errors.append(f"invalid_reader_selection_represented:{path_id}")
                for synthesis_id in synthesis_ids:
                    if synthesis_id not in approved:
                        errors.append(f"reader_selection_unapproved_synthesis:{path_id}")
                    elif synthesis_id not in domain_sources[domain_id]:
                        errors.append(f"reader_selection_synthesis_missing_domain_provenance:{path_id}")
            elif kind == "merged_with_represented":
                if synthesis_ids or not isinstance(merge_target, str) or not merge_target or not isinstance(rationale, str) or not rationale.strip():
                    errors.append(f"invalid_reader_selection_merge:{path_id}")
            else:
                if synthesis_ids or merge_target is not None or not isinstance(rationale, str) or not rationale.strip():
                    errors.append(f"invalid_reader_selection_omission:{path_id}")

        for path_id in expected_path_ids:
            decision = entry_by_path.get(path_id, {})
            if not isinstance(decision, dict) or decision.get("decision") != "merged_with_represented":
                continue
            target_id = decision.get("merged_with_path_id")
            target = entry_by_path.get(str(target_id))
            if not isinstance(target, dict) or str(target_id) not in path_by_id or target.get("decision") != "represented":
                errors.append(f"invalid_reader_selection_merge_target:{path_id}")

        for target_id, target in entry_by_path.items():
            if not isinstance(target, dict) or target.get("decision") != "represented" or target_id not in path_by_id:
                continue
            cluster_ids = [target_id, *[
                path_id for path_id, item in entry_by_path.items()
                if isinstance(item, dict)
                and item.get("decision") == "merged_with_represented"
                and item.get("merged_with_path_id") == target_id
            ]]
            synthesis_ids = target.get("synthesis_ids", [])
            members = [approved[item] for item in synthesis_ids if item in approved]
            contributing: set[str] = set()
            for cluster_path_id in cluster_ids:
                matched, contributors = _selection_synthesis_set_matches_path(members, path_by_id[cluster_path_id])
                if not matched:
                    errors.append(f"reader_selection_insufficient_set_ancestry:{cluster_path_id}")
                contributing.update(contributors)
            if set(synthesis_ids) - contributing:
                errors.append(f"reader_selection_noncontributing_synthesis_padding:{target_id}")
            if domain_id == "active_life_chapter" or any(
                str(timing_id) for cluster_path_id in cluster_ids
                for timing_id in path_by_id[cluster_path_id].get("timing_ids", [])
            ) or any(
                str(factor).startswith("timing.")
                for member in members for factor in member.get("primary_factors", [])
            ):
                synthesis_timing = {
                    str(factor)
                    for member in members
                    for factor in member.get("primary_factors", [])
                    if str(factor).startswith("timing.")
                }
                path_timing = {
                    str(timing_id)
                    for cluster_path_id in cluster_ids
                    for timing_id in path_by_id[cluster_path_id].get("timing_ids", [])
                }
                if synthesis_timing != path_timing:
                    errors.append(f"reader_selection_timing_cluster_mismatch:{target_id}")
    return list(dict.fromkeys(errors)), plan, _canonical_hash(plan)


def _validate_reader_domain_coverage(
    parsed: Dict[str, object], reader_sections: object, narrative_block_sources: List[Dict[str, object]],
    approved_syntheses: Iterable[Dict[str, object]], manifest: object,
) -> List[str]:
    """Validate 1.4 domain coverage using paragraphs and list items only."""
    if not isinstance(reader_sections, dict) or not isinstance(manifest, dict):
        return ["missing_reader_domain_coverage_contract"]
    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict) and item.get("status") == "allowed"}
    by_hash = {str(item.get("narrative_block_sha256")): item for item in narrative_block_sources if isinstance(item, dict)}
    domains = {str(item.get("domain_id")): item for item in reader_sections.get("domains", []) if isinstance(item, dict)}
    errors: List[str] = []

    def relational_section_has_synthesis(section_key: str) -> bool:
        hashes = [
            str(item.get("narrative_block_sha256"))
            for item in parsed.get("sections", {}).get(section_key, {}).get("prose", [])
            if isinstance(item, dict)
        ]
        for block_hash in hashes:
            source = by_hash.get(block_hash, {})
            for synthesis_id in source.get("synthesis_ids", []):
                synthesis = approved.get(str(synthesis_id))
                if not synthesis:
                    continue
                if synthesis.get("reasoning_class") not in {"integrated_pattern", "theme_interaction"}:
                    continue
                if any(str(claim_id).startswith("claim.house_ruler.placidus.") for claim_id in synthesis.get("source_claim_ids", [])):
                    continue
                return True
        return False

    if not relational_section_has_synthesis("opening"):
        errors.append("reader_opening_requires_relational_synthesis")
    if not relational_section_has_synthesis("integration"):
        errors.append("reader_integration_requires_relational_synthesis")

    for domain in manifest.get("domains", []):
        if not isinstance(domain, dict):
            continue
        domain_id = str(domain["id"])
        if domain.get("availability") != "available":
            continue
        # Domain coverage is deliberately limited to paragraphs and list items.
        # H3 remains in ownership and source provenance, but can never keep a
        # domain alive or satisfy a path by itself.
        hashes = [
            str(item.get("narrative_block_sha256"))
            for item in parsed.get("sections", {}).get(domain_id, {}).get("prose", [])
            if isinstance(item, dict)
        ]
        covered = False
        for block_hash in hashes:
            source = by_hash.get(str(block_hash), {})
            timing_refs = set(map(str, source.get("timing_ids", [])))
            if domain_id == "active_life_chapter" and timing_refs:
                cited_timing_syntheses = [approved.get(str(item)) for item in source.get("synthesis_ids", [])]
                if not any(
                    synthesis
                    and synthesis.get("reasoning_class") == "natal_timing_interaction"
                    and timing_refs.issubset(set(map(str, synthesis.get("primary_factors", []))))
                    for synthesis in cited_timing_syntheses
                ):
                    errors.append("reader_timing_source_not_linked_to_cited_synthesis")
            block_covered = False
            for synthesis_id in source.get("synthesis_ids", []):
                synthesis = approved.get(str(synthesis_id))
                if not synthesis:
                    continue
                matched_paths = [
                    path for path in domain.get("legal_coverage_paths", [])
                    if _synthesis_matches_reader_path(synthesis, path)
                ]
                if domain_id == "active_life_chapter":
                    synthesis_factors = set(map(str, synthesis.get("primary_factors", [])))
                    synthesis_timing = {factor for factor in synthesis_factors if factor.startswith("timing.")}
                    matched_timing = {
                        timing_id
                        for path in matched_paths
                        for timing_id in map(str, path.get("timing_ids", []))
                    }
                    if (
                        synthesis.get("reasoning_class") == "natal_timing_interaction"
                        and timing_refs
                        and timing_refs == synthesis_timing
                        and synthesis_timing == matched_timing
                        and any(not factor.startswith("timing.") for factor in synthesis_factors)
                    ):
                        block_covered = True
                    if block_covered:
                        break
                    continue
                if matched_paths:
                    block_covered = True
                    break
            direct_claim_ids = set(map(str, source.get("claim_ids", [])))
            direct_route_authorized = bool(direct_claim_ids) and any(
                direct_claim_ids.issubset(set(map(str, path.get("source_claim_ids", []))))
                for path in domain.get("legal_coverage_paths", [])
            )
            if not block_covered and not direct_route_authorized:
                errors.append(f"reader_domain_paragraph_outside_legal_path:{domain_id}")
            covered = covered or block_covered
        if not covered:
            errors.append(f"missing_reader_domain_coverage:{domain_id}")
    return list(dict.fromkeys(errors))


def _validate_subheading_sources(
    parsed: Dict[str, object], narrative_block_sources: Iterable[Dict[str, object]],
    approved_syntheses: Iterable[Dict[str, object]], manifest: object,
) -> List[str]:
    """Check H3 sourcing without allowing it into coverage or selection."""
    if not isinstance(manifest, dict):
        return ["missing_reader_domain_manifest"]
    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict) and item.get("status") == "allowed"}
    by_hash = {str(item.get("narrative_block_sha256")): item for item in narrative_block_sources if isinstance(item, dict)}
    domains = {str(item.get("id")): item for item in manifest.get("domains", []) if isinstance(item, dict)}
    errors: List[str] = []
    for heading in parsed.get("subheadings", []):
        if not isinstance(heading, dict):
            continue
        block_hash = str(heading.get("narrative_block_sha256"))
        source = by_hash.get(block_hash)
        if not source:
            errors.append("subheading_without_source_map")
            continue
        domain_id = str(heading.get("section"))
        domain = domains.get(domain_id)
        if not domain or domain.get("availability") != "available":
            errors.append(f"subheading_not_in_available_domain:{domain_id}")
            continue
        synthesis_ids = source.get("synthesis_ids", [])
        if not isinstance(synthesis_ids, list) or not synthesis_ids:
            errors.append("subheading_requires_synthesis_source")
            continue
        cited_timing: set[str] = set()
        for synthesis_id in synthesis_ids:
            synthesis = approved.get(str(synthesis_id))
            if not synthesis:
                errors.append("untraceable_subheading_source")
                continue
            cited_timing.update(
                str(factor) for factor in synthesis.get("primary_factors", [])
                if str(factor).startswith("timing.")
            )
            matched_paths = [
                path for path in domain.get("legal_coverage_paths", [])
                if _synthesis_matches_reader_path(synthesis, path)
            ]
            if not matched_paths:
                errors.append(f"subheading_synthesis_illegal_for_domain:{domain_id}")
            legal_timing = {
                str(timing_id)
                for path in matched_paths
                for timing_id in path.get("timing_ids", [])
            }
            if set(map(str, source.get("timing_ids", []))) - legal_timing:
                errors.append(f"subheading_timing_illegal_for_domain:{domain_id}")
        if set(map(str, source.get("timing_ids", []))) != cited_timing:
            errors.append("subheading_timing_not_linked_to_cited_synthesis")
    return list(dict.fromkeys(errors))


def _handoff_contract_errors_v13(bundle: Dict[str, object], bundle_kind: str) -> List[str]:
    """Frozen V4.1.3 bundle checks; legacy extras remain replay-compatible."""
    contract = _premium_handoff_contract_v13()
    contract_hash = _canonical_hash(contract)
    errors = []
    required_key = f"{bundle_kind}_bundle_required_fields"
    for field in contract[required_key]:
        if field not in bundle:
            errors.append(f"premium_handoff_{bundle_kind}_bundle_missing_required_field:{field}")
    if bundle.get("premium_handoff_contract_version") != LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("premium_handoff_contract_version_mismatch")
    if bundle.get("premium_handoff_contract") != contract:
        errors.append("premium_handoff_contract_body_mismatch")
    if bundle.get("premium_handoff_contract_sha256") != contract_hash:
        errors.append("premium_handoff_contract_hash_mismatch")
    if "premium_handoff_contract" in bundle and _canonical_hash(bundle["premium_handoff_contract"]) != bundle.get("premium_handoff_contract_sha256"):
        errors.append("premium_handoff_contract_body_hash_mismatch")
    if _NARRATIVE_PREMIUM_FIELDS.intersection(bundle):
        errors.append("mixed_version_narrative_block_fields")
    return errors


def _handoff_contract_errors_v14(bundle: Dict[str, object], bundle_kind: str) -> List[str]:
    """Fail-closed exact shape checks for a current 1.4 bundle."""
    contract = _premium_handoff_contract()
    contract_hash = _canonical_hash(contract)
    errors: List[str] = []
    required_key = f"{bundle_kind}_bundle_required_fields"
    expected = set(contract[required_key])
    if not isinstance(bundle, dict):
        return [f"invalid_premium_handoff_{bundle_kind}_bundle_shape"]
    for field in contract[required_key]:
        if field not in bundle:
            errors.append(f"premium_handoff_{bundle_kind}_bundle_missing_required_field:{field}")
    unknown = set(bundle) - expected
    for field in sorted(unknown):
        errors.append(f"premium_handoff_{bundle_kind}_bundle_unknown_field:{field}")
    if set(bundle) != expected:
        errors.append(f"invalid_premium_handoff_{bundle_kind}_bundle_shape")
    if bundle.get("premium_handoff_contract_version") != PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("premium_handoff_contract_version_mismatch")
    if bundle.get("premium_handoff_contract") != contract:
        errors.append("premium_handoff_contract_body_mismatch")
    if bundle.get("premium_handoff_contract_sha256") != contract_hash:
        errors.append("premium_handoff_contract_hash_mismatch")
    if "premium_handoff_contract" in bundle and _canonical_hash(bundle["premium_handoff_contract"]) != bundle.get("premium_handoff_contract_sha256"):
        errors.append("premium_handoff_contract_body_hash_mismatch")
    if _LEGACY_PREMIUM_FIELDS.intersection(bundle):
        errors.append("legacy_paragraph_fields_not_allowed_in_v14")
    return list(dict.fromkeys(errors))


def _handoff_contract_errors(bundle: Dict[str, object], bundle_kind: str, premium_contract_version: str = PREMIUM_HANDOFF_CONTRACT_VERSION) -> List[str]:
    """Version-dispatched bundle shape validation."""
    if premium_contract_version == LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION:
        return _handoff_contract_errors_v13(bundle, bundle_kind)
    if premium_contract_version == PREMIUM_HANDOFF_CONTRACT_VERSION:
        return _handoff_contract_errors_v14(bundle, bundle_kind)
    return ["unsupported_premium_handoff_contract_version"]


def _verify_authoritative_prepared_handoff(
    prepared_handoff: Optional[Dict[str, object]], authoritative: Optional[Dict[str, object]] = None,
    *, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True,
    premium_contract_version: str = PREMIUM_HANDOFF_CONTRACT_VERSION,
) -> tuple[Optional[datetime], int, bool, List[str]]:
    """Parse and verify the single deterministic authority for one Premium version.

    The first call supplies the materialized deterministic selectors for a
    recomputation.  The second call receives that recomputation and verifies
    the supplied handoff's complete prepared identity against it.  Both
    Premium guards use this exact path; transport consistency is not authority.
    """
    handoff = prepared_handoff if isinstance(prepared_handoff, dict) else {}
    try:
        contract = _premium_handoff_contract_for_version(premium_contract_version)
    except ValueError:
        contract = _premium_handoff_contract()
    parameters = handoff.get("preparation_parameters") if isinstance(handoff.get("preparation_parameters"), dict) else {}
    prepared_as_of_raw = parameters.get("effective_as_of")
    prepared_as_of: Optional[datetime] = None
    errors: List[str] = []
    if not handoff:
        errors.append("missing_authoritative_prepared_handoff")
    if set(parameters) != {"effective_as_of", "horizon_days", "include_timing"}:
        errors.append("invalid_preparation_parameters")
    if prepared_as_of_raw is not None:
        try:
            prepared_as_of = datetime.fromisoformat(str(prepared_as_of_raw).replace("Z", "+00:00"))
            if prepared_as_of.tzinfo is None:
                raise ValueError("effective_as_of must include a UTC offset")
        except ValueError:
            errors.append("invalid_prepared_effective_as_of")
    prepared_horizon = parameters.get("horizon_days")
    prepared_include_timing = parameters.get("include_timing")
    if not isinstance(prepared_horizon, int) or isinstance(prepared_horizon, bool) or prepared_horizon <= 0:
        errors.append("invalid_prepared_horizon_days")
        prepared_horizon = horizon_days
    if not isinstance(prepared_include_timing, bool):
        errors.append("invalid_prepared_include_timing")
        prepared_include_timing = include_timing
    if prepared_include_timing and prepared_as_of is None:
        errors.append("missing_prepared_effective_as_of")
    if as_of is not None and prepared_as_of != as_of:
        errors.append("publication_as_of_mismatch")
    if horizon_days != prepared_horizon:
        errors.append("publication_horizon_days_mismatch")
    if include_timing != prepared_include_timing:
        errors.append("publication_include_timing_mismatch")
    if handoff.get("stage") != "reasoning_packet_ready":
        errors.append("invalid_authoritative_prepared_handoff_stage")
    if handoff.get("premium_report_depth") != "deep":
        errors.append("invalid_authoritative_prepared_handoff_type")
    if handoff.get("premium_handoff_contract_version") != premium_contract_version:
        errors.append("authoritative_handoff_contract_version_mismatch")
    if handoff.get("premium_handoff_contract") != contract:
        errors.append("authoritative_handoff_contract_body_mismatch")
    if handoff.get("premium_handoff_contract_sha256") != _canonical_hash(contract):
        errors.append("authoritative_handoff_contract_hash_mismatch")
    handoff_introduction = handoff.get("reader_introduction")
    handoff_introduction_hash = handoff.get("reader_introduction_sha256")
    if handoff_introduction not in PREMIUM_READER_INTRODUCTIONS.values():
        errors.append("invalid_authoritative_handoff_reader_introduction")
    if handoff_introduction_hash != _canonical_hash(handoff_introduction):
        errors.append("authoritative_handoff_reader_introduction_body_hash_mismatch")
    if authoritative is not None:
        if handoff.get("packet_id") != authoritative.get("packet_id"):
            errors.append("authoritative_handoff_packet_id_mismatch")
        if handoff.get("chart_signature") != authoritative.get("chart_signature"):
            errors.append("authoritative_handoff_chart_signature_mismatch")
        if handoff.get("prepared_chart_signature_sha256") != authoritative.get("prepared_chart_signature_sha256"):
            errors.append("authoritative_handoff_chart_signature_hash_mismatch")
        if handoff.get("prepared_signature_syntheses") != authoritative.get("prepared_signature_syntheses"):
            errors.append("authoritative_handoff_signature_synthesis_basis_mismatch")
        if handoff.get("prepared_signature_synthesis_sha256") != authoritative.get("prepared_signature_synthesis_sha256"):
            errors.append("authoritative_handoff_signature_synthesis_hash_mismatch")
        if handoff.get("reader_domain_manifest") != authoritative.get("reader_domain_manifest"):
            errors.append("authoritative_handoff_reader_domain_manifest_mismatch")
        if handoff.get("reader_domain_manifest_sha256") != authoritative.get("reader_domain_manifest_sha256"):
            errors.append("authoritative_handoff_reader_domain_manifest_hash_mismatch")
        if handoff_introduction != authoritative.get("reader_introduction"):
            errors.append("authoritative_handoff_reader_introduction_mismatch")
        if handoff_introduction_hash != authoritative.get("reader_introduction_sha256"):
            errors.append("authoritative_handoff_reader_introduction_hash_mismatch")
    return prepared_as_of, prepared_horizon, prepared_include_timing, list(dict.fromkeys(errors))


def _verify_authoritative_prepared_handoff_v13(
    prepared_handoff: Optional[Dict[str, object]], authoritative: Optional[Dict[str, object]] = None,
    *, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True,
) -> tuple[Optional[datetime], int, bool, List[str]]:
    return _verify_authoritative_prepared_handoff(
        prepared_handoff, authoritative, as_of=as_of, horizon_days=horizon_days,
        include_timing=include_timing, premium_contract_version=LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
    )


def _verify_authoritative_prepared_handoff_v14(
    prepared_handoff: Optional[Dict[str, object]], authoritative: Optional[Dict[str, object]] = None,
    *, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True,
) -> tuple[Optional[datetime], int, bool, List[str]]:
    return _verify_authoritative_prepared_handoff(
        prepared_handoff, authoritative, as_of=as_of, horizon_days=horizon_days,
        include_timing=include_timing, premium_contract_version=PREMIUM_HANDOFF_CONTRACT_VERSION,
    )


def _validate_premium_author_bundle_v13(birth: BirthData, author_bundle: Dict[str, object], profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True, prepared_handoff: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    """Frozen V4.1.3 Deterministic Provenance Guard for replay."""
    items = author_bundle.get("reasoned_syntheses", [])
    prepared_as_of, prepared_horizon, prepared_include_timing, _ = _verify_authoritative_prepared_handoff_v13(
        prepared_handoff, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    checked = validate_premium_syntheses(
        birth, items if isinstance(items, list) else [], profile,
        prepared_as_of, prepared_horizon, prepared_include_timing,
        premium_contract_version=LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
    )
    _prepared_as_of, _prepared_horizon, _prepared_include_timing, errors = _verify_authoritative_prepared_handoff_v13(
        prepared_handoff, checked, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    errors.extend(_handoff_contract_errors_v13(author_bundle, "author"))
    if author_bundle.get("packet_id") != checked["packet_id"]:
        errors.append("packet_id_mismatch")
    for field in ("prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256"):
        if author_bundle.get(field) != checked.get(field):
            errors.append(f"{field}_mismatch")
    expected_synthesis_hash = _canonical_hash([item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"])
    if author_bundle.get("synthesis_bundle_sha256") != expected_synthesis_hash:
        errors.append("synthesis_bundle_hash_mismatch")
    draft = author_bundle.get("draft_report")
    if author_bundle.get("draft_report_sha256") != _canonical_hash(draft):
        errors.append("draft_report_hash_mismatch")
    approved_ids = {item["id"] for item in checked["reasoned_synthesis"] if item["status"] == "allowed"}
    allowed_claims = {item["id"]: Claim(**item) for item in checked["allowed_claims"]}
    parsed = _parse_premium_narrative_v13(draft, checked["reader_domain_manifest"])
    errors.extend(_validate_reader_sections_v13(parsed, author_bundle.get("reader_sections"), checked["reader_domain_manifest"]))
    source_errors, valid_sources = _validated_paragraph_sources_v13(draft, author_bundle.get("paragraph_sources"), approved_ids, allowed_claims, set(checked["timing_evidence_ids"]), parsed)
    errors.extend(source_errors)
    approved_syntheses = checked["approved_reasoned_syntheses"]
    errors.extend(_validate_mandatory_coverage_v13(draft, valid_sources, approved_syntheses, checked.get("coverage")))
    errors.extend(_validate_reader_domain_coverage_v13(parsed, author_bundle.get("reader_sections"), valid_sources, approved_syntheses, checked["reader_domain_manifest"]))
    selection_errors, selection_plan, selection_plan_hash = _validate_reader_selection_plan_v13(
        author_bundle.get("reader_selection_plan"), author_bundle.get("reader_selection_plan_sha256"),
        parsed, valid_sources, approved_syntheses, checked["reader_domain_manifest"],
    )
    errors.extend(selection_errors)
    if isinstance(draft, str) and _contains_prohibited_extension(draft):
        errors.append("prohibited_extension_in_author_draft")
    if not birth.birth_time_known:
        errors.append("premium_birth_time_required")
    return {"stage": "deterministic_provenance_guard", "approved": checked["approved"] and not errors, "verification_errors": list(dict.fromkeys(errors)), "packet_id": checked["packet_id"], "premium_handoff_contract_version": LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": _premium_handoff_contract_v13(), "premium_handoff_contract_sha256": _canonical_hash(_premium_handoff_contract_v13()), "prepared_chart_signature_sha256": checked["prepared_chart_signature_sha256"], "prepared_signature_synthesis_sha256": checked["prepared_signature_synthesis_sha256"], "prepared_signature_syntheses": checked["prepared_signature_syntheses"], "reader_domain_manifest": checked["reader_domain_manifest"], "reader_domain_manifest_sha256": checked["reader_domain_manifest_sha256"], "reader_selection_plan": selection_plan, "reader_selection_plan_sha256": selection_plan_hash, "approved_reasoned_syntheses": approved_syntheses, "allowed_claims": checked["allowed_claims"], "synthesis_bundle_sha256": expected_synthesis_hash, "draft_report_sha256": _canonical_hash(draft), "timing_evidence_ids": checked["timing_evidence_ids"], "coverage": checked.get("coverage"), "chart_signature": checked["chart_signature"], "narrative_plan": checked["narrative_plan"]}


def _validate_premium_author_bundle_v14(
    birth: BirthData,
    author_bundle: Dict[str, object],
    profile: Optional[LocalizationProfile] = None,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
    include_timing: bool = True,
    prepared_handoff: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Deterministic Provenance Guard for the current 1.4 narrative contract."""
    items = author_bundle.get("reasoned_syntheses", [])
    _prepared_as_of, prepared_horizon, prepared_include_timing, _ = _verify_authoritative_prepared_handoff_v14(
        prepared_handoff, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    checked = validate_premium_syntheses(
        birth, items if isinstance(items, list) else [], profile,
        _prepared_as_of, prepared_horizon, prepared_include_timing,
        premium_contract_version=PREMIUM_HANDOFF_CONTRACT_VERSION,
    )
    _prepared_as_of, _prepared_horizon, _prepared_include_timing, errors = _verify_authoritative_prepared_handoff_v14(
        prepared_handoff, checked, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    errors.extend(_handoff_contract_errors_v14(author_bundle, "author"))
    if author_bundle.get("packet_id") != checked["packet_id"]:
        errors.append("packet_id_mismatch")
    for field in ("prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256"):
        if author_bundle.get(field) != checked.get(field):
            errors.append(f"{field}_mismatch")
    expected_synthesis_hash = _canonical_hash([item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"])
    if author_bundle.get("synthesis_bundle_sha256") != expected_synthesis_hash:
        errors.append("synthesis_bundle_hash_mismatch")
    draft = author_bundle.get("draft_report")
    if author_bundle.get("draft_report_sha256") != _canonical_hash(draft):
        errors.append("draft_report_hash_mismatch")
    approved_ids = {str(item["id"]) for item in checked["reasoned_synthesis"] if item["status"] == "allowed"}
    allowed_claims = {str(item["id"]): Claim(**item) for item in checked["allowed_claims"]}
    manifest = checked["reader_domain_manifest"]
    parsed = _parse_premium_narrative(draft, manifest)
    errors.extend(_validate_reader_sections(parsed, author_bundle.get("reader_sections"), manifest))
    source_errors, valid_sources = _validated_narrative_block_sources(
        draft, author_bundle.get("narrative_block_sources"), approved_ids, allowed_claims,
        set(checked["timing_evidence_ids"]), parsed,
    )
    errors.extend(source_errors)
    author_materialized_synthesis_ids = sorted(list({
        str(s_id)
        for src in valid_sources
        if isinstance(src, dict)
        for s_id in src.get("synthesis_ids", [])
    }))
    approved_syntheses = checked["approved_reasoned_syntheses"]
    errors.extend(_validate_subheading_sources(parsed, valid_sources, approved_syntheses, manifest))
    eligible_hashes = {
        str(item.get("narrative_block_sha256"))
        for item in parsed.get("eligible", []) if isinstance(item, dict)
    }
    errors.extend(_validate_mandatory_coverage_v14(draft, valid_sources, approved_syntheses, checked.get("coverage"), eligible_hashes))
    errors.extend(_validate_reader_domain_coverage(parsed, author_bundle.get("reader_sections"), valid_sources, approved_syntheses, manifest))
    selection_errors, selection_plan, selection_plan_hash = _validate_reader_selection_plan(
        author_bundle.get("reader_selection_plan"), author_bundle.get("reader_selection_plan_sha256"),
        parsed, valid_sources, approved_syntheses, manifest,
    )
    errors.extend(selection_errors)
    if isinstance(draft, str) and _contains_prohibited_extension(draft):
        errors.append("prohibited_extension_in_author_draft")
    if not birth.birth_time_known:
        errors.append("premium_birth_time_required")
    contract = _premium_handoff_contract()
    return {
        "stage": "deterministic_provenance_guard",
        "approved": checked["approved"] and not errors,
        "verification_errors": list(dict.fromkeys(errors)),
        "packet_id": checked["packet_id"],
        "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION,
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": _canonical_hash(contract),
        "prepared_chart_signature_sha256": checked["prepared_chart_signature_sha256"],
        "prepared_signature_synthesis_sha256": checked["prepared_signature_synthesis_sha256"],
        "prepared_signature_syntheses": checked["prepared_signature_syntheses"],
        "reader_domain_manifest": checked["reader_domain_manifest"],
        "reader_domain_manifest_sha256": checked["reader_domain_manifest_sha256"],
        "reader_selection_plan": selection_plan,
        "reader_selection_plan_sha256": selection_plan_hash,
        "approved_reasoned_syntheses": approved_syntheses,
        "author_materialized_synthesis_ids": author_materialized_synthesis_ids,
        "allowed_claims": checked["allowed_claims"],
        "synthesis_bundle_sha256": expected_synthesis_hash,
        "draft_report_sha256": _canonical_hash(draft),
        "timing_evidence_ids": checked["timing_evidence_ids"],
        "coverage": checked.get("coverage"),
        "chart_signature": checked["chart_signature"],
        "narrative_plan": checked["narrative_plan"],
    }


def _validate_premium_narrative_v13(
    narrative_payload: Dict[str, object],
    provenance: Dict[str, object],
    birth: BirthData,
    profile: Optional[LocalizationProfile] = None,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
    include_timing: bool = True,
    prepared_handoff: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Check publication provenance after the separate human/High narrative judge.

    This is intentionally a structural and safety gate.  An attestation by a
    High Narrative Judge is required for semantic equivalence; token checks do
    not claim to prove it.
    """
    prepared_as_of, prepared_horizon, prepared_include_timing, _ = _verify_authoritative_prepared_handoff_v13(
        prepared_handoff, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    authoritative = validate_premium_syntheses(
        birth, [], profile, prepared_as_of, prepared_horizon, prepared_include_timing,
        premium_contract_version=LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION,
    )
    _prepared_as_of, _prepared_horizon, _prepared_include_timing, preparation_errors = _verify_authoritative_prepared_handoff_v13(
        prepared_handoff, authoritative, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    approved_ids = {str(item.get("id")) for item in provenance.get("approved_reasoned_syntheses", [])}
    report = narrative_payload.get("final_report")
    errors = ([] if provenance.get("approved") else ["author_provenance_not_approved"]) + preparation_errors
    errors.extend(_handoff_contract_errors_v13(narrative_payload, "reviewer"))
    if provenance.get("premium_handoff_contract_version") != LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("provenance_handoff_contract_version_mismatch")
    if provenance.get("premium_handoff_contract_sha256") != _canonical_hash(_premium_handoff_contract_v13()):
        errors.append("provenance_handoff_contract_hash_mismatch")
    if provenance.get("premium_handoff_contract") != _premium_handoff_contract_v13():
        errors.append("provenance_handoff_contract_body_mismatch")
    if narrative_payload.get("packet_id") != provenance.get("packet_id"):
        errors.append("packet_id_mismatch")
    for field in ("prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256"):
        if narrative_payload.get(field) != provenance.get(field):
            errors.append(f"{field}_mismatch")
        if provenance.get(field) != authoritative.get(field):
            errors.append(f"provenance_{field}_mismatch")
        if narrative_payload.get(field) != authoritative.get(field):
            errors.append(f"authoritative_{field}_mismatch")
    if provenance.get("packet_id") != authoritative.get("packet_id"):
        errors.append("provenance_packet_id_mismatch")
    if provenance.get("chart_signature") != authoritative.get("chart_signature") or _canonical_hash(provenance.get("chart_signature")) != authoritative.get("prepared_chart_signature_sha256"):
        errors.append("provenance_chart_signature_mismatch")
    if provenance.get("prepared_signature_syntheses") != authoritative.get("prepared_signature_syntheses") or _canonical_hash(provenance.get("prepared_signature_syntheses")) != authoritative.get("prepared_signature_synthesis_sha256"):
        errors.append("provenance_signature_synthesis_basis_mismatch")
    manifest = provenance.get("reader_domain_manifest")
    reviewer_plan = narrative_payload.get("reader_selection_plan")
    reviewer_plan_hash = narrative_payload.get("reader_selection_plan_sha256")
    provenance_plan = provenance.get("reader_selection_plan")
    provenance_plan_hash = provenance.get("reader_selection_plan_sha256")
    if provenance_plan_hash != _canonical_hash(provenance_plan):
        errors.append("provenance_reader_selection_plan_hash_mismatch")
    if reviewer_plan != provenance_plan:
        errors.append("reader_selection_plan_body_mismatch")
    if reviewer_plan_hash != provenance_plan_hash or reviewer_plan_hash != _canonical_hash(reviewer_plan):
        errors.append("reader_selection_plan_hash_mismatch")
    if narrative_payload.get("synthesis_bundle_sha256") != provenance.get("synthesis_bundle_sha256"):
        errors.append("synthesis_bundle_hash_mismatch")
    if narrative_payload.get("reviewed_draft_sha256") != provenance.get("draft_report_sha256"):
        errors.append("reviewed_draft_hash_mismatch")
    verdict = narrative_payload.get("verdict")
    regeneration_request = narrative_payload.get("regeneration_request")
    if verdict not in {"approved", "regenerate_author", "blocked"}:
        errors.append("invalid_reviewer_verdict")
    if verdict == "approved" and regeneration_request is not None:
        errors.append("invalid_reviewer_regeneration_request")
    if verdict == "blocked":
        if regeneration_request is not None or not isinstance(narrative_payload.get("remaining_warnings"), list) or not any(
            isinstance(item, str) and item.strip() for item in narrative_payload.get("remaining_warnings", [])
        ):
            errors.append("invalid_reviewer_blocked_verdict")
    if verdict == "regenerate_author":
        if not isinstance(regeneration_request, dict) or set(regeneration_request) != {"items"} or not isinstance(regeneration_request.get("items"), list) or not regeneration_request["items"]:
            errors.append("invalid_reviewer_regeneration_request")
        else:
            manifest_paths = {
                str(domain["id"]): {str(path["id"]) for path in domain.get("legal_coverage_paths", [])}
                for domain in manifest.get("domains", []) if domain.get("availability") == "available"
            }
            seen_requested = set()
            for item in regeneration_request["items"]:
                if not isinstance(item, dict) or set(item) != {"domain_id", "path_ids", "reason"}:
                    errors.append("invalid_reviewer_regeneration_request")
                    continue
                domain_id, path_ids, reason = item.get("domain_id"), item.get("path_ids"), item.get("reason")
                if not isinstance(domain_id, str) or not isinstance(path_ids, list) or not path_ids or not all(isinstance(value, str) for value in path_ids) or len(path_ids) != len(set(path_ids)) or not isinstance(reason, str) or not reason.strip():
                    errors.append("invalid_reviewer_regeneration_request")
                    continue
                if domain_id not in manifest_paths or not set(path_ids).issubset(manifest_paths[domain_id]):
                    errors.append("invalid_reviewer_regeneration_request")
                for path_id in path_ids:
                    marker = (domain_id, path_id)
                    if marker in seen_requested:
                        errors.append("duplicate_reviewer_regeneration_request")
                    seen_requested.add(marker)
    if narrative_payload.get("final_report_sha256") != _canonical_hash(report):
        errors.append("final_report_hash_mismatch")
    allowed_claims = {str(item.get("id")): Claim(**item) for item in provenance.get("allowed_claims", []) if isinstance(item, dict) and item.get("status") == "allowed"}
    if _canonical_hash(manifest) != provenance.get("reader_domain_manifest_sha256"):
        errors.append("provenance_reader_domain_manifest_hash_mismatch")
    if manifest != authoritative.get("reader_domain_manifest"):
        errors.append("provenance_reader_domain_manifest_mismatch")
    # A non-approved Reviewer verdict is actionable only after its plan and
    # prepared lineage have been authenticated above.  It cannot publish a
    # report and does not require a second narrative parse to request a fresh
    # Author bundle.
    if verdict == "regenerate_author":
        return {
            "stage": "narrative_judged", "approved": False, "verification_errors": list(dict.fromkeys(errors)),
            "semantic_status": "author_regeneration_required" if not errors else "not_publishable",
            "report": None, "next_step": "regenerate_author" if not errors else None,
        }
    if verdict == "blocked":
        return {
            "stage": "narrative_judged", "approved": False, "verification_errors": list(dict.fromkeys(errors)),
            "semantic_status": "not_publishable", "report": None,
        }
    parsed = _parse_premium_narrative_v13(report, manifest)
    errors.extend(_validate_reader_sections_v13(parsed, narrative_payload.get("reader_sections"), manifest))
    source_errors, valid_sources = _validated_paragraph_sources_v13(report, narrative_payload.get("paragraph_sources"), approved_ids, allowed_claims, set(provenance.get("timing_evidence_ids", [])), parsed)
    errors.extend(source_errors)
    errors.extend(_validate_mandatory_coverage_v13(report, valid_sources, provenance.get("approved_reasoned_syntheses", []), provenance.get("coverage")))
    errors.extend(_validate_reader_domain_coverage_v13(parsed, narrative_payload.get("reader_sections"), valid_sources, provenance.get("approved_reasoned_syntheses", []), manifest))
    if isinstance(report, str) and _contains_prohibited_extension(report):
        errors.append("prohibited_extension_in_final_narrative")
    return {
        "stage": "narrative_judged",
        "approved": not errors,
        "verification_errors": errors,
        "semantic_status": "reviewer_attested_not_deterministically_proven" if not errors else "not_publishable",
        "report": report if not errors else None,
    }


def _validate_premium_narrative_v14(
    narrative_payload: Dict[str, object],
    provenance: Dict[str, object],
    birth: BirthData,
    profile: Optional[LocalizationProfile] = None,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
    include_timing: bool = True,
    prepared_handoff: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Publication Guard for the current 1.4 narrative block contract."""
    if not isinstance(narrative_payload, dict):
        return {
            "stage": "narrative_judged", "approved": False,
            "verification_errors": ["invalid_premium_handoff_reviewer_bundle_shape"],
            "semantic_status": "not_publishable", "report": None,
        }
    if not isinstance(provenance, dict):
        return {
            "stage": "narrative_judged", "approved": False,
            "verification_errors": ["invalid_premium_provenance_shape"],
            "semantic_status": "not_publishable", "report": None,
        }
    prepared_as_of, prepared_horizon, prepared_include_timing, _ = _verify_authoritative_prepared_handoff_v14(
        prepared_handoff, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    authoritative = validate_premium_syntheses(
        birth, [], profile, prepared_as_of, prepared_horizon, prepared_include_timing,
        premium_contract_version=PREMIUM_HANDOFF_CONTRACT_VERSION,
    )
    _prepared_as_of, _prepared_horizon, _prepared_include_timing, preparation_errors = _verify_authoritative_prepared_handoff_v14(
        prepared_handoff, authoritative, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    approved_ids = {str(item.get("id")) for item in provenance.get("approved_reasoned_syntheses", []) if isinstance(item, dict)}
    report = narrative_payload.get("final_report")
    errors = ([] if provenance.get("approved") else ["author_provenance_not_approved"]) + preparation_errors
    errors.extend(_handoff_contract_errors_v14(narrative_payload, "reviewer"))
    contract = _premium_handoff_contract()
    if provenance.get("premium_handoff_contract_version") != PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("provenance_handoff_contract_version_mismatch")
    if provenance.get("premium_handoff_contract_sha256") != _canonical_hash(contract):
        errors.append("provenance_handoff_contract_hash_mismatch")
    if provenance.get("premium_handoff_contract") != contract:
        errors.append("provenance_handoff_contract_body_mismatch")
    if narrative_payload.get("packet_id") != provenance.get("packet_id"):
        errors.append("packet_id_mismatch")
    for field in ("prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256"):
        if narrative_payload.get(field) != provenance.get(field):
            errors.append(f"{field}_mismatch")
        if provenance.get(field) != authoritative.get(field):
            errors.append(f"provenance_{field}_mismatch")
        if narrative_payload.get(field) != authoritative.get(field):
            errors.append(f"authoritative_{field}_mismatch")
    if provenance.get("packet_id") != authoritative.get("packet_id"):
        errors.append("provenance_packet_id_mismatch")
    if provenance.get("chart_signature") != authoritative.get("chart_signature") or _canonical_hash(provenance.get("chart_signature")) != authoritative.get("prepared_chart_signature_sha256"):
        errors.append("provenance_chart_signature_mismatch")
    if provenance.get("prepared_signature_syntheses") != authoritative.get("prepared_signature_syntheses") or _canonical_hash(provenance.get("prepared_signature_syntheses")) != authoritative.get("prepared_signature_synthesis_sha256"):
        errors.append("provenance_signature_synthesis_basis_mismatch")
    manifest = provenance.get("reader_domain_manifest")
    reviewer_plan = narrative_payload.get("reader_selection_plan")
    reviewer_plan_hash = narrative_payload.get("reader_selection_plan_sha256")
    provenance_plan = provenance.get("reader_selection_plan")
    provenance_plan_hash = provenance.get("reader_selection_plan_sha256")
    if provenance_plan_hash != _canonical_hash(provenance_plan):
        errors.append("provenance_reader_selection_plan_hash_mismatch")
    if reviewer_plan != provenance_plan:
        errors.append("reader_selection_plan_body_mismatch")
    if reviewer_plan_hash != provenance_plan_hash or reviewer_plan_hash != _canonical_hash(reviewer_plan):
        errors.append("reader_selection_plan_hash_mismatch")
    if narrative_payload.get("synthesis_bundle_sha256") != provenance.get("synthesis_bundle_sha256"):
        errors.append("synthesis_bundle_hash_mismatch")
    if narrative_payload.get("reviewed_draft_sha256") != provenance.get("draft_report_sha256"):
        errors.append("reviewed_draft_hash_mismatch")
    verdict = narrative_payload.get("verdict")
    regeneration_request = narrative_payload.get("regeneration_request")
    if verdict not in {"approved", "regenerate_author", "blocked"}:
        errors.append("invalid_reviewer_verdict")
    if verdict == "approved" and regeneration_request is not None:
        errors.append("invalid_reviewer_regeneration_request")
    if verdict == "blocked":
        if regeneration_request is not None or not isinstance(narrative_payload.get("remaining_warnings"), list) or not any(
            isinstance(item, str) and item.strip() for item in narrative_payload.get("remaining_warnings", [])
        ):
            errors.append("invalid_reviewer_blocked_verdict")
    if verdict == "regenerate_author":
        if not isinstance(regeneration_request, dict) or set(regeneration_request) != {"items"} or not isinstance(regeneration_request.get("items"), list) or not regeneration_request["items"]:
            errors.append("invalid_reviewer_regeneration_request")
        else:
            manifest_paths = {
                str(domain["id"]): {str(path["id"]) for path in domain.get("legal_coverage_paths", [])}
                for domain in manifest.get("domains", [])
                if isinstance(domain, dict) and domain.get("availability") == "available"
            } if isinstance(manifest, dict) else {}
            seen_requested = set()
            for item in regeneration_request["items"]:
                if not isinstance(item, dict) or set(item) != {"domain_id", "path_ids", "reason"}:
                    errors.append("invalid_reviewer_regeneration_request")
                    continue
                domain_id, path_ids, reason = item.get("domain_id"), item.get("path_ids"), item.get("reason")
                if not isinstance(domain_id, str) or not isinstance(path_ids, list) or not path_ids or not all(isinstance(value, str) for value in path_ids) or len(path_ids) != len(set(path_ids)) or not isinstance(reason, str) or not reason.strip():
                    errors.append("invalid_reviewer_regeneration_request")
                    continue
                if domain_id not in manifest_paths or not set(path_ids).issubset(manifest_paths[domain_id]):
                    errors.append("invalid_reviewer_regeneration_request")
                for path_id in path_ids:
                    marker = (domain_id, path_id)
                    if marker in seen_requested:
                        errors.append("duplicate_reviewer_regeneration_request")
                    seen_requested.add(marker)
    if narrative_payload.get("final_report_sha256") != _canonical_hash(report):
        errors.append("final_report_hash_mismatch")
    allowed_claims = {
        str(item.get("id")): Claim(**item)
        for item in provenance.get("allowed_claims", [])
        if isinstance(item, dict) and item.get("status") == "allowed"
    }
    if _canonical_hash(manifest) != provenance.get("reader_domain_manifest_sha256"):
        errors.append("provenance_reader_domain_manifest_hash_mismatch")
    if manifest != authoritative.get("reader_domain_manifest"):
        errors.append("provenance_reader_domain_manifest_mismatch")

    # A non-approved Reviewer verdict is actionable only after its plan and
    # prepared lineage have been authenticated above.
    if verdict == "regenerate_author":
        return {
            "stage": "narrative_judged", "approved": False, "verification_errors": list(dict.fromkeys(errors)),
            "semantic_status": "author_regeneration_required" if not errors else "not_publishable",
            "report": None, "next_step": "regenerate_author" if not errors else None,
        }
    if verdict == "blocked":
        return {
            "stage": "narrative_judged", "approved": False, "verification_errors": list(dict.fromkeys(errors)),
            "semantic_status": "not_publishable", "report": None,
        }

    parsed = _parse_premium_narrative(report, manifest)
    errors.extend(_validate_reader_sections(parsed, narrative_payload.get("reader_sections"), manifest))
    source_errors, valid_sources = _validated_narrative_block_sources(
        report, narrative_payload.get("narrative_block_sources"), approved_ids, allowed_claims,
        set(provenance.get("timing_evidence_ids", [])), parsed,
    )
    errors.extend(source_errors)
    author_materialized_ids = set(provenance.get("author_materialized_synthesis_ids") or [])
    if author_materialized_ids:
        for src in valid_sources:
            if isinstance(src, dict):
                for s_id in src.get("synthesis_ids", []):
                    if s_id not in author_materialized_ids:
                        errors.append(f"reviewer_unauthorized_synthesis_expansion:{s_id}")

    manifest_domain_map = {str(d["id"]): d for d in manifest.get("domains", []) if isinstance(d, dict)}
    entry_by_hash = {str(item.get("narrative_block_sha256")): item for item in parsed.get("authored", []) if isinstance(item, dict)}
    approved_by_id = {str(item.get("id")): item for item in provenance.get("approved_reasoned_syntheses", []) if isinstance(item, dict)}
    for src in valid_sources:
        if isinstance(src, dict):
            b_hash = str(src.get("narrative_block_sha256"))
            sec = entry_by_hash.get(b_hash, {}).get("section")
            if sec in manifest_domain_map:
                d_obj = manifest_domain_map[sec]
                d_paths = d_obj.get("legal_coverage_paths", [])
                for s_id in src.get("synthesis_ids", []):
                    s_obj = approved_by_id.get(str(s_id))
                    if s_obj:
                        matches_domain = any(_synthesis_matches_reader_path(s_obj, p) for p in d_paths)
                        if not matches_domain:
                            errors.append(f"reviewer_unauthorized_cross_domain_synthesis:{sec}:{s_id}")

    approved_syntheses = provenance.get("approved_reasoned_syntheses", [])
    errors.extend(_validate_subheading_sources(parsed, valid_sources, approved_syntheses, manifest))
    eligible_hashes = {
        str(item.get("narrative_block_sha256"))
        for item in parsed.get("eligible", []) if isinstance(item, dict)
    }
    errors.extend(_validate_mandatory_coverage_v14(report, valid_sources, approved_syntheses, provenance.get("coverage"), eligible_hashes))
    errors.extend(_validate_reader_domain_coverage(parsed, narrative_payload.get("reader_sections"), valid_sources, approved_syntheses, manifest))
    final_selection_errors, final_selection_plan, final_selection_plan_hash = _validate_reader_selection_plan(
        reviewer_plan, reviewer_plan_hash, parsed, valid_sources, approved_syntheses, manifest,
    )
    # Publication revalidates the complete plan against the final physical
    # report; a plan/hash that was valid for the draft cannot rescue missing
    # or reordered final paragraph/list-item provenance.
    errors.extend(final_selection_errors)
    if final_selection_plan != provenance_plan:
        errors.append("final_reader_selection_plan_mismatch")
    if final_selection_plan_hash != provenance_plan_hash:
        errors.append("final_reader_selection_plan_hash_mismatch")
    if isinstance(report, str) and _contains_prohibited_extension(report):
        errors.append("prohibited_extension_in_final_narrative")
    return {
        "stage": "narrative_judged",
        "approved": not errors,
        "verification_errors": list(dict.fromkeys(errors)),
        "semantic_status": "reviewer_attested_not_deterministically_proven" if not errors else "not_publishable",
        "report": report if not errors else None,
        "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION,
    }


def _authoritative_prepared_contract_version(prepared_handoff: object) -> Optional[str]:
    """Return only the version carried by the authoritative prepared handoff."""
    if not isinstance(prepared_handoff, dict):
        return None
    version = prepared_handoff.get("premium_handoff_contract_version")
    if version in {PREMIUM_HANDOFF_CONTRACT_VERSION, LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION}:
        return str(version)
    return None


def _missing_or_unsupported_premium_dispatch(prepared_handoff: object) -> Dict[str, object]:
    if not isinstance(prepared_handoff, dict):
        error = "missing_authoritative_prepared_handoff"
    else:
        error = "unsupported_premium_handoff_contract_version"
    return {
        "stage": "deterministic_provenance_guard",
        "approved": False,
        "verification_errors": [error],
        "semantic_status": "not_publishable",
    }


def validate_premium_author_bundle(
    birth: BirthData,
    author_bundle: Dict[str, object],
    profile: Optional[LocalizationProfile] = None,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
    include_timing: bool = True,
    prepared_handoff: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Dispatch Author validation only from the authoritative handoff version."""
    version = _authoritative_prepared_contract_version(prepared_handoff)
    if version is None:
        return _missing_or_unsupported_premium_dispatch(prepared_handoff)
    if version == LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION:
        if not isinstance(author_bundle, dict):
            return {"stage": "deterministic_provenance_guard", "approved": False, "verification_errors": ["invalid_premium_handoff_author_bundle_shape"]}
        return _validate_premium_author_bundle_v13(
            birth, author_bundle, profile, as_of, horizon_days, include_timing, prepared_handoff,
        )
    if not isinstance(author_bundle, dict):
        return {"stage": "deterministic_provenance_guard", "approved": False, "verification_errors": ["invalid_premium_handoff_author_bundle_shape"]}
    return _validate_premium_author_bundle_v14(
        birth, author_bundle, profile, as_of, horizon_days, include_timing, prepared_handoff,
    )


def validate_premium_narrative(
    narrative_payload: Dict[str, object],
    provenance: Dict[str, object],
    birth: BirthData,
    profile: Optional[LocalizationProfile] = None,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
    include_timing: bool = True,
    prepared_handoff: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Dispatch Publication validation only from the authoritative handoff version."""
    version = _authoritative_prepared_contract_version(prepared_handoff)
    if version is None:
        result = _missing_or_unsupported_premium_dispatch(prepared_handoff)
        result["stage"] = "narrative_judged"
        return result
    if version == LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION:
        return _validate_premium_narrative_v13(
            narrative_payload, provenance, birth, profile, as_of, horizon_days, include_timing, prepared_handoff,
        )
    return _validate_premium_narrative_v14(
        narrative_payload, provenance, birth, profile, as_of, horizon_days, include_timing, prepared_handoff,
    )


def _contains_prohibited_extension(text: str) -> bool:
    return bool(re.search(r"\b(trauma|diagn[oó]stico|diagnosis|morte|death|doen[cç]a|disease|gravidez|pregnancy|div[oó]rcio|divorce|fal[eê]ncia|bankruptcy|vai acontecer|will happen)\b", text, re.I))


def _require_premium_birth_time(birth: BirthData) -> None:
    if not birth.birth_time_known:
        raise ValueError("Premium beta requires a known local birth time. Use the limited safe deterministic reading when the time is unknown.")


# --- V2.2 Prospective Provenance & Production Bundle Construction ---

def compose_canonical_domain_syntheses(
    claims: Dict[str, Dict[str, object]],
    manifest: Dict[str, object],
    coverage: Dict[str, object],
) -> Tuple[List[Dict[str, object]], Dict[str, List[str]], List[str]]:
    """Compose domain syntheses and mandatory coverage syntheses from claims and manifest."""
    syntheses_dict: Dict[str, ReasonedSynthesis] = {}
    domain_sources: Dict[str, List[str]] = {}
    for domain in manifest.get("domains", []):
        if not isinstance(domain, dict) or domain.get("availability") != "available":
            continue
        d_id = str(domain["id"])
        paths = domain.get("legal_coverage_paths", [])
        if not paths:
            continue
        dom_synths: List[str] = []
        for path in paths:
            source_claims = [claims[item] for item in path.get("source_claim_ids", []) if item in claims]
            route_claim = next((item for item in source_claims if item.get("type") == "placidus_house_ruler"), None)
            if route_claim:
                house = str(route_claim["id"]).rsplit(".", 1)[-1]
                ruler_factor = next((item for item in path.get("primary_factor_ids", []) if str(item).startswith("position.")), None)
                r_name = str(ruler_factor).replace("position.", "") if ruler_factor else "ruler"
                synthesis_id = f"reasoned.house_ruler_context.placidus.{house}.{r_name}"
            else:
                p_id = str(path["id"])
                synthesis_id = f"reasoned.{p_id}"

            dom_synths.append(synthesis_id)
            if synthesis_id in syntheses_dict:
                continue

            statement = " ".join(str(item.get("statement", "")) for item in source_claims) or f"Leitura interpretativa do domínio {d_id}."
            s = ReasonedSynthesis(
                id=synthesis_id, observation=statement, primary_factors=list(path.get("primary_factor_ids", [])),
                modifiers=[], counterweights=[],
                reasoning_class=str(path.get("reasoning_class", "domain_synthesis")),
                confidence_within_astrological_model="light",
                possible_expressions=[statement], alternative_reading="", prohibited_extensions=[],
                source_claim_ids=list(path.get("source_claim_ids", [])),
                source_motif_ids=[motif for item in source_claims for motif in item.get("authorized_motifs", [])],
                composition_operations=list(path.get("composition_operations", [])),
                derived_propositions=[{"text": statement, "sources": list(path.get("source_claim_ids", []))}],
            )
            syntheses_dict[synthesis_id] = s

        domain_sources[d_id] = list(dict.fromkeys(dom_synths))

    required = coverage.get("required_evidence", {})
    by_evidence = {evidence: claim for claim in claims.values() for evidence in claim.get("evidence", [])}
    mandatory_ids: List[str] = []
    for ordinal, evidence in enumerate(sorted({item for values in required.values() for item in values}), 1):
        if evidence in by_evidence:
            claim = by_evidence[evidence]
            stmt = str(claim.get("statement", ""))
            s = ReasonedSynthesis(
                id=f"coverage.mandatory.{ordinal}", observation=stmt, primary_factors=[evidence], modifiers=[], counterweights=[],
                reasoning_class="single_structural_factor", confidence_within_astrological_model="light",
                possible_expressions=[stmt], alternative_reading="", prohibited_extensions=[],
                source_claim_ids=[str(claim.get("id"))], source_motif_ids=list(claim.get("authorized_motifs", [])),
                composition_operations=["contextualization"],
                derived_propositions=[{"text": stmt, "sources": [str(claim.get("id"))]}],
            )
            syntheses_dict[s.id] = s
            mandatory_ids.append(s.id)

    synths_list = [asdict(s) for s in syntheses_dict.values()]
    return synths_list, domain_sources, mandatory_ids


def validate_author_selection_plan(
    plan: Dict[str, object],
    manifest: Dict[str, object],
    approved_syntheses: Optional[Iterable[Dict[str, object]]] = None,
    handoff: Optional[Dict[str, object]] = None,
) -> Tuple[bool, List[str]]:
    """Validate the structural legality, completeness, and synthesis ancestry of an author selection plan."""
    errors: List[str] = []
    if not isinstance(plan, dict):
        return False, ["missing_plan_dict"]
    if plan.get("version") != "1.0":
        errors.append("invalid_plan_version")

    # Strict packet lineage check
    if handoff and isinstance(handoff, dict) and "packet_id" in handoff:
        plan_packet_id = plan.get("packet_id")
        if plan_packet_id and plan_packet_id != handoff["packet_id"]:
            errors.append(f"lineage_mismatch:plan_packet_id_{plan_packet_id}_vs_handoff_{handoff['packet_id']}")

    available = [
        d for d in manifest.get("domains", [])
        if isinstance(d, dict) and d.get("availability") == "available"
    ]
    plan_domains = plan.get("domains", [])
    if not isinstance(plan_domains, list):
        return False, ["invalid_domains_list"]
    domain_entry_map = {str(e.get("domain_id")): e for e in plan_domains if isinstance(e, dict)}

    # Extract approved syntheses if handoff provided
    if approved_syntheses is None and handoff is not None:
        if handoff.get("approved_reasoned_syntheses"):
            approved_syntheses = handoff["approved_reasoned_syntheses"]
        else:
            facts = handoff.get("reasoning_packet", {}).get("facts", {})
            claims_list = (
                facts.get("allowed_claims")
                or handoff.get("allowed_claims")
                or handoff.get("reasoning_packet", {}).get("claims")
                or []
            )
            claims_dict = {str(item["id"]): item for item in claims_list if isinstance(item, dict)}
            coverage = facts.get("coverage", {})
            composed, _, _ = compose_canonical_domain_syntheses(claims_dict, manifest, coverage)
            for c in composed:
                if isinstance(c, dict):
                    c["status"] = "allowed"
            sig_synths = handoff.get("prepared_signature_syntheses", [])
            approved_syntheses = [*composed, *sig_synths]
    approved = {
        str(item.get("id")): item
        for item in (approved_syntheses or [])
        if isinstance(item, dict) and item.get("status") == "allowed"
    }

    for d in available:
        d_id = str(d["id"])
        if d_id not in domain_entry_map:
            errors.append(f"missing_domain:{d_id}")
            continue
        d_entry = domain_entry_map[d_id]
        legal_paths = d.get("legal_coverage_paths", [])
        expected_ids = [str(p["id"]) for p in legal_paths]
        path_by_id = {str(p["id"]): p for p in legal_paths}
        path_entries = d_entry.get("paths", [])
        if not isinstance(path_entries, list):
            errors.append(f"invalid_paths_list:{d_id}")
            continue

        # Enforce coverage contract: every available domain must have at least one represented path
        represented_in_domain = [
            pe for pe in path_entries if isinstance(pe, dict) and pe.get("decision") == "represented"
        ]
        if not represented_in_domain:
            errors.append(f"domain_has_no_represented_paths:{d_id}")

        path_map = {str(pe.get("path_id")): pe for pe in path_entries if isinstance(pe, dict)}

        for pid in expected_ids:
            if pid not in path_map:
                errors.append(f"missing_path:{d_id}:{pid}")
                continue
            pe = path_map[pid]
            decision = pe.get("decision")
            if decision not in {"represented", "merged_with_represented", "omitted_no_distinct_reader_value"}:
                errors.append(f"invalid_decision:{pid}:{decision}")
            if decision == "represented":
                s_ids = pe.get("synthesis_ids")
                if not s_ids or not isinstance(s_ids, list):
                    errors.append(f"represented_path_missing_synthesis_ids:{pid}")
                else:
                    if len(s_ids) != len(set(s_ids)):
                        errors.append(f"duplicate_synthesis_ids:{pid}")
                    if approved:
                        for s_id in s_ids:
                            if str(s_id) not in approved:
                                errors.append(f"unknown_synthesis_id:{pid}:{s_id}")
                if pe.get("merged_with_path_id") is not None:
                    errors.append(f"represented_path_cannot_have_merge_target:{pid}")
                if pe.get("rationale") is not None:
                    errors.append(f"represented_path_cannot_have_rationale:{pid}")
            elif decision == "merged_with_represented":
                tgt = pe.get("merged_with_path_id")
                if not tgt or tgt not in path_map:
                    errors.append(f"invalid_merge_target:{pid}:{tgt}")
                elif path_map[tgt].get("decision") != "represented":
                    errors.append(f"merge_target_must_be_represented:{pid}:{tgt}")
                if not pe.get("rationale") or not str(pe.get("rationale")).strip():
                    errors.append(f"missing_merge_rationale:{pid}")
                if pe.get("synthesis_ids"):
                    errors.append(f"merged_path_cannot_have_synthesis_ids:{pid}")
            elif decision == "omitted_no_distinct_reader_value":
                if not pe.get("rationale") or not str(pe.get("rationale")).strip():
                    errors.append(f"missing_omission_rationale:{pid}")
                if pe.get("merged_with_path_id") is not None:
                    errors.append(f"omitted_path_cannot_have_merge_target:{pid}")
                if pe.get("synthesis_ids"):
                    errors.append(f"omitted_path_cannot_have_synthesis_ids:{pid}")

        # Deep Ancestry and Cluster Validation when approved syntheses are available
        if approved:
            for target_id, target in path_map.items():
                if not isinstance(target, dict) or target.get("decision") != "represented" or target_id not in path_by_id:
                    continue
                cluster_ids = [target_id, *[
                    pid for pid, item in path_map.items()
                    if isinstance(item, dict) and item.get("decision") == "merged_with_represented" and str(item.get("merged_with_path_id")) == target_id
                ]]
                synthesis_ids = target.get("synthesis_ids", [])
                members = [approved[item] for item in synthesis_ids if item in approved]
                contributing: set[str] = set()
                for cluster_path_id in cluster_ids:
                    if cluster_path_id not in path_by_id:
                        continue
                    matched, contributors = _selection_synthesis_set_matches_path(members, path_by_id[cluster_path_id])
                    if not matched:
                        errors.append(f"reader_selection_insufficient_set_ancestry:{cluster_path_id}")
                    contributing.update(contributors)
                if set(synthesis_ids) - contributing:
                    errors.append(f"reader_selection_noncontributing_synthesis_padding:{target_id}")
                if d_id == "active_life_chapter":
                    synthesis_timing = {
                        str(factor) for member in members for factor in member.get("primary_factors", []) if str(factor).startswith("timing.")
                    }
                    path_timing = {
                        str(timing_id) for cluster_path_id in cluster_ids
                        for timing_id in path_by_id[cluster_path_id].get("timing_ids", [])
                    }
                    if synthesis_timing != path_timing:
                        errors.append(f"reader_selection_timing_cluster_mismatch:{target_id}")

    return (len(errors) == 0, errors)


def build_canonical_selection_plan(
    manifest: Dict[str, object],
    domain_sources: Optional[Dict[str, List[str]]] = None,
    author_selection_plan: Optional[Dict[str, object]] = None,
    *,
    allow_conservative_fallback: bool = False,
    approved_syntheses: Optional[Iterable[Dict[str, object]]] = None,
    handoff: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Validate an Author-owned ReaderSelectionPlan, or build a conservative fallback for test/headless use.

    In production, author_selection_plan is required (fails closed).
    The conservative test fallback marks ALL legal paths as represented with no merges
    and no omissions, eliminating all Python-level editorial or ranking decisions.
    """
    if author_selection_plan is not None:
        valid, errors = validate_author_selection_plan(
            author_selection_plan, manifest, approved_syntheses=approved_syntheses, handoff=handoff
        )
        if not valid:
            raise ValueError("Invalid author selection plan: " + ", ".join(errors[:5]))
        return author_selection_plan

    if not allow_conservative_fallback:
        raise ValueError("author_selection_plan is required: Premium Complete fails closed without an Author-owned selection plan.")

    domains_out: List[Dict[str, object]] = []
    for domain in manifest.get("domains", []):
        if not isinstance(domain, dict) or domain.get("availability") != "available":
            continue
        domain_id = str(domain["id"])
        paths = domain.get("legal_coverage_paths", [])
        if not paths:
            continue

        def _path_synth_id(p: Dict[str, object]) -> str:
            s_claims = p.get("source_claim_ids", [])
            route_c = next((c for c in s_claims if "house_ruler.placidus." in str(c)), None)
            if route_c:
                house = str(route_c).rsplit(".", 1)[-1]
                ruler_f = next((item for item in p.get("primary_factor_ids", []) if str(item).startswith("position.")), None)
                r_name = str(ruler_f).replace("position.", "") if ruler_f else "ruler"
                return f"reasoned.house_ruler_context.placidus.{house}.{r_name}"
            pid = str(p["id"])
            return f"reasoned.{pid}"

        path_entries: List[Dict[str, object]] = []
        for p in sorted(paths, key=lambda item: str(item.get("id"))):
            p_id = str(p["id"])
            path_entries.append({
                "path_id": p_id,
                "decision": "represented",
                "synthesis_ids": [_path_synth_id(p)],
                "merged_with_path_id": None,
                "rationale": None,
            })

        domains_out.append({"domain_id": domain_id, "paths": path_entries})

    return {"version": "1.0", "domains": domains_out}


def plan_prospective_narrative_blocks(
    handoff: Dict[str, object],
    selection_plan: Optional[Dict[str, object]] = None,
    author_selection_plan: Optional[Dict[str, object]] = None,
    *,
    allow_conservative_fallback: bool = False,
) -> Dict[str, object]:
    """Create a prospective block plan establishing source selection before prose generation.

    Enforces the invariant: Source selection precedes prose generation.
    In production, a validated author_selection_plan is mandatory (fails closed).
    """
    manifest = handoff["reader_domain_manifest"]
    if not isinstance(manifest, dict):
        raise ValueError("Invalid reader_domain_manifest in handoff")

    facts = handoff.get("reasoning_packet", {}).get("facts", {})
    claims_list = (
        facts.get("allowed_claims")
        or handoff.get("allowed_claims")
        or handoff.get("reasoning_packet", {}).get("claims")
        or []
    )
    claims_dict = {str(item["id"]): item for item in claims_list if isinstance(item, dict)}
    coverage = facts.get("coverage", {})

    composed_synths, domain_sources, mandatory_ids = compose_canonical_domain_syntheses(claims_dict, manifest, coverage)
    for c in composed_synths:
        if isinstance(c, dict):
            c["status"] = "allowed"

    available_domains = [d for d in manifest.get("domains", []) if isinstance(d, dict) and d.get("availability") == "available"]

    # Identify primary domain syntheses from selection plan or manifest defaults
    effective_selection = author_selection_plan or selection_plan
    approved_synths = (
        handoff.get("approved_reasoned_syntheses")
        or [*composed_synths, *handoff.get("prepared_signature_syntheses", [])]
    )
    if effective_selection is None and not handoff.get("reader_selection_plan"):
        if not allow_conservative_fallback:
            raise ValueError(
                "author_selection_plan is required for prospective narrative block planning; "
                "production pipeline fails closed without validated author selection."
            )
        sel_plan = build_canonical_selection_plan(
            manifest,
            domain_sources=domain_sources,
            allow_conservative_fallback=True,
            approved_syntheses=approved_synths,
            handoff=handoff,
        )
    else:
        sel_plan = effective_selection or handoff.get("reader_selection_plan")
        if sel_plan.get("packet_id") and handoff.get("packet_id") and sel_plan["packet_id"] != handoff["packet_id"]:
            raise LineageMismatchError(
                f"Selection plan packet_id {sel_plan.get('packet_id')} does not match handoff packet_id {handoff.get('packet_id')}"
            )
        valid, errors = validate_author_selection_plan(
            sel_plan,
            manifest,
            approved_syntheses=approved_synths,
            handoff=handoff,
        )
        if not valid:
            raise SelectionPlanValidationError("Invalid reader selection plan: " + ", ".join(errors[:5]))
    plan_by_domain: Dict[str, Dict[str, object]] = {}

    for d_entry in sel_plan.get("domains", []):
        if isinstance(d_entry, dict):
            plan_by_domain[str(d_entry.get("domain_id"))] = d_entry

    # Identify relational synthesis candidates
    prepared_synths = handoff.get("prepared_signature_syntheses", [])
    relational_candidates = [
        s["id"] for s in prepared_synths
        if isinstance(s, dict) and s.get("reasoning_class") in {"integrated_pattern", "theme_interaction"}
        and not any(str(c).startswith("claim.house_ruler.placidus.") for c in s.get("source_claim_ids", []))
    ]
    primary_relational = relational_candidates[0] if relational_candidates else "reasoned.competence"
    secondary_relational = relational_candidates[1] if len(relational_candidates) > 1 else primary_relational

    sections_plan: Dict[str, List[Dict[str, object]]] = {}

    # 1. Opening: 2 relational blocks weaving mandatory items together
    half_m = len(mandatory_ids) // 2
    first_half_m = mandatory_ids[:half_m]
    second_half_m = mandatory_ids[half_m:]

    sections_plan["opening"] = [
        {
            "block_index": 0,
            "kind": "paragraph",
            "synthesis_ids": [primary_relational, *first_half_m],
            "claim_ids": [],
            "timing_ids": [],
            "intended_mechanism": "Síntese relacional de ordem superior dos centros de gravidade do mapa e eixos estruturantes",
        },
        {
            "block_index": 1,
            "kind": "paragraph",
            "synthesis_ids": [secondary_relational, *second_half_m],
            "claim_ids": [],
            "timing_ids": [],
            "intended_mechanism": "Tensões dinâmicas fundamentais, polaridades e integração dos recursos vitais",
        },
    ]

    # 2. Domains: each available domain plans blocks based on represented paths
    for d in available_domains:
        d_id = str(d["id"])
        domain_entry = plan_by_domain.get(d_id, {})
        represented_paths = [
            p for p in domain_entry.get("paths", [])
            if isinstance(p, dict) and p.get("decision") == "represented"
        ]
        path_by_id = {str(p["id"]): p for p in d.get("legal_coverage_paths", [])}

        blocks = []
        if represented_paths:
            for b_idx, rp in enumerate(represented_paths):
                rp_id = str(rp["path_id"])
                p_obj = path_by_id.get(rp_id, {})
                t_ids = list(map(str, p_obj.get("timing_ids", []))) if d_id == "active_life_chapter" else []
                blocks.append({
                    "block_index": b_idx,
                    "kind": "paragraph",
                    "synthesis_ids": list(rp.get("synthesis_ids", [])),
                    "claim_ids": [],
                    "timing_ids": t_ids,
                    "intended_mechanism": f"Mecanismo de {rp_id} no domínio {d_id}",
                })
        else:
            raise SelectionPlanValidationError(f"Available domain '{d_id}' has no represented paths in selection plan")

        sections_plan[d_id] = blocks

    # Align domain_sources strictly with the selection plan's represented paths
    aligned_domain_sources: Dict[str, List[str]] = {}
    for d in available_domains:
        d_id = str(d["id"])
        domain_entry = plan_by_domain.get(d_id, {})
        represented_paths = [
            p for p in domain_entry.get("paths", [])
            if isinstance(p, dict) and p.get("decision") == "represented"
        ]
        s_ids = []
        for rp in represented_paths:
            s_ids.extend(rp.get("synthesis_ids", []))
        aligned_domain_sources[d_id] = list(dict.fromkeys(s_ids or domain_sources.get(d_id, [f"reasoned.reader.{d_id}"])))

    # 3. Integration: higher-order synthesis
    sections_plan["integration"] = [
        {
            "block_index": 0,
            "kind": "paragraph",
            "synthesis_ids": [primary_relational],
            "claim_ids": [],
            "timing_ids": [],
            "intended_mechanism": "Síntese de ordem superior organizando a pessoa como um todo e pergunta reflexiva final",
        }
    ]

    plan_payload = {
        "plan_version": "1.0",
        "packet_id": handoff["packet_id"],
        "sections": sections_plan,
        "composed_syntheses": composed_synths,
        "domain_sources": aligned_domain_sources,
        "mandatory_ids": mandatory_ids,
        "primary_relational": primary_relational,
        "selection_plan": sel_plan,
    }
    plan_payload["plan_sha256"] = _canonical_hash({k: v for k, v in plan_payload.items() if k != "composed_syntheses"})
    return plan_payload


def bind_prospective_plan_to_prose(
    draft_report: str,
    block_plan: Dict[str, object],
    manifest: Dict[str, object],
) -> Tuple[List[Dict[str, object]], Dict[str, object], Dict[str, object]]:
    """Bind authored narrative blocks to a pre-selected prospective block plan.

    Hashes are computed from the resulting prose, while sources derive from the plan.
    """
    parsed = _parse_premium_narrative(draft_report, manifest)
    if parsed.get("errors"):
        raise ValueError("Cannot bind prose with parse errors: " + ", ".join(parsed["errors"]))

    sections_plan = block_plan.get("sections", {})
    sources: List[Dict[str, object]] = []
    ownership: Dict[str, object] = {
        "opening": {"narrative_block_sha256s": []},
        "domains": [],
        "integration": {"narrative_block_sha256s": []},
    }

    # Opening
    opening_blks = parsed["sections"]["opening"]["authored"]
    planned_opening = sections_plan.get("opening", [])
    ownership["opening"]["narrative_block_sha256s"] = [str(b["narrative_block_sha256"]) for b in opening_blks]
    all_mandatory_s = block_plan.get("mandatory_ids", [])
    primary_rel = block_plan.get("primary_relational", "reasoned.competence")
    sec_rel = block_plan.get("secondary_relational") or primary_rel

    composed_synths_by_id = {
        s["id"]: s for s in block_plan.get("composed_syntheses", [])
        if isinstance(s, dict)
    }

    _PLANET_PATTERNS = {
        "sun": [r"\bsol\b", r"\bsolar\b", r"\bsun\b"],
        "moon": [r"\blua\b", r"\blunar\b", r"\bmoon\b"],
        "mercury": [r"\bmercúrio\b", r"\bmercurio\b", r"\bmercury\b"],
        "venus": [r"\bvênus\b", r"\bvenus\b"],
        "mars": [r"\bmarte\b", r"\bmars\b"],
        "jupiter": [r"\bjúpiter\b", r"\bjupiter\b", r"\bjupiterian[ao]?\b"],
        "saturn": [r"\bsaturno\b", r"\bsaturn\b", r"\bsaturnin[ao]?\b"],
        "uranus": [r"\burano\b", r"\buranus\b"],
        "neptune": [r"\bnetuno\b", r"\bneptune\b"],
        "pluto": [r"\bplutão\b", r"\bplutao\b", r"\bpluto\b"],
        "chiron": [r"\bquíron\b", r"\bquiron\b", r"\bchiron\b"],
        "lilith": [r"\blilith\b"],
    }

    _HOUSE_PATTERNS = {
        "1": [
            r"\b(?:casa|house)\s+(?:1|i|um|uma|one)\b",
            r"\b1[ªaºo][\s-]+(?:casa|house)\b",
            r"\b1st[\s-]+house\b",
            r"\b(?<!d[eé]cima[\s-])primeira[\s-]+casa\b",
            r"\bfirst[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+(?<!d[eé]cima[\s-])primeira\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+first\b",
            r"\bascendente\b", r"\bascendant\b", r"\basc\b",
        ],
        "2": [
            r"\b(?:casa|house)\s+(?:2|ii|dois|duas|two)\b",
            r"\b2[ªaºo][\s-]+(?:casa|house)\b",
            r"\b2nd[\s-]+house\b",
            r"\b(?<!d[eé]cima[\s-])segunda[\s-]+casa\b",
            r"\bsecond[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+(?<!d[eé]cima[\s-])segunda\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+second\b",
        ],
        "3": [
            r"\b(?:casa|house)\s+(?:3|iii|tr[eê]s|three)\b",
            r"\b3[ªaºo][\s-]+(?:casa|house)\b",
            r"\b3rd[\s-]+house\b",
            r"\bterceira[\s-]+casa\b",
            r"\bthird[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+terceira\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+third\b",
        ],
        "4": [
            r"\b(?:casa|house)\s+(?:4|iv|quatro|four)\b",
            r"\b4[ªaºo][\s-]+(?:casa|house)\b",
            r"\b4th[\s-]+house\b",
            r"\bquarta[\s-]+casa\b",
            r"\bfourth[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+quarta\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+fourth\b",
            r"\bfundo do céu\b", r"\bfundo do ceu\b", r"\bfundo-do-céu\b", r"\bfundo-do-ceu\b", r"\bimum coeli\b", r"\bic\b",
        ],
        "5": [
            r"\b(?:casa|house)\s+(?:5|v|cinco|five)\b",
            r"\b5[ªaºo][\s-]+(?:casa|house)\b",
            r"\b5th[\s-]+house\b",
            r"\bquinta[\s-]+casa\b",
            r"\bfifth[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+quinta\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+fifth\b",
        ],
        "6": [
            r"\b(?:casa|house)\s+(?:6|vi|seis|six)\b",
            r"\b6[ªaºo][\s-]+(?:casa|house)\b",
            r"\b6th[\s-]+house\b",
            r"\bsexta[\s-]+casa\b",
            r"\bsixth[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+sexta\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+sixth\b",
        ],
        "7": [
            r"\b(?:casa|house)\s+(?:7|vii|sete|seven)\b",
            r"\b7[ªaºo][\s-]+(?:casa|house)\b",
            r"\b7th[\s-]+house\b",
            r"\bs[eé]tima[\s-]+casa\b",
            r"\bseventh[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+s[eé]tima\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+seventh\b",
            r"\bdescendente\b", r"\bdescendant\b", r"\bdsc\b",
        ],
        "8": [
            r"\b(?:casa|house)\s+(?:8|viii|oito|eight)\b",
            r"\b8[ªaºo][\s-]+(?:casa|house)\b",
            r"\b8th[\s-]+house\b",
            r"\boitava[\s-]+casa\b",
            r"\beighth[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+oitava\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+eighth\b",
        ],
        "9": [
            r"\b(?:casa|house)\s+(?:9|ix|nove|nine)\b",
            r"\b9[ªaºo][\s-]+(?:casa|house)\b",
            r"\b9th[\s-]+house\b",
            r"\bnona[\s-]+casa\b",
            r"\bninth[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+nona\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+ninth\b",
        ],
        "10": [
            r"\b(?:casa|house)\s+(?:10|x|dez|ten)\b",
            r"\b10[ªaºo][\s-]+(?:casa|house)\b",
            r"\b10th[\s-]+house\b",
            r"\bd[eé]cima[\s-]+casa\b",
            r"\btenth[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+d[eé]cima\b(?![\s-](?:primeira|segunda))",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+tenth\b",
            r"\bmeio do céu\b", r"\bmeio do ceu\b", r"\bmeio-do-céu\b", r"\bmeio-do-ceu\b", r"\bmc\b", r"\bmidheaven\b",
        ],
        "11": [
            r"\b(?:casa|house)\s+(?:11|xi|onze|eleven)\b",
            r"\b11[ªaºo][\s-]+(?:casa|house)\b",
            r"\b11th[\s-]+house\b",
            r"\bd[eé]cima[\s-]primeira[\s-]+casa\b",
            r"\beleventh[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+d[eé]cima[\s-]primeira\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+eleventh\b",
        ],
        "12": [
            r"\b(?:casa|house)\s+(?:12|xii|doze|twelve)\b",
            r"\b12[ªaºo][\s-]+(?:casa|house)\b",
            r"\b12th[\s-]+house\b",
            r"\bd[eé]cima[\s-]segunda[\s-]+casa\b",
            r"\btwelfth[\s-]+house\b",
            r"\b(?:regente|regência|regencia|cúspide|cuspide|governança|governanca|da|na|pela|a)\s+d[eé]cima[\s-]segunda\b",
            r"\b(?:ruler\s+of(?:\s+the)?|cusp\s+of(?:\s+the)?|in(?:\s+the)?)\s+twelfth\b",
        ],
    }

    def _extract_synthesis_patterns(synth: Dict[str, object]) -> List[str]:
        patterns = []
        sid = str(synth.get("id", ""))
        factors = [str(f) for f in synth.get("primary_factors", [])]
        claims = [str(c) for c in synth.get("source_claim_ids", [])]
        all_tokens = [sid] + factors + claims

        for p, pats in _PLANET_PATTERNS.items():
            if any(re.search(r"(?:^|[._])" + p + r"(?:[._]|$)", t) or (p == "lilith" and "lilith_mean" in t) for t in all_tokens):
                patterns.extend(pats)

        for t in all_tokens:
            for h in re.findall(r"(?:placidus|house)[._](\d+)\b", t):
                if h in _HOUSE_PATTERNS:
                    patterns.extend(_HOUSE_PATTERNS[h])

        if any("ascendant" in t or "angle.asc" in t or t.endswith(".asc") for t in all_tokens):
            patterns.extend([r"\bascendente\b", r"\bascendant\b", r"\basc\b"])
        if any("midheaven" in t or "angle.mc" in t or t.endswith(".mc") for t in all_tokens):
            patterns.extend([r"\bmeio do céu\b", r"\bmeio do ceu\b", r"\bmeio-do-céu\b", r"\bmeio-do-ceu\b", r"\bmc\b", r"\bmidheaven\b"])
        if any("descendant" in t or "angle.dsc" in t or t.endswith(".dsc") for t in all_tokens):
            patterns.extend([r"\bdescendente\b", r"\bdescendant\b", r"\bdsc\b"])
        if any("imum_coeli" in t or "angle.ic" in t or t.endswith(".ic") for t in all_tokens):
            patterns.extend([r"\bfundo do céu\b", r"\bfundo do ceu\b", r"\bfundo-do-céu\b", r"\bfundo-do-ceu\b", r"\bic\b", r"\bimum coeli\b"])
        if any("chart_ruler" in t for t in all_tokens):
            patterns.extend([r"\bregente do mapa\b", r"\bregente do ascendente\b", r"\bchart ruler\b"])
        if any("node" in t for t in all_tokens):
            patterns.extend([r"\bnodo\b", r"\bnó lunar\b", r"\beixo nodal\b", r"\bnodal axis\b", r"\bnode\b"])
        if any("stellium" in t for t in all_tokens):
            patterns.extend([r"\bstellium\b", r"\bconcentração\b", r"\bacumulação\b"])
        if any("profection" in t for t in all_tokens):
            patterns.extend([r"\bprofecç[aã]o\b", r"\bprofection\b", r"\bsenhor do ano\b", r"\btime lord\b"])
        if any("progression" in t or "secondary_progression" in t for t in all_tokens):
            patterns.extend([r"\bprogress[aã]o\b", r"\bprogression\b", r"\bsecund[aá]ria\b"])
        if any("solar_arc" in t for t in all_tokens):
            patterns.extend([r"\barco solar\b", r"\bsolar arc\b"])
        if any("transit" in t for t in all_tokens):
            patterns.extend([r"\btr[aâ]nsito\b", r"\btransit\b"])

        _SIGN_PATTERNS = {
            "aries": [r"\b[aá]ries\b", r"\bariano[as]?\b"],
            "taurus": [r"\btouro\b", r"\btaurino[as]?\b"],
            "gemini": [r"\bg[eê]meos\b", r"\bgeminiano[as]?\b"],
            "cancer": [r"\bc[aâ]ncer\b", r"\bcanceriano[as]?\b"],
            "leo": [r"\ble[aã]o\b", r"\bleonino[as]?\b"],
            "virgo": [r"\bvirgem\b", r"\bvirginiano[as]?\b"],
            "libra": [r"\blibra\b", r"\blibriano[as]?\b"],
            "scorpio": [r"\bescorpi[aã]o\b", r"\bescorpiano[as]?\b"],
            "sagittarius": [r"\bsagit[aá]rio\b", r"\bsagitariano[as]?\b"],
            "capricorn": [r"\bcapric[oó]rnio\b", r"\bcapricorniano[as]?\b"],
            "aquarius": [r"\baqu[aá]rio\b", r"\baquariano[as]?\b"],
            "pisces": [r"\bpeixes\b", r"\bpisciano[as]?\b"],
        }
        for sgn, s_pats in _SIGN_PATTERNS.items():
            if any(re.search(r"(?:^|[._])" + sgn + r"(?:[._]|$)", t) for t in all_tokens):
                patterns.extend(s_pats)

        if any("growth_through_contradiction" in t for t in all_tokens):
            patterns.extend([r"\bpolaridade\b", r"\bcontradiç[aã]o\b", r"\btens[aã]o\b", r"\bpolos?\b", r"\boposiç[aã]o\b", r"\bquadratura\b"])
        if any("shadow_defenses_patterns" in t for t in all_tokens):
            patterns.extend([r"\bsombra\b", r"\bdefesa[s]?\b", r"\bpadr[aã]o\b", r"\breativo[as]?\b", r"\bexcesso\b"])
        if any("developmental_direction" in t for t in all_tokens):
            patterns.extend([r"\bdireç[aã]o\b", r"\bevolu[çc][aã]o\b", r"\bdesenvolvimento\b", r"\bpropósito\b", r"\bproposito\b"])

        return list(set(patterns))


    unmaterialized_mandatories: List[str] = []
    matched_mandatories_all_blocks: set[str] = set()

    for i, blk in enumerate(opening_blks):
        blk_text = str(blk.get("text", "")).casefold()
        rel_candidates = [primary_rel, sec_rel] if sec_rel != primary_rel else [primary_rel]
        rel_synth = rel_candidates[i % len(rel_candidates)]
        matching_mandatories = []
        for m_id in all_mandatory_s:
            s_obj = composed_synths_by_id.get(m_id)
            if s_obj:
                pats = _extract_synthesis_patterns(s_obj)
                if any(re.search(p, blk_text) for p in pats):
                    matching_mandatories.append(m_id)
                    matched_mandatories_all_blocks.add(m_id)

        # FAIL-CLOSED: strictly no fallback to planned_opening when no mandatory patterns match
        s_list = list(dict.fromkeys([rel_synth, *matching_mandatories]))
        sources.append({
            "narrative_block_sha256": str(blk["narrative_block_sha256"]),
            "synthesis_ids": s_list,
            "claim_ids": [],
            "timing_ids": [],
        })

    for m_id in all_mandatory_s:
        if m_id not in matched_mandatories_all_blocks:
            unmaterialized_mandatories.append(m_id)

    # Domains
    domain_sources_map = block_plan.get("domain_sources", {})
    unmaterialized_planned_sources: List[Dict[str, str]] = []
    blocks_without_semantic_source: List[Dict[str, object]] = []

    for domain in manifest.get("domains", []):
        if not isinstance(domain, dict) or domain.get("availability") != "available":
            continue
        d_id = str(domain["id"])
        dom_blks = parsed["sections"][d_id]["authored"]
        ownership["domains"].append({
            "domain_id": d_id,
            "narrative_block_sha256s": [str(b["narrative_block_sha256"]) for b in dom_blks],
        })
        planned_dom = sections_plan.get(d_id, [])
        all_d_synths = domain_sources_map.get(d_id) or [f"reasoned.reader.{d_id}"]

        if d_id == "active_life_chapter":
            scores_by_block: List[Dict[str, int]] = []
            for blk in dom_blks:
                blk_text = str(blk.get("text", "")).casefold()
                blk_scores: Dict[str, int] = {}
                for sid in all_d_synths:
                    s_obj = composed_synths_by_id.get(sid)
                    if s_obj:
                        pats = _extract_synthesis_patterns(s_obj)
                        blk_scores[sid] = sum(1 for p in pats if re.search(p, blk_text))
                    else:
                        blk_scores[sid] = 0
                scores_by_block.append(blk_scores)

            materialized_timing = [
                sid for sid in all_d_synths
                if max(scores_by_block[k].get(sid, 0) for k in range(len(dom_blks))) > 0
            ]
            for bi, blk in enumerate(dom_blks):
                matched_synths = [sid for sid in all_d_synths if scores_by_block[bi].get(sid, 0) > 0]
                if not matched_synths and materialized_timing:
                    matched_synths = [materialized_timing[0]]
                t_ids = planned_dom[0].get("timing_ids", []) if (planned_dom and matched_synths) else []
                if not matched_synths and not t_ids:
                    blocks_without_semantic_source.append({
                        "domain_id": d_id,
                        "block_index": bi,
                        "sha256": str(blk["narrative_block_sha256"]),
                    })
                sources.append({
                    "narrative_block_sha256": str(blk["narrative_block_sha256"]),
                    "synthesis_ids": list(dict.fromkeys(matched_synths)),
                    "claim_ids": [],
                    "timing_ids": t_ids,
                })
            continue

        # Score each synthesis semantically across blocks in this domain
        scores_by_block: List[Dict[str, int]] = []
        for blk in dom_blks:
            blk_text = str(blk.get("text", "")).casefold()
            blk_scores: Dict[str, int] = {}
            for sid in all_d_synths:
                s_obj = composed_synths_by_id.get(sid)
                if s_obj:
                    pats = _extract_synthesis_patterns(s_obj)
                    blk_scores[sid] = sum(1 for p in pats if re.search(p, blk_text))
                else:
                    blk_scores[sid] = 0
            scores_by_block.append(blk_scores)

        assigned_by_block: List[List[str]] = [[] for _ in range(len(dom_blks))]
        for sid in all_d_synths:
            max_score = max(scores_by_block[bi].get(sid, 0) for bi in range(len(dom_blks)))
            if max_score > 0:
                for bi in range(len(dom_blks)):
                    score = scores_by_block[bi].get(sid, 0)
                    if score == max_score or (score >= 3 and score >= 0.8 * max_score):
                        assigned_by_block[bi].append(sid)
            else:
                # FAIL-CLOSED: A planned synthesis with ZERO semantic support is strictly NOT assigned
                unmaterialized_planned_sources.append({
                    "domain_id": d_id,
                    "synthesis_id": sid,
                })

        # Continuing blocks in a domain inherit the domain's verified materialized syntheses.
        # However, if the ENTIRE domain has 0 materialized syntheses (author wrote nothing relevant),
        # blocks remain empty, triggering fail-closed provenance validation!
        materialized_synths = [
            sid for sid in all_d_synths
            if max(scores_by_block[bi].get(sid, 0) for bi in range(len(dom_blks))) > 0
        ]
        for bi in range(len(dom_blks)):
            if not assigned_by_block[bi]:
                if materialized_synths:
                    assigned_by_block[bi].append(materialized_synths[0])
                else:
                    blocks_without_semantic_source.append({
                        "domain_id": d_id,
                        "block_index": bi,
                        "sha256": str(dom_blks[bi]["narrative_block_sha256"]),
                    })

        for bi, blk in enumerate(dom_blks):
            sources.append({
                "narrative_block_sha256": str(blk["narrative_block_sha256"]),
                "synthesis_ids": list(dict.fromkeys(assigned_by_block[bi])),
                "claim_ids": [],
                "timing_ids": [],
            })

    # Integration
    integ_blks = parsed["sections"]["integration"]["authored"]
    planned_integ = sections_plan.get("integration", [])
    ownership["integration"]["narrative_block_sha256s"] = [str(b["narrative_block_sha256"]) for b in integ_blks]
    for i, blk in enumerate(integ_blks):
        p = planned_integ[min(i, len(planned_integ) - 1)] if planned_integ else {"synthesis_ids": [primary_rel], "claim_ids": [], "timing_ids": []}
        sources.append({
            "narrative_block_sha256": str(blk["narrative_block_sha256"]),
            "synthesis_ids": list(p.get("synthesis_ids", [])) or [primary_rel],
            "claim_ids": list(p.get("claim_ids", [])),
            "timing_ids": list(p.get("timing_ids", [])),
        })

    audit_trace = {
        "prospective_plan_sha256": block_plan.get("plan_sha256"),
        "opening_mandatory_bindings": {
            s["narrative_block_sha256"]: s["synthesis_ids"]
            for s in sources[:len(opening_blks)]
        },
        "unmaterialized_mandatories": unmaterialized_mandatories,
        "unmaterialized_planned_sources": unmaterialized_planned_sources,
        "blocks_without_semantic_source": blocks_without_semantic_source,
        "provenance_fail_closed": True,
        "bound_block_count": len(sources),
        "prospective_provenance_verified": True,
    }
    return sources, ownership, audit_trace



def build_author_bundle(
    handoff: Dict[str, object],
    draft_report: str,
    narrative_block_sources: List[Dict[str, object]],
    reader_selection_plan: Optional[Dict[str, object]] = None,
    reasoned_syntheses: Optional[List[Dict[str, object]]] = None,
    reader_sections: Optional[Dict[str, object]] = None,
    synthesis_bundle_sha256: Optional[str] = None,
) -> Dict[str, object]:
    """Construct a canonical Contract 1.4 AuthorBundle from handoff and authored content."""
    contract = _premium_handoff_contract()
    manifest = handoff["reader_domain_manifest"]

    if reader_sections is None:
        parsed = _parse_premium_narrative(draft_report, manifest)
        if parsed.get("errors"):
            raise ValueError(f"Invalid draft report for AuthorBundle: {', '.join(parsed['errors'])}")
        reader_sections = {
            "opening": {"narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"]["opening"]["authored"]]},
            "domains": [
                {"domain_id": str(d["id"]), "narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"][str(d["id"])]["authored"]]}
                for d in manifest["domains"] if d.get("availability") == "available"
            ],
            "integration": {"narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"]["integration"]["authored"]]},
        }

    if reader_selection_plan is None:
        reader_selection_plan = build_canonical_selection_plan(manifest)

    selection_plan_hash = _canonical_hash(reader_selection_plan)

    if reasoned_syntheses is None:
        if handoff.get("approved_reasoned_syntheses"):
            reasoned_syntheses = handoff["approved_reasoned_syntheses"]
        else:
            facts = handoff.get("reasoning_packet", {}).get("facts", {})
            claims_list = (
                facts.get("allowed_claims")
                or handoff.get("allowed_claims")
                or handoff.get("reasoning_packet", {}).get("claims")
                or []
            )
            claims_dict = {str(item["id"]): item for item in claims_list if isinstance(item, dict)}
            coverage = facts.get("coverage", {})
            composed, _, _ = compose_canonical_domain_syntheses(claims_dict, manifest, coverage)
            for c in composed:
                if isinstance(c, dict):
                    c["status"] = "allowed"
            sig_synths = handoff.get("prepared_signature_syntheses", [])
            seen_ids = set()
            combined = []
            for item in [*composed, *sig_synths]:
                if isinstance(item, dict) and item.get("id") not in seen_ids:
                    seen_ids.add(item.get("id"))
                    combined.append(item)
            reasoned_syntheses = combined

    allowed_syntheses = [s for s in reasoned_syntheses if isinstance(s, dict) and s.get("status", "allowed") == "allowed"]
    synth_hash = synthesis_bundle_sha256 or handoff.get("synthesis_bundle_sha256") or _canonical_hash(allowed_syntheses)
    report_hash = _canonical_hash(draft_report)

    prep_sig_hash = handoff.get("prepared_chart_signature_sha256") or _canonical_hash(handoff.get("chart_signature"))
    prep_synth_hash = handoff.get("prepared_signature_synthesis_sha256") or _canonical_hash(handoff.get("reasoned_synthesis", []))
    manifest_hash = handoff.get("reader_domain_manifest_sha256") or _canonical_hash(handoff.get("reader_domain_manifest"))

    return {
        "packet_id": handoff["packet_id"],
        "premium_handoff_contract_version": contract["version"],
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": _canonical_hash(contract),
        "prepared_chart_signature_sha256": prep_sig_hash,
        "prepared_signature_synthesis_sha256": prep_synth_hash,
        "reader_domain_manifest_sha256": manifest_hash,
        "reader_selection_plan": reader_selection_plan,
        "reader_selection_plan_sha256": selection_plan_hash,
        "reasoned_syntheses": reasoned_syntheses,
        "synthesis_bundle_sha256": synth_hash,
        "draft_report": draft_report,
        "draft_report_sha256": report_hash,
        "narrative_block_sources": narrative_block_sources,
        "reader_sections": reader_sections,
    }





def build_reviewer_bundle(
    author_bundle: Dict[str, object],
    provenance_result: Dict[str, object],
    final_report: Optional[str] = None,
    verdict: str = "approved",
    corrections_made: Optional[List[str]] = None,
    remaining_warnings: Optional[List[str]] = None,
    regeneration_request: Optional[Dict[str, object]] = None,
    narrative_block_sources: Optional[List[Dict[str, object]]] = None,
    reader_sections: Optional[Dict[str, object]] = None,
    block_plan: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    """Construct a canonical Contract 1.4 ReviewerBundle from author bundle and review results."""
    contract = _premium_handoff_contract()
    report = author_bundle["draft_report"] if final_report is None else final_report
    manifest = provenance_result.get("reader_domain_manifest") or author_bundle.get("reader_domain_manifest")

    if final_report is not None and narrative_block_sources is None and block_plan is not None and manifest:
        sources, sections, _ = bind_prospective_plan_to_prose(report, block_plan, manifest)
    else:
        sources = author_bundle["narrative_block_sources"] if narrative_block_sources is None else narrative_block_sources
        sections = author_bundle["reader_sections"] if reader_sections is None else reader_sections

        # If the report was edited and sections were not provided, re-parse
        if final_report is not None and reader_sections is None and manifest:
            parsed = _parse_premium_narrative(report, manifest)
            if not parsed.get("errors"):
                sections = {
                    "opening": {"narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"]["opening"]["authored"]]},
                    "domains": [
                        {"domain_id": str(d["id"]), "narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"][str(d["id"])]["authored"]]}
                        for d in manifest.get("domains", []) if d.get("availability") == "available"
                    ],
                    "integration": {"narrative_block_sha256s": [str(x["narrative_block_sha256"]) for x in parsed["sections"]["integration"]["authored"]]},
                }

    return {
        "packet_id": provenance_result["packet_id"],
        "premium_handoff_contract_version": contract["version"],
        "premium_handoff_contract": contract,
        "premium_handoff_contract_sha256": _canonical_hash(contract),
        "prepared_chart_signature_sha256": provenance_result["prepared_chart_signature_sha256"],
        "prepared_signature_synthesis_sha256": provenance_result["prepared_signature_synthesis_sha256"],
        "reader_domain_manifest_sha256": provenance_result["reader_domain_manifest_sha256"],
        "synthesis_bundle_sha256": provenance_result["synthesis_bundle_sha256"],
        "reviewed_draft_sha256": provenance_result["draft_report_sha256"],
        "verdict": verdict,
        "corrections_made": corrections_made or [],
        "remaining_warnings": remaining_warnings or [],
        "final_report": report,
        "final_report_sha256": _canonical_hash(report),
        "narrative_block_sources": sources,
        "reader_sections": sections,
        "reader_selection_plan": provenance_result["reader_selection_plan"],
        "reader_selection_plan_sha256": provenance_result["reader_selection_plan_sha256"],
        "regeneration_request": regeneration_request,
    }
