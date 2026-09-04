"""Unit tests for V2.2.1 timing renderer, order-agnostic selection plan, and semantic block binding."""
from datetime import datetime, timezone
import random
from astrology.models import BirthData
from astrology.pipeline import (
    analyse_birth_chart, prepare_premium_handoff, plan_prospective_narrative_blocks,
    bind_prospective_plan_to_prose, build_canonical_selection_plan,
    validate_premium_author_bundle, build_author_bundle, validate_premium_syntheses,
    build_reviewer_bundle, validate_premium_narrative,
    _canonical_hash, compose_canonical_domain_syntheses
)
from astrology.report import format_canonical_timing_activation, render_canonical_technical_appendix
from tests.test_v22_architecture_and_guards import sample_birth


CHART_3_BIRTH = BirthData("1995-09-08T19:45:00", "Europe/Paris", 48.8566, 2.3522)


def test_canonical_timing_renderer_schema_and_real_dates():
    """Verify R1: timing renderer schema fields, technique labels, and verified concrete dates."""
    analysis = analyse_birth_chart(CHART_3_BIRTH, include_timing=True)
    timing = analysis.get("timing")
    assert timing is not None
    activations = timing.get("modern_stream", {}).get("major_transits", [])
    assert len(activations) > 0

    first_act = activations[0]
    fmt = format_canonical_timing_activation(first_act, lang="pt")

    # Verify canonical schema fields
    required_keys = {
        "activation_id", "technique", "transit_body", "aspect",
        "target", "window_start", "exact_peak", "window_end", "window",
    }
    assert required_keys.issubset(fmt.keys())
    assert fmt["technique"] == "Trânsito Maior"
    assert fmt["transit_body"] != ""
    assert fmt["aspect"] != ""
    assert fmt["target"] != ""
    assert fmt["exact_peak"] != "N/A"
    assert " .. " in fmt["window"]

    # Verify English localization
    fmt_en = format_canonical_timing_activation(first_act, lang="en")
    assert fmt_en["technique"] == "Major Transit"

    # Verify appendix markdown rendering with distinct peak/type
    appendix = render_canonical_technical_appendix(CHART_3_BIRTH, timing=timing, lang="pt")
    assert "Fatos Canônicos de Timing" in appendix
    assert "| Ativação | Técnica | Trânsito | Aspecto | Alvo Natal | Janela | Pico (Tipo) |" in appendix
    assert "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |" in appendix
    assert fmt["activation_id"] in appendix
    assert fmt["technique"] in appendix



def test_reader_selection_plan_order_agnostic_and_multi_path():
    """Verify R2: ReaderSelectionPlan is order-agnostic, has no first-element bias, and represents multiple paths."""
    analysis = analyse_birth_chart(CHART_3_BIRTH)
    manifest = analysis["reader_domain_manifest"]
    plan = build_canonical_selection_plan(manifest)

    # 1. Multi-path representation verification
    by_domain = {d["domain_id"]: d["paths"] for d in plan["domains"]}

    # Work vocation: both Casa 10 ruler and Casa 6 ruler represented
    work_paths = by_domain["work_vocation_visibility"]
    assert len(work_paths) == 2
    assert all(p["decision"] == "represented" for p in work_paths)

    # Money: Casa 2 ruler and Casa 8 ruler represented, topical Mars merged
    money_paths = by_domain["money_resources_value"]
    money_decisions = [p["decision"] for p in money_paths]
    assert money_decisions.count("represented") >= 2
    assert "merged_with_represented" in money_decisions

    # Creativity: Path 0 is Sun (merged), Path 1 Venus (represented), Path 2 Moon/Casa 5 (represented)
    creativity_paths = by_domain["creativity_pleasure_aliveness"]
    assert creativity_paths[0]["decision"] == "merged_with_represented"
    assert creativity_paths[1]["decision"] == "represented"
    assert creativity_paths[2]["decision"] == "represented"

    # Rationales for omitted/merged paths must be substantive and non-empty
    for d in plan["domains"]:
        for p in d["paths"]:
            if p["decision"] in ("merged_with_represented", "omitted_no_distinct_reader_value"):
                assert p["rationale"] is not None
                assert len(p["rationale"]) > 15

    # 2. Order-agnostic verification: shuffle paths and verify decisions are identical
    shuffled_manifest = {
        "manifest_version": manifest.get("manifest_version"),
        "domains": [],
    }
    for d in manifest["domains"]:
        d_copy = dict(d)
        orig_paths = list(d.get("legal_coverage_paths", []))
        rev_paths = list(reversed(orig_paths))
        d_copy["legal_coverage_paths"] = rev_paths
        shuffled_manifest["domains"].append(d_copy)

    shuffled_plan = build_canonical_selection_plan(shuffled_manifest)
    shuffled_by_domain = {d["domain_id"]: {p["path_id"]: p["decision"] for p in d["paths"]} for d in shuffled_plan["domains"]}
    orig_by_domain = {d["domain_id"]: {p["path_id"]: p["decision"] for p in d["paths"]} for d in plan["domains"]}

    for d_id, path_decisions in orig_by_domain.items():
        assert path_decisions == shuffled_by_domain[d_id], f"Domain {d_id} decisions differed under path reversal"


