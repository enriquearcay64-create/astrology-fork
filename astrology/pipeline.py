"""Single orchestration entrypoint with strict fact-to-language boundaries."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Dict, Iterable, List, Optional

from .consultation import answer_question, classify_question, render_consultation
from .config import PREMIUM_HANDOFF_CONTRACT_VERSION
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


def analyse_birth_chart(birth: BirthData, profile: Optional[LocalizationProfile] = None, report_depth: str = "executive", include_timing: bool = True, as_of: Optional[datetime] = None, horizon_days: int = 366, question_topics: Iterable[int] = ()) -> Dict[str, object]:
    language = profile.preferred_language if profile else "pt-BR"
    raw_chart = calculate_chart(birth)
    packet_id = _packet_id(birth, profile, raw_chart.policy, as_of, horizon_days, include_timing)
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
        "packet_id": packet_id, "chart": raw_chart.as_dict(), "safe_interpretive_view": to_primitive(chart), "hierarchy": natal_hierarchy, "current_hierarchy": current_hierarchy,
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


def _premium_handoff_contract() -> Dict[str, object]:
    """One serialized source-map contract for both Premium guard stages."""
    return {
        "version": PREMIUM_HANDOFF_CONTRACT_VERSION,
        "author_bundle_required_fields": [
            "packet_id", "premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256",
            "prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256",
            "reasoned_syntheses", "draft_report", "paragraph_sources", "reader_sections", "synthesis_bundle_sha256", "draft_report_sha256",
        ],
        "reviewer_bundle_required_fields": [
            "packet_id", "premium_handoff_contract_version", "premium_handoff_contract", "premium_handoff_contract_sha256",
            "prepared_chart_signature_sha256", "prepared_signature_synthesis_sha256", "reader_domain_manifest_sha256",
            "synthesis_bundle_sha256", "reviewed_draft_sha256", "verdict", "corrections_made", "remaining_warnings",
            "final_report", "final_report_sha256", "paragraph_sources", "reader_sections",
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
        "prepared_signature_rule": "pre_domain_chart_signature_and_its_deterministic_synthesis_basis_are_frozen",
        "publication_authority_rule": "original_prepared_handoff_binds_packet_signature_synthesis_basis_manifest_and_materialized_timing_parameters",
    }


def _packet_id(birth: BirthData, profile: Optional[LocalizationProfile], policy: Dict[str, object], as_of: Optional[datetime], horizon_days: int, include_timing: bool) -> str:
    """Identity for one methodologically meaningful premium calculation."""
    return _canonical_hash({
        "birth": to_primitive(birth), "localization_profile": to_primitive(profile) if profile else None,
        "versions": {
            **{key: policy.get(key) for key in ("methodology_version", "schema_version", "semantic_registry_version", "timing_version")},
            "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION,
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
    manifest_hash = _canonical_hash(core["reader_domain_manifest"])
    reader_introduction = _premium_reader_introduction(core["reader_domain_manifest"].get("locale"))
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
        "reader_domain_manifest": core["reader_domain_manifest"],
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
        "timeline": core["timeline"],
        "developmental_intervals": core["developmental_intervals"],
        # The client appendix is concise deterministic reference data; the
        # established full technical renderer remains an internal audit sidecar.
        "technical_appendix": technical_appendix(handoff_chart, core["hierarchy"], [], core["timing"], core["chart_structure"], profile),
        "audit_sidecar": render_report("technical", handoff_chart, [], [], core["hierarchy"], core["timing"], core["timeline"], [], [], core["chart_structure"], profile, [], core["narrative_plan"], core["developmental_intervals"], core["chart_signature"]),
        "reasoned_synthesis_schema": list(ReasonedSynthesis.__dataclass_fields__),
        "author_bundle_contract": {"packet_id": core["packet_id"], "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": handoff_contract, "premium_handoff_contract_sha256": handoff_contract_hash, "prepared_chart_signature_sha256": prepared_signature_hash, "prepared_signature_synthesis_sha256": prepared_synthesis_hash, "reader_domain_manifest_sha256": manifest_hash, "reasoned_syntheses": "list[ReasonedSynthesis]", "draft_report": "string", "paragraph_sources": [{"paragraph_sha256": "sha256", "synthesis_ids": ["reasoned.id"], "claim_ids": ["claim.id"], "timing_ids": ["timing.activation.id"]}], "reader_sections": "opening + canonical domains + integration", "synthesis_bundle_sha256": "sha256", "draft_report_sha256": "sha256"},
        "reviewer_bundle_contract": {"packet_id": core["packet_id"], "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": handoff_contract, "premium_handoff_contract_sha256": handoff_contract_hash, "prepared_chart_signature_sha256": prepared_signature_hash, "prepared_signature_synthesis_sha256": prepared_synthesis_hash, "reader_domain_manifest_sha256": manifest_hash, "synthesis_bundle_sha256": "sha256", "reviewed_draft_sha256": "sha256", "verdict": "approved|blocked", "corrections_made": ["string"], "remaining_warnings": ["string"], "final_report": "string", "final_report_sha256": "sha256", "paragraph_sources": "same mapping contract", "reader_sections": "same ownership contract"},
        "sol_high_instruction": llm_reasoning_instructions(),
        "author_voice_instruction": core["humanization_instructions"],
        "narrative_judge_instruction": humanization_verifier_instructions(profile.preferred_language if profile else "pt-BR"),
    }


def validate_premium_syntheses(birth: BirthData, synthesis_payload: Iterable[Dict[str, object]], profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True) -> Dict[str, object]:
    """Deterministically gate manually authored High syntheses; no API call."""
    core = analyse_birth_chart(birth, profile, "deep", include_timing, as_of, horizon_days)
    allowed_fields = set(ReasonedSynthesis.__dataclass_fields__)
    items = [ReasonedSynthesis(**{key: value for key, value in item.items() if key in allowed_fields}) for item in synthesis_payload]
    chart = build_safe_interpretive_view(calculate_chart(birth))
    timing_ids = [item["id"] for item in core["reasoning_packet"]["facts"]["timing_evidence"]]
    checked = validate_reasoned_syntheses(items, chart, [Claim(**claim) for claim in core["claims"]], timing_ids)
    approved = [to_primitive(item) for item in checked if item.status == "allowed"]
    reader_introduction = _premium_reader_introduction(core["reader_domain_manifest"].get("locale"))
    return {
        "stage": "provenance_syntheses_checked", "packet_id": core["packet_id"], "approved": len(approved) == len(checked),
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


def _parse_premium_narrative(report: object, manifest: object) -> Dict[str, object]:
    """Parse one canonical physical block universe for handoff 1.2."""
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


def _validated_paragraph_sources(report: object, paragraph_sources: object, approved_ids: set[str], allowed_claims: Dict[str, Claim], timing_ids: set[str], parsed: Optional[Dict[str, object]] = None) -> tuple[List[str], List[Dict[str, object]]]:
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
    return _validated_paragraph_sources(report, paragraph_sources, approved_ids, allowed_claims, timing_ids)[0]


def _validate_mandatory_coverage(report: object, paragraph_sources: object, approved_syntheses: Iterable[Dict[str, object]], coverage: object) -> List[str]:
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


def paragraph_source_template(report: str, reader_domain_manifest: Optional[Dict[str, object]] = None) -> List[Dict[str, object]]:
    """Return the exact substantial-paragraph hashes an Author must source."""
    if reader_domain_manifest is not None:
        parsed = _parse_premium_narrative(report, reader_domain_manifest)
        if parsed["errors"]:
            raise ValueError("Invalid Premium narrative: " + ", ".join(parsed["errors"]))
        hashes = [item["sha256"] for item in parsed["prose"]]
    else:
        hashes = list(dict.fromkeys(_canonical_hash(paragraph) for paragraph in _substantive_paragraphs(report)))
    return [
        {"paragraph_sha256": paragraph_hash, "synthesis_ids": [], "claim_ids": [], "timing_ids": []}
        for paragraph_hash in hashes
    ]


def _validate_reader_sections(parsed: Dict[str, object], reader_sections: object, manifest: object) -> List[str]:
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


def _validate_reader_domain_coverage(
    parsed: Dict[str, object], reader_sections: object, paragraph_sources: List[Dict[str, object]],
    approved_syntheses: Iterable[Dict[str, object]], manifest: object,
) -> List[str]:
    if not isinstance(reader_sections, dict) or not isinstance(manifest, dict):
        return ["missing_reader_domain_coverage_contract"]
    approved = {str(item.get("id")): item for item in approved_syntheses if isinstance(item, dict) and item.get("status") == "allowed"}
    by_hash = {str(item.get("paragraph_sha256")): item for item in paragraph_sources if isinstance(item, dict)}
    domains = {str(item.get("domain_id")): item for item in reader_sections.get("domains", []) if isinstance(item, dict)}
    errors: List[str] = []

    def synthesis_matches_path(synthesis: Dict[str, object], path: Dict[str, object]) -> bool:
        return (
            set(map(str, path.get("source_claim_ids", []))).issubset(set(map(str, synthesis.get("source_claim_ids", []))))
            and set(map(str, path.get("primary_factor_ids", []))).issubset(set(map(str, synthesis.get("primary_factors", []))))
            and str(synthesis.get("reasoning_class")) == str(path.get("reasoning_class"))
            and set(map(str, path.get("composition_operations", []))).issubset(set(map(str, synthesis.get("composition_operations", []))))
        )

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
                    if synthesis_matches_path(synthesis, path)
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


def _handoff_contract_errors(bundle: Dict[str, object], bundle_kind: str) -> List[str]:
    contract = _premium_handoff_contract()
    contract_hash = _canonical_hash(contract)
    errors = []
    required_key = f"{bundle_kind}_bundle_required_fields"
    for field in contract[required_key]:
        if field not in bundle:
            errors.append(f"premium_handoff_{bundle_kind}_bundle_missing_required_field:{field}")
    if bundle.get("premium_handoff_contract_version") != PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("premium_handoff_contract_version_mismatch")
    if bundle.get("premium_handoff_contract") != contract:
        errors.append("premium_handoff_contract_body_mismatch")
    if bundle.get("premium_handoff_contract_sha256") != contract_hash:
        errors.append("premium_handoff_contract_hash_mismatch")
    if "premium_handoff_contract" in bundle and _canonical_hash(bundle["premium_handoff_contract"]) != bundle.get("premium_handoff_contract_sha256"):
        errors.append("premium_handoff_contract_body_hash_mismatch")
    return errors


def _verify_authoritative_prepared_handoff(
    prepared_handoff: Optional[Dict[str, object]], authoritative: Optional[Dict[str, object]] = None,
    *, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True,
) -> tuple[Optional[datetime], int, bool, List[str]]:
    """Parse and verify the single deterministic authority for Premium 1.2.

    The first call supplies the materialized deterministic selectors for a
    recomputation.  The second call receives that recomputation and verifies
    the supplied handoff's complete prepared identity against it.  Both
    Premium guards use this exact path; transport consistency is not authority.
    """
    handoff = prepared_handoff if isinstance(prepared_handoff, dict) else {}
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
    if handoff.get("premium_handoff_contract_version") != PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("authoritative_handoff_contract_version_mismatch")
    if handoff.get("premium_handoff_contract") != _premium_handoff_contract():
        errors.append("authoritative_handoff_contract_body_mismatch")
    if handoff.get("premium_handoff_contract_sha256") != _canonical_hash(_premium_handoff_contract()):
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


def validate_premium_author_bundle(birth: BirthData, author_bundle: Dict[str, object], profile: Optional[LocalizationProfile] = None, as_of: Optional[datetime] = None, horizon_days: int = 366, include_timing: bool = True, prepared_handoff: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    """Deterministic Provenance Guard between the Author and Reviewer."""
    items = author_bundle.get("reasoned_syntheses", [])
    prepared_as_of, prepared_horizon, prepared_include_timing, _ = _verify_authoritative_prepared_handoff(
        prepared_handoff, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    checked = validate_premium_syntheses(
        birth, items if isinstance(items, list) else [], profile,
        prepared_as_of, prepared_horizon, prepared_include_timing,
    )
    _prepared_as_of, _prepared_horizon, _prepared_include_timing, errors = _verify_authoritative_prepared_handoff(
        prepared_handoff, checked, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    errors.extend(_handoff_contract_errors(author_bundle, "author"))
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
    parsed = _parse_premium_narrative(draft, checked["reader_domain_manifest"])
    errors.extend(_validate_reader_sections(parsed, author_bundle.get("reader_sections"), checked["reader_domain_manifest"]))
    source_errors, valid_sources = _validated_paragraph_sources(draft, author_bundle.get("paragraph_sources"), approved_ids, allowed_claims, set(checked["timing_evidence_ids"]), parsed)
    errors.extend(source_errors)
    approved_syntheses = checked["approved_reasoned_syntheses"]
    errors.extend(_validate_mandatory_coverage(draft, valid_sources, approved_syntheses, checked.get("coverage")))
    errors.extend(_validate_reader_domain_coverage(parsed, author_bundle.get("reader_sections"), valid_sources, approved_syntheses, checked["reader_domain_manifest"]))
    if isinstance(draft, str) and _contains_prohibited_extension(draft):
        errors.append("prohibited_extension_in_author_draft")
    if not birth.birth_time_known:
        errors.append("premium_birth_time_required")
    return {"stage": "deterministic_provenance_guard", "approved": checked["approved"] and not errors, "verification_errors": list(dict.fromkeys(errors)), "packet_id": checked["packet_id"], "premium_handoff_contract_version": PREMIUM_HANDOFF_CONTRACT_VERSION, "premium_handoff_contract": _premium_handoff_contract(), "premium_handoff_contract_sha256": _canonical_hash(_premium_handoff_contract()), "prepared_chart_signature_sha256": checked["prepared_chart_signature_sha256"], "prepared_signature_synthesis_sha256": checked["prepared_signature_synthesis_sha256"], "prepared_signature_syntheses": checked["prepared_signature_syntheses"], "reader_domain_manifest": checked["reader_domain_manifest"], "reader_domain_manifest_sha256": checked["reader_domain_manifest_sha256"], "approved_reasoned_syntheses": approved_syntheses, "allowed_claims": checked["allowed_claims"], "synthesis_bundle_sha256": expected_synthesis_hash, "draft_report_sha256": _canonical_hash(draft), "timing_evidence_ids": checked["timing_evidence_ids"], "coverage": checked.get("coverage"), "chart_signature": checked["chart_signature"], "narrative_plan": checked["narrative_plan"]}


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
    """Check publication provenance after the separate human/High narrative judge.

    This is intentionally a structural and safety gate.  An attestation by a
    High Narrative Judge is required for semantic equivalence; token checks do
    not claim to prove it.
    """
    prepared_as_of, prepared_horizon, prepared_include_timing, _ = _verify_authoritative_prepared_handoff(
        prepared_handoff, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    authoritative = validate_premium_syntheses(
        birth, [], profile, prepared_as_of, prepared_horizon, prepared_include_timing,
    )
    _prepared_as_of, _prepared_horizon, _prepared_include_timing, preparation_errors = _verify_authoritative_prepared_handoff(
        prepared_handoff, authoritative, as_of=as_of, horizon_days=horizon_days, include_timing=include_timing,
    )
    approved_ids = {str(item.get("id")) for item in provenance.get("approved_reasoned_syntheses", [])}
    report = narrative_payload.get("final_report")
    errors = ([] if provenance.get("approved") else ["author_provenance_not_approved"]) + preparation_errors
    errors.extend(_handoff_contract_errors(narrative_payload, "reviewer"))
    if provenance.get("premium_handoff_contract_version") != PREMIUM_HANDOFF_CONTRACT_VERSION:
        errors.append("provenance_handoff_contract_version_mismatch")
    if provenance.get("premium_handoff_contract_sha256") != _canonical_hash(_premium_handoff_contract()):
        errors.append("provenance_handoff_contract_hash_mismatch")
    if provenance.get("premium_handoff_contract") != _premium_handoff_contract():
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
    if narrative_payload.get("synthesis_bundle_sha256") != provenance.get("synthesis_bundle_sha256"):
        errors.append("synthesis_bundle_hash_mismatch")
    if narrative_payload.get("reviewed_draft_sha256") != provenance.get("draft_report_sha256"):
        errors.append("reviewed_draft_hash_mismatch")
    if narrative_payload.get("verdict") != "approved":
        errors.append("reviewer_not_approved")
    if narrative_payload.get("final_report_sha256") != _canonical_hash(report):
        errors.append("final_report_hash_mismatch")
    allowed_claims = {str(item.get("id")): Claim(**item) for item in provenance.get("allowed_claims", []) if isinstance(item, dict) and item.get("status") == "allowed"}
    manifest = provenance.get("reader_domain_manifest")
    if _canonical_hash(manifest) != provenance.get("reader_domain_manifest_sha256"):
        errors.append("provenance_reader_domain_manifest_hash_mismatch")
    if manifest != authoritative.get("reader_domain_manifest"):
        errors.append("provenance_reader_domain_manifest_mismatch")
    parsed = _parse_premium_narrative(report, manifest)
    errors.extend(_validate_reader_sections(parsed, narrative_payload.get("reader_sections"), manifest))
    source_errors, valid_sources = _validated_paragraph_sources(report, narrative_payload.get("paragraph_sources"), approved_ids, allowed_claims, set(provenance.get("timing_evidence_ids", [])), parsed)
    errors.extend(source_errors)
    errors.extend(_validate_mandatory_coverage(report, valid_sources, provenance.get("approved_reasoned_syntheses", []), provenance.get("coverage")))
    errors.extend(_validate_reader_domain_coverage(parsed, narrative_payload.get("reader_sections"), valid_sources, provenance.get("approved_reasoned_syntheses", []), manifest))
    if isinstance(report, str) and _contains_prohibited_extension(report):
        errors.append("prohibited_extension_in_final_narrative")
    return {
        "stage": "narrative_judged",
        "approved": not errors,
        "verification_errors": errors,
        "semantic_status": "reviewer_attested_not_deterministically_proven" if not errors else "not_publishable",
        "report": report if not errors else None,
    }


def _contains_prohibited_extension(text: str) -> bool:
    return bool(re.search(r"\b(trauma|diagn[oó]stico|diagnosis|morte|death|doen[cç]a|disease|gravidez|pregnancy|div[oó]rcio|divorce|fal[eê]ncia|bankruptcy|vai acontecer|will happen)\b", text, re.I))


def _require_premium_birth_time(birth: BirthData) -> None:
    if not birth.birth_time_known:
        raise ValueError("Premium beta requires a known local birth time. Use the limited safe deterministic reading when the time is unknown.")
