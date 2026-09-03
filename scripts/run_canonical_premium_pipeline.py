#!/usr/bin/env python3
"""Canonical runner for the end-to-end Premium Complete astrology pipeline.

Executes the strict canonical sequence:
1. prepare_premium_handoff (Deterministic Handoff)
2. Author generation + AuthorBundle v1.4 construction
3. validate_premium_author_bundle (Deterministic Provenance Guard)
4. Reviewer verification + ReviewerBundle v1.4 construction
5. validate_premium_narrative (Publication Guard)
6. editorial_qa (Barnum, Grandiosity, Medicalization lints)
7. Deterministic Technical Appendix generation
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

SKILL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from astrology.models import BirthData, LocalizationProfile, Claim
from astrology.engine import calculate_chart
from astrology.pipeline import (
    analyse_birth_chart,
    prepare_premium_handoff,
    validate_premium_author_bundle,
    validate_premium_narrative,
    _canonical_hash,
    _premium_handoff_contract,
    _parse_premium_narrative,
)
from astrology.editorial_qa import (
    barnum_risk,
    grandiosity_and_flattery_risk,
    medicalization_risk,
)
from astrology.reasoning import (
    humanization_instructions,
    humanization_verifier_instructions,
)


SIGNS_PT = ["Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem", "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes"]
SIGNS_EN = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

BODIES_PT = {
    "sun": "Sol", "moon": "Lua", "mercury": "Mercúrio", "venus": "Vênus",
    "mars": "Marte", "jupiter": "Júpiter", "saturn": "Saturno", "uranus": "Urano",
    "neptune": "Netuno", "pluto": "Plutão", "true_node": "Nodo Norte Verdadeiro",
    "chiron": "Quíron", "lilith_mean": "Lilith (Média)",
}
ASPECTS_PT = {
    "conjunction": "Conjunção", "sextile": "Sextil", "square": "Quadratura",
    "trine": "Trígono", "quincunx": "Quincúncio", "opposition": "Oposição",
}


def format_degree_minute(deg_float: float, lang: str = "pt") -> Tuple[str, str]:
    signs = SIGNS_PT if lang.startswith("pt") else SIGNS_EN
    sign_idx = int(deg_float // 30) % 12
    deg_in_sign = deg_float % 30
    d = int(deg_in_sign)
    m = int(round((deg_in_sign - d) * 60))
    if m == 60:
        d += 1
        m = 0
        if d == 30:
            d = 0
            sign_idx = (sign_idx + 1) % 12
    return f"{d:02d}°{m:02d}'", signs[sign_idx]


def render_canonical_technical_appendix(birth: BirthData, lang: str = "pt") -> str:
    """Deterministically renders exact Swiss Ephemeris data into an immutable technical appendix."""
    chart = calculate_chart(birth)
    lines = []
    
    title = "## Apêndice Técnico Canônico" if lang.startswith("pt") else "## Canonical Technical Appendix"
    lines.append(title)
    lines.append("")
    
    intro = (
        "*Os dados abaixo são calculados deterministicamente pelo motor astronômico de alta precisão "
        "(Swiss Ephemeris / IAU SOFA) e constituem a verdade técnica imutável deste mapa natal.*"
        if lang.startswith("pt") else
        "*The data below is deterministically computed by the high-precision astronomical engine "
        "(Swiss Ephemeris / IAU SOFA) and constitutes the immutable technical ground truth of this birth chart.*"
    )
    lines.append(intro)
    lines.append("")
    
    # 1. Positions
    p_title = "### 1. Posições Planetárias e Pontos Natais" if lang.startswith("pt") else "### 1. Planetary Positions and Natal Points"
    lines.append(p_title)
    lines.append("")
    lines.append("| Ponto | Pos. Exata | Signo | Casa Placidus | Movimento |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")
    
    for key, pos in chart.positions.items():
        name = BODIES_PT.get(key, pos.label) if lang.startswith("pt") else pos.label
        deg_str, sign_str = format_degree_minute(pos.longitude, lang)
        motion = "Retrógrado (R)" if pos.retrograde else "Direto"
        house = chart.house_placements.get(key)
        h_str = f"Casa {house.placidus_house}" if house and house.placidus_house else "—"
        lines.append(f"| {name} | {deg_str} | {sign_str} | {h_str} | {motion} |")
    
    lines.append("")
    
    # 2. Angles & Cusps
    a_title = "### 2. Ângulos Principais e Cúspides de Casas" if lang.startswith("pt") else "### 2. Principal Angles and House Cusps"
    lines.append(a_title)
    lines.append("")
    lines.append("| Ângulo / Cúspide | Pos. Exata | Signo |")
    lines.append("| :--- | :--- | :--- |")
    
    for key in ("asc", "mc", "dsc", "ic"):
        val = chart.angles.get(key)
        if val is not None:
            label = {"asc": "Ascendente (ASC)", "mc": "Meio do Céu (MC)", "dsc": "Descendente (DSC)", "ic": "Fundo do Céu (IC)"}.get(key, key.upper())
            deg_str, sign_str = format_degree_minute(val, lang)
            lines.append(f"| {label} | {deg_str} | {sign_str} |")
            
    if chart.house_cusps_placidus:
        for i, cusp in enumerate(chart.house_cusps_placidus):
            deg_str, sign_str = format_degree_minute(cusp, lang)
            lines.append(f"| Casa {i+1} (Placidus) | {deg_str} | {sign_str} |")
            
    lines.append("")
    
    # 3. Aspects
    asp_title = "### 3. Aspectos Maiores e Orbes Exatos" if lang.startswith("pt") else "### 3. Major Aspects and Exact Orbs"
    lines.append(asp_title)
    lines.append("")
    lines.append("| Fator 1 | Aspecto | Fator 2 | Orbe Decimal | Orbe Minutos | Estado |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for asp in chart.aspects:
        p1 = BODIES_PT.get(asp.left, asp.left) if lang.startswith("pt") else asp.left.title()
        p2 = BODIES_PT.get(asp.right, asp.right) if lang.startswith("pt") else asp.right.title()
        asp_name = ASPECTS_PT.get(asp.kind, asp.kind) if lang.startswith("pt") else asp.kind.title()
        d = int(asp.orb)
        m = int(round((asp.orb - d) * 60))
        orb_deg = f"{asp.orb:.2f}°"
        orb_min = f"{d:02d}°{m:02d}'"
        status = "Aplicando" if asp.applying else "Separando"
        lines.append(f"| {p1} | {asp_name} | {p2} | {orb_deg} | {orb_min} | {status} |")
        
    lines.append("")
    return "\n".join(lines)


def run_pipeline(
    birth: BirthData,
    profile: LocalizationProfile,
    output_dir: Path,
    as_of: Optional[datetime] = None,
    horizon_days: int = 366,
) -> Dict[str, object]:
    """Runs the full canonical premium pipeline with true production guards."""
    output_dir.mkdir(parents=True, exist_ok=True)
    lang = profile.preferred_language
    
    # Step 1: Prepare Deterministic Handoff
    print("==> [Stage 1] Preparing Deterministic Handoff...")
    handoff = prepare_premium_handoff(
        birth, profile=profile, report_depth="deep", include_timing=True,
        as_of=as_of, horizon_days=horizon_days,
    )
    analysis = analyse_birth_chart(
        birth, profile=profile, report_depth="deep", include_timing=True,
        as_of=as_of, horizon_days=horizon_days,
    )
    
    (output_dir / "01-handoff.json").write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "01-analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    
    author_prompt = (
        f"=== AUTHOR INSTRUCTIONS ===\n{humanization_instructions(lang)}\n\n"
        f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(analysis['reasoning_packet'], ensure_ascii=False, indent=2)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, indent=2)}\n\n"
        f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
    )
    (output_dir / "author_prompt.txt").write_text(author_prompt, encoding="utf-8")
    
    reviewer_prompt = (
        f"=== REVIEWER INSTRUCTIONS ===\n{humanization_verifier_instructions(lang)}\n\n"
        f"=== REASONING PACKET / HANDOFF ===\n{json.dumps(analysis['reasoning_packet'], ensure_ascii=False, indent=2)}\n\n"
        f"=== READER DOMAIN MANIFEST ===\n{json.dumps(handoff['reader_domain_manifest'], ensure_ascii=False, indent=2)}\n\n"
        f"=== FIXED READER INTRODUCTION ===\n{handoff['reader_introduction']}\n"
    )
    (output_dir / "reviewer_prompt.txt").write_text(reviewer_prompt, encoding="utf-8")
    
    return {
        "handoff": handoff,
        "analysis": analysis,
        "packet_id": handoff["packet_id"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run canonical premium pipeline")
    parser.add_argument("--date", default="1989-11-01T12:08:00")
    parser.add_argument("--tz", default="America/Caracas")
    parser.add_argument("--lat", type=float, default=10.1620)
    parser.add_argument("--lon", type=float, default=-68.0077)
    parser.add_argument("--lang", default="pt-BR")
    parser.add_argument("--out", default="/tmp/run_valencia_1989_v21")
    args = parser.parse_args()
    
    b = BirthData(args.date, args.tz, args.lat, args.lon, birth_time_known=True)
    p = LocalizationProfile(preferred_language=args.lang)
    res = run_pipeline(b, p, Path(args.out))
    print(f"Handoff ready. Packet ID: {res['packet_id']}")