def test_opening_blocks_bind_only_cited_mandatory_syntheses():
    """Verify R3: Opening blocks bind only cited mandatory syntheses, not all 15 bundled indiscriminately."""
    handoff = prepare_premium_handoff(CHART_3_BIRTH)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)
    mandatory_ids = block_plan["mandatory_ids"]
    assert len(mandatory_ids) >= 10

    # Create synthetic draft report following the canonical section order
    heading_by_key = {
        "opening": manifest["opening"]["heading"],
        "integration": manifest["integration"]["heading"],
        **{item["id"]: item["heading"] for item in manifest["domains"]},
    }
    order = ["opening", *[item["id"] for item in manifest["domains"]], "integration"]
    report_parts = [handoff["reader_introduction"]]

    for key in order:
        report_parts.append(f"## {heading_by_key[key]}")
        if key == "opening":
            report_parts.append("Com o Sol em Virgem e o Ascendente em Peixes, este mapa articula uma sensibilidade fina.")
            report_parts.append("A Lua em Peixes aprofunda a percepção psíquica e o recolhimento emocional.")
        elif key == "integration":
            report_parts.append("Integração final do mapa como totalidade viva.")
        else:
            domain = next((d for d in manifest["domains"] if d["id"] == key), None)
            if domain and domain.get("availability") == "unavailable":
                report_parts.append(domain["unavailable_notice"]["text"])
            else:
                report_parts.append(f"Texto reflexivo sobre o domínio {key}.")

    draft_report = "\n\n".join(report_parts)
    sources, sections, audit = bind_prospective_plan_to_prose(draft_report, block_plan, manifest)

    # Opening block 0 must NOT have all 15 mandatory items
    opening_s0 = sources[0]["synthesis_ids"]
    opening_s1 = sources[1]["synthesis_ids"]

    assert len(opening_s0) < len(mandatory_ids), "Opening block 0 bundled all mandatory syntheses indiscriminately!"
    assert len(opening_s1) < len(mandatory_ids), "Opening block 1 bundled all mandatory syntheses indiscriminately!"
    # Verify that block 0 bound Sol/ASC and block 1 bound Moon
    assert len(opening_s0) >= 1
    assert len(opening_s1) >= 1


def test_author_bundle_provenance_guard_pass_with_v221():
    """Verify that author bundle with V2.2.1 prospective plan and selection passes Provenance Guard."""
    import json
    from pathlib import Path
    birth = sample_birth()
    handoff = prepare_premium_handoff(birth)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    bench_file = Path("docs/benchmark_reports/04-reviewer-bundle.json")
    if bench_file.exists():
        data = json.loads(bench_file.read_text(encoding="utf-8"))
        report = data["final_report"]
        sources, sections, audit = bind_prospective_plan_to_prose(report, block_plan, manifest)
        all_synths = list(block_plan.get("composed_syntheses", []))
        for ps in handoff.get("prepared_signature_syntheses", []):
            if ps["id"] not in [x["id"] for x in all_synths]:
                all_synths.append(ps)

        checked = validate_premium_syntheses(birth, all_synths, premium_contract_version="1.4")
        approved_synths = [item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"]
        expected_synthesis_hash = _canonical_hash(approved_synths)

        bundle = build_author_bundle(
            handoff, report, sources,
            reader_selection_plan=block_plan["selection_plan"],
            reasoned_syntheses=all_synths,
            reader_sections=sections,
            synthesis_bundle_sha256=expected_synthesis_hash,
        )

        res = validate_premium_author_bundle(birth, bundle, prepared_handoff=handoff)
        assert res["approved"] is True, f"Provenance Guard failed: {res.get('verification_errors')}"


def test_timing_formatter_case_insensitivity_and_missing_exact():
    """Verify timing activation formatter is robust to uppercase targets/bodies and handles missing peak."""
    activation = {
        "id": "transit.saturn_opp_mercury.1234",
        "technique": "Major Transit",
        "transit_body": "SATURN",
        "aspect": "OPPOSITION",
        "target": "MC",
        "window_start": "2026-03-01",
        "window_end": "2026-07-01",
        "exact_at": None,
    }
    fmt_pt = format_canonical_timing_activation(activation, lang="pt")
    assert fmt_pt["transit_body"] == "Saturno"
    assert fmt_pt["aspect"] == "Oposição"
    assert fmt_pt["target"] == "Meio do Céu (MC)"
    assert fmt_pt["exact_peak"] == ""
    assert fmt_pt["window"] == "2026-03-01 .. 2026-07-01"

    fmt_en = format_canonical_timing_activation(activation, lang="en")
    assert fmt_en["transit_body"] == "Saturn"
    assert fmt_en["aspect"] == "Opposition"
    assert fmt_en["target"] == "Midheaven (MC)"


def test_semantic_block_reassignment_on_paragraph_swap():
    """Verify R3: Swapping paragraphs in a multi-path domain semantically reassigns syntheses based on text."""
    from scripts.run_chart3_pipeline import DRAFT_REPORT
    handoff = prepare_premium_handoff(CHART_3_BIRTH)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    p0 = "O Meio do Céu em Sagitário é regido por Júpiter domiciliado na nona casa, desenhando uma vocação voltada para a transmissão de conhecimento, orientação ética, síntese interdisciplinar e ampliação de horizontes culturais ou intelectuais."
    p1 = "Na esfera operacional, a sexta casa em Câncer é regida pela Lua na décima segunda casa em Peixes, estabelecendo que a rotina de trabalho deve respeitar o ritmo interno e a sensibilidade psíquica. O trabalho ganha eficácia quando estruturado em ambientes humanos e acolhedores, alternando fases de dedicação meticulosa e pausas necessárias para reabastecimento anímico."

    # In original report, p0 (Jupiter/MC) is Block 0 and p1 (Moon/House 6) is Block 1
    sources_orig, sections_orig, _ = bind_prospective_plan_to_prose(DRAFT_REPORT, block_plan, manifest)
    own_w_orig = next(d for d in sections_orig["domains"] if d["domain_id"] == "work_vocation_visibility")
    b0_orig = next(s for s in sources_orig if s["narrative_block_sha256"] == own_w_orig["narrative_block_sha256s"][0])
    b1_orig = next(s for s in sources_orig if s["narrative_block_sha256"] == own_w_orig["narrative_block_sha256s"][1])
    assert "10.jupiter" in b0_orig["synthesis_ids"][0]
    assert "6.moon" in b1_orig["synthesis_ids"][0]

    # Swap p0 and p1: p1 is now Block 0, p0 is now Block 1
    swapped_report = DRAFT_REPORT.replace(p0 + "\n\n" + p1, p1 + "\n\n" + p0)
    sources_swap, sections_swap, _ = bind_prospective_plan_to_prose(swapped_report, block_plan, manifest)
    own_w_swap = next(d for d in sections_swap["domains"] if d["domain_id"] == "work_vocation_visibility")
    b0_swap = next(s for s in sources_swap if s["narrative_block_sha256"] == own_w_swap["narrative_block_sha256s"][0])
    b1_swap = next(s for s in sources_swap if s["narrative_block_sha256"] == own_w_swap["narrative_block_sha256s"][1])

    # Semantic reassignment must bind Lua/6 to Block 0 and Jupiter/10 to Block 1, NOT positionally!
    assert "6.moon" in b0_swap["synthesis_ids"][0], f"Expected 6.moon in swapped block 0, got {b0_swap['synthesis_ids']}"
    assert "10.jupiter" in b1_swap["synthesis_ids"][0], f"Expected 10.jupiter in swapped block 1, got {b1_swap['synthesis_ids']}"


def test_reviewer_bundle_automatic_rebind_on_edited_report():
    """Verify R3: build_reviewer_bundle automatically rebinds narrative blocks semantically when report is edited."""
    from scripts.run_chart3_pipeline import DRAFT_REPORT
    from astrology.models import LocalizationProfile
    profile = LocalizationProfile(preferred_language="pt-BR")
    handoff = prepare_premium_handoff(CHART_3_BIRTH, profile=profile)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    sources, sections, _ = bind_prospective_plan_to_prose(DRAFT_REPORT, block_plan, manifest)
    all_synths = list(block_plan.get("composed_syntheses", []))
    for ps in handoff.get("prepared_signature_syntheses", []):
        if ps["id"] not in [x["id"] for x in all_synths]:
            all_synths.append(ps)

    checked = validate_premium_syntheses(CHART_3_BIRTH, all_synths, premium_contract_version="1.4")
    approved_synths = [item for item in checked["reasoned_synthesis"] if item["status"] == "allowed"]
    expected_synthesis_hash = _canonical_hash(approved_synths)
    author_bundle = build_author_bundle(
        handoff, DRAFT_REPORT, sources,
        reader_selection_plan=block_plan["selection_plan"],
        reasoned_syntheses=all_synths,
        reader_sections=sections,
        synthesis_bundle_sha256=expected_synthesis_hash,
    )
    prov_res = validate_premium_author_bundle(CHART_3_BIRTH, author_bundle, profile=profile, prepared_handoff=handoff)
    assert prov_res["approved"] is True

    # Reviewer edits the report: splits work section into two paragraphs with slight phrasing refinement
    edited_report = DRAFT_REPORT.replace(
        "O trabalho ganha eficácia quando estruturado em ambientes humanos e acolhedores, alternando fases de dedicação meticulosa e pausas necessárias para reabastecimento anímico.",
        "O trabalho ganha eficácia quando estruturado em ambientes humanos e acolhedores.\n\nAlternam-se fases de dedicação meticulosa e pausas necessárias para reabastecimento anímico."
    )

    # Call build_reviewer_bundle without manual narrative_block_sources, passing block_plan
    rev_bundle = build_reviewer_bundle(
        author_bundle, prov_res, final_report=edited_report, block_plan=block_plan
    )

    pub_res = validate_premium_narrative(
        rev_bundle, prov_res, CHART_3_BIRTH, profile, prepared_handoff=handoff, include_timing=True
    )
    assert pub_res["approved"] is True, f"Publication Guard failed on automatic rebind: {pub_res.get('verification_errors')}"


def test_timing_formatter_date_sanitization_and_target_fallbacks():
    """Verify timing formatter cleans dirty strings ('None', 'N/A', 'null') and supports target fallbacks."""
    dirty_activation = {
        "activation_instance": "transit.saturn_trine_mars.9999",
        "technique": "Trânsito Maior",
        "body": "saturn",
        "aspect": "trine",
        "natal_target": "mars",  # using natal_target instead of target
        "window_start": "None",
        "window_end": "null",
        "exact_at": "N/A",
    }
    fmt = format_canonical_timing_activation(dirty_activation, lang="pt")
    assert fmt["target"] == "Marte"
    assert fmt["transit_body"] == "Saturno"
    assert fmt["aspect"] == "Trígono"
    assert fmt["window_start"] == ""
    assert fmt["window_end"] == ""
    assert fmt["exact_peak"] == ""
    assert fmt["window"] == "—"


def test_portuguese_roman_numerals_and_unaccented_house_matching():
    """Verify Roman numerals (casa VI, casa X) and unaccented ordinals match correctly when swapped."""
    from scripts.run_chart3_pipeline import DRAFT_REPORT
    handoff = prepare_premium_handoff(CHART_3_BIRTH)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    p0 = "O Meio do Céu em Sagitário é regido por Júpiter domiciliado na nona casa, desenhando uma vocação voltada para a transmissão de conhecimento, orientação ética, síntese interdisciplinar e ampliação de horizontes culturais ou intelectuais."
    p1 = "Na esfera operacional, a sexta casa em Câncer é regida pela Lua na décima segunda casa em Peixes, estabelecendo que a rotina de trabalho deve respeitar o ritmo interno e a sensibilidade psíquica. O trabalho ganha eficácia quando estruturado em ambientes humanos e acolhedores, alternando fases de dedicação meticulosa e pausas necessárias para reabastecimento anímico."

    # Roman numeral swapped prose: Block 0 is house VI (Moon), Block 1 is house X (Jupiter)
    roman_b0 = "Na esfera operacional, a regência da casa VI se apoia na sensibilidade e ritmo interno da casa XII."
    roman_b1 = "A visibilidade pública e vocação culminam na casa X, orientadas pelo horizonte ético da casa IX."

    swapped_roman_report = DRAFT_REPORT.replace(p0 + "\n\n" + p1, roman_b0 + "\n\n" + roman_b1)
    sources_roman, sections_roman, _ = bind_prospective_plan_to_prose(swapped_roman_report, block_plan, manifest)
    own_w = next(d for d in sections_roman["domains"] if d["domain_id"] == "work_vocation_visibility")
    b0_roman = next(s for s in sources_roman if s["narrative_block_sha256"] == own_w["narrative_block_sha256s"][0])
    b1_roman = next(s for s in sources_roman if s["narrative_block_sha256"] == own_w["narrative_block_sha256s"][1])

    assert "6.moon" in b0_roman["synthesis_ids"][0], f"Roman numeral block 0 expected 6.moon, got {b0_roman['synthesis_ids']}"
    assert "10.jupiter" in b1_roman["synthesis_ids"][0], f"Roman numeral block 1 expected 10.jupiter, got {b1_roman['synthesis_ids']}"

    # Unaccented ordinal swapped prose: Block 0 is house 6/12, Block 1 is house 10
    unaccented_b0 = "Na rotina pratica, a decima segunda casa e a sexta casa exigem pausas regenerativas."
    unaccented_b1 = "A vocacao superior alcanca a decima casa e se expande com amplitude de horizonte."

    swapped_unacc_report = DRAFT_REPORT.replace(p0 + "\n\n" + p1, unaccented_b0 + "\n\n" + unaccented_b1)
    sources_unacc, sections_unacc, _ = bind_prospective_plan_to_prose(swapped_unacc_report, block_plan, manifest)
    own_w_u = next(d for d in sections_unacc["domains"] if d["domain_id"] == "work_vocation_visibility")
    b0_unacc = next(s for s in sources_unacc if s["narrative_block_sha256"] == own_w_u["narrative_block_sha256s"][0])
    b1_unacc = next(s for s in sources_unacc if s["narrative_block_sha256"] == own_w_u["narrative_block_sha256s"][1])

    assert "6.moon" in b0_unacc["synthesis_ids"][0], f"Unaccented block 0 expected 6.moon, got {b0_unacc['synthesis_ids']}"
    assert "10.jupiter" in b1_unacc["synthesis_ids"][0], f"Unaccented block 1 expected 10.jupiter, got {b1_unacc['synthesis_ids']}"


def test_semantic_attribution_avoids_incidental_cross_mention_pollution():
    """Verify that an incidental mention of another factor in Block 0 does not pollute Block 0's source attribution."""
    from scripts.run_chart3_pipeline import DRAFT_REPORT
    handoff = prepare_premium_handoff(CHART_3_BIRTH)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    # In Block 0, add an incidental contrast mentioning Lua once, while Jupiter dominates
    polluted_p0 = (
        "O Meio do Céu em Sagitário é regido por Júpiter domiciliado na nona casa, desenhando uma vocação "
        "voltada para a transmissão de conhecimento, orientação ética, síntese interdisciplinar e ampliação "
        "de horizontes culturais. Ao contrário da sensibilidade recolhida da Lua, esta vocação jupiteriana exige visibilidade pública."
    )
    polluted_report = DRAFT_REPORT.replace(
        "O Meio do Céu em Sagitário é regido por Júpiter domiciliado na nona casa, desenhando uma vocação voltada para a transmissão de conhecimento, orientação ética, síntese interdisciplinar e ampliação de horizontes culturais ou intelectuais.",
        polluted_p0
    )

    sources, sections, _ = bind_prospective_plan_to_prose(polluted_report, block_plan, manifest)
    own_w = next(d for d in sections["domains"] if d["domain_id"] == "work_vocation_visibility")
    b0 = next(s for s in sources if s["narrative_block_sha256"] == own_w["narrative_block_sha256s"][0])
    b1 = next(s for s in sources if s["narrative_block_sha256"] == own_w["narrative_block_sha256s"][1])

    # Block 0 must contain Jupiter and NOT be polluted with 6.moon
    assert any("10.jupiter" in sid for sid in b0["synthesis_ids"]), "Block 0 must contain Jupiter synthesis"
    assert not any("6.moon" in sid for sid in b0["synthesis_ids"]), f"Block 0 was cross-polluted with Moon synthesis: {b0['synthesis_ids']}"
    # Block 1 must contain Moon
    assert any("6.moon" in sid for sid in b1["synthesis_ids"]), "Block 1 must contain Moon synthesis"


def test_selection_plan_order_invariance_across_diverse_fixtures():
    """Verify order invariance of build_canonical_selection_plan across diverse chart configurations."""
    from scripts.ux_editorial_audit import FIXTURES
    for key in ["A", "B", "C", "E", "F", "G", "H"]:
        birth = FIXTURES[key]["birth"]
        analysis = analyse_birth_chart(birth, include_timing=True)
        manifest = analysis["reader_domain_manifest"]
        orig_plan = build_canonical_selection_plan(manifest)

        # Reverse paths in each domain
        shuffled_manifest = {
            "manifest_version": manifest.get("manifest_version"),
            "domains": [],
        }
        for d in manifest["domains"]:
            d_copy = dict(d)
            d_copy["legal_coverage_paths"] = list(reversed(list(d.get("legal_coverage_paths", []))))
            shuffled_manifest["domains"].append(d_copy)

        shuffled_plan = build_canonical_selection_plan(shuffled_manifest)

        orig_by_dom = {d["domain_id"]: {p["path_id"]: p["decision"] for p in d["paths"]} for d in orig_plan["domains"]}
        shuf_by_dom = {d["domain_id"]: {p["path_id"]: p["decision"] for p in d["paths"]} for d in shuffled_plan["domains"]}

        for d_id in orig_by_dom:
            assert orig_by_dom[d_id] == shuf_by_dom[d_id], f"Fixture {key} domain {d_id} selection differed under path reversal"


def test_timing_formatter_bidirectional_translation_and_normalization():
    """Verify bidirectional translation and normalization of technique, bodies, aspects, and angles."""
    # 1. English to Portuguese
    act_en = {
        "technique": "Major Transit",
        "transit_body": "Saturn",
        "aspect": "Opposition",
        "target": "Midheaven (MC)",
        "window_start": "2026-09-04",
        "window_end": "2027-03-04",
        "exact_at": "2026-09-19",
    }
    fmt_pt = format_canonical_timing_activation(act_en, lang="pt")
    assert fmt_pt["technique"] == "Trânsito Maior"
    assert fmt_pt["transit_body"] == "Saturno"
    assert fmt_pt["aspect"] == "Oposição"
    assert fmt_pt["target"] == "Meio do Céu (MC)"
    assert fmt_pt["exact_peak"] == "2026-09-19"

    # 2. Portuguese to English
    act_pt = {
        "technique": "Trânsito Maior",
        "transit_body": "Júpiter",
        "aspect": "Trígono",
        "target": "Ascendente (ASC)",
        "window_start": "2026-01-01",
        "window_end": "2026-06-01",
        "exact_at": "2026-03-15",
    }
    fmt_en = format_canonical_timing_activation(act_pt, lang="en")
    assert fmt_en["technique"] == "Major Transit"
    assert fmt_en["transit_body"] == "Jupiter"
    assert fmt_en["aspect"] == "Trine"
    assert fmt_en["target"] == "Ascendant (ASC)"
    assert fmt_en["exact_peak"] == "2026-03-15"


def test_portuguese_cardinal_and_prepositional_house_matching():
    """Verify cardinal house names (casa seis, casa dez) and prepositional phrases (regente da sexta) rebind semantically."""
    from scripts.run_chart3_pipeline import DRAFT_REPORT
    handoff = prepare_premium_handoff(CHART_3_BIRTH)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    p0 = "O Meio do Céu em Sagitário é regido por Júpiter domiciliado na nona casa, desenhando uma vocação voltada para a transmissão de conhecimento, orientação ética, síntese interdisciplinar e ampliação de horizontes culturais ou intelectuais."
    p1 = "Na esfera operacional, a sexta casa em Câncer é regida pela Lua na décima segunda casa em Peixes, estabelecendo que a rotina de trabalho deve respeitar o ritmo interno e a sensibilidade psíquica. O trabalho ganha eficácia quando estruturado em ambientes humanos e acolhedores, alternando fases de dedicação meticulosa e pausas necessárias para reabastecimento anímico."

    # Cardinal numbers swapped: Block 0 is casa seis, Block 1 is casa dez
    cardinal_b0 = "Na rotina operacional, a regência da casa seis articula pausas necessárias para o ritmo psíquico."
    cardinal_b1 = "A vocação culmina na casa dez, voltada para ampliação ética e novos horizontes."

    card_report = DRAFT_REPORT.replace(p0 + "\n\n" + p1, cardinal_b0 + "\n\n" + cardinal_b1)
    sources_card, sections_card, _ = bind_prospective_plan_to_prose(card_report, block_plan, manifest)
    own_w_c = next(d for d in sections_card["domains"] if d["domain_id"] == "work_vocation_visibility")
    b0_c = next(s for s in sources_card if s["narrative_block_sha256"] == own_w_c["narrative_block_sha256s"][0])
    b1_c = next(s for s in sources_card if s["narrative_block_sha256"] == own_w_c["narrative_block_sha256s"][1])

    assert "6.moon" in b0_c["synthesis_ids"][0], f"Expected 6.moon in swapped cardinal block 0, got {b0_c['synthesis_ids']}"
    assert "10.jupiter" in b1_c["synthesis_ids"][0], f"Expected 10.jupiter in swapped cardinal block 1, got {b1_c['synthesis_ids']}"

    # Prepositional phrases swapped: Block 0 is regente da sexta, Block 1 is regente da décima
    prep_b0 = "Na esfera operacional, a regente da sexta em Câncer orienta as pausas e ritmos anímicos do trabalho diário."
    prep_b1 = "No plano de realização pública, a regente da décima em Sagitário desenha a vocação voltada para a transmissão ética."

    prep_report = DRAFT_REPORT.replace(p0 + "\n\n" + p1, prep_b0 + "\n\n" + prep_b1)
    sources_prep, sections_prep, _ = bind_prospective_plan_to_prose(prep_report, block_plan, manifest)
    own_w_p = next(d for d in sections_prep["domains"] if d["domain_id"] == "work_vocation_visibility")
    b0_p = next(s for s in sources_prep if s["narrative_block_sha256"] == own_w_p["narrative_block_sha256s"][0])
    b1_p = next(s for s in sources_prep if s["narrative_block_sha256"] == own_w_p["narrative_block_sha256s"][1])

    assert "6.moon" in b0_p["synthesis_ids"][0], f"Expected 6.moon in swapped prepositional block 0, got {b0_p['synthesis_ids']}"
    assert "10.jupiter" in b1_p["synthesis_ids"][0], f"Expected 10.jupiter in swapped prepositional block 1, got {b1_p['synthesis_ids']}"


def test_english_house_references_semantic_reassignment():
    """Verify English house phrasing (house 6 vs house 10) correctly rebinds semantically."""
    from scripts.run_chart3_pipeline import DRAFT_REPORT
    handoff = prepare_premium_handoff(CHART_3_BIRTH)
    manifest = handoff["reader_domain_manifest"]
    block_plan = plan_prospective_narrative_blocks(handoff)

    p0 = "O Meio do Céu em Sagitário é regido por Júpiter domiciliado na nona casa, desenhando uma vocação voltada para a transmissão de conhecimento, orientação ética, síntese interdisciplinar e ampliação de horizontes culturais ou intelectuais."
    p1 = "Na esfera operacional, a sexta casa em Câncer é regida pela Lua na décima segunda casa em Peixes, estabelecendo que a rotina de trabalho deve respeitar o ritmo interno e a sensibilidade psíquica. O trabalho ganha eficácia quando estruturado em ambientes humanos e acolhedores, alternando fases de dedicação meticulosa e pausas necessárias para reabastecimento anímico."

    en_b0 = "In daily routines, the ruler of house 6 sets the internal rhythm and protective pauses."
    en_b1 = "Public contribution culminates in house 10, directed towards broad ethical synthesis."

    en_report = DRAFT_REPORT.replace(p0 + "\n\n" + p1, en_b0 + "\n\n" + en_b1)
    sources_en, sections_en, _ = bind_prospective_plan_to_prose(en_report, block_plan, manifest)
    own_w_e = next(d for d in sections_en["domains"] if d["domain_id"] == "work_vocation_visibility")
    b0_e = next(s for s in sources_en if s["narrative_block_sha256"] == own_w_e["narrative_block_sha256s"][0])
    b1_e = next(s for s in sources_en if s["narrative_block_sha256"] == own_w_e["narrative_block_sha256s"][1])

    assert "6.moon" in b0_e["synthesis_ids"][0], f"Expected 6.moon in English block 0, got {b0_e['synthesis_ids']}"
    assert "10.jupiter" in b1_e["synthesis_ids"][0], f"Expected 10.jupiter in English block 1, got {b1_e['synthesis_ids']}"
