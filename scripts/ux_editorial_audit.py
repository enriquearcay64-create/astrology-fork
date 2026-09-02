#!/usr/bin/env python3
"""Generate fixed UX/editorial A/B fixtures and mechanical reading metrics.

The reader personas are audit lenses only. They are written to the manifest but
never passed to the astrological pipeline. This protects the test from gender,
age, biography, and skepticism leaking into interpretation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Dict, List, Tuple

SKILL_ROOT = Path(__file__).resolve().parents[1]
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from astrology.config import LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION, PREMIUM_HANDOFF_CONTRACT_VERSION
from astrology.models import BirthData, LocalizationProfile
from astrology.pipeline import _parse_premium_narrative, _parse_premium_narrative_v13, analyse_birth_chart
from astrology.editorial_qa import barnum_risk, exact_reuse, llm_semantic_review_prompt, report_swap_risk, semantic_cross_report_similarity


AS_OF = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
WORDS_PER_PAGE = 450
WORDS_PER_MINUTE = 220

FIXTURES = {
    "A": {
        "reader_profile": {
            "language": "pt-BR",
            "description": "Adulto, homem, leigo em astrologia, interessado em autoconhecimento, objetivo e avesso a misticismo excessivo.",
            "audit_only": True,
        },
        "birth": BirthData(
            local_datetime="1990-07-12T14:30:00",
            timezone_name="America/Sao_Paulo",
            latitude=-23.5505,
            longitude=-46.6333,
            place_label="Synthetic A — São Paulo",
            source="synthetic_ux_fixture",
        ),
        "localization": LocalizationProfile(
            preferred_language="pt-BR",
            current_country="Brazil",
            cultural_context="Brazil",
            source="synthetic_ux_fixture",
            localization_level="light",
        ),
    },
    "B": {
        "reader_profile": {
            "language": "pt-BR",
            "description": "Adulta, mulher, pouco conhecimento técnico, interessada em emoções, relações e desenvolvimento, com preferência por profundidade sem fadiga.",
            "audit_only": True,
        },
        "birth": BirthData(
            local_datetime="1985-03-24T06:45:00",
            timezone_name="Europe/Lisbon",
            latitude=38.7223,
            longitude=-9.1393,
            place_label="Synthetic B — Lisboa",
            source="synthetic_ux_fixture",
        ),
        "localization": LocalizationProfile(
            preferred_language="pt-BR",
            current_country="Portugal",
            cultural_context="Portugal",
            source="synthetic_ux_fixture",
            localization_level="light",
        ),
    },
    "C": {
        "reader_profile": {
            "language": "en-US",
            "description": "Pessoa de 63 anos, gênero não especificado, leitora cética, sem formação astrológica e com preferência por reflexão simbólica em linguagem direta.",
            "audit_only": True,
            "selection_reason": "Testa idade, idioma, contexto cultural, ceticismo e neutralidade de gênero sem presumir preferências a partir de sexo.",
        },
        "birth": BirthData(
            local_datetime="1962-11-05T18:20:00",
            timezone_name="Asia/Tokyo",
            latitude=35.6762,
            longitude=139.6503,
            place_label="Synthetic C — Tokyo",
            source="synthetic_ux_fixture",
        ),
        "localization": LocalizationProfile(
            preferred_language="en-US",
            current_country="Canada",
            cultural_context="English-speaking Canada",
            source="synthetic_ux_fixture",
            localization_level="light",
        ),
    },
    "D": {
        "reader_profile": {
            "language": "pt-BR",
            "description": "Pessoa adulta com hora de nascimento desconhecida; testa se o produto continua útil sem inventar casas, ângulos ou timing tópico.",
            "audit_only": True,
        },
        "birth": BirthData(
            local_datetime="1978-09-19T12:00:00", timezone_name="America/Argentina/Buenos_Aires",
            latitude=-34.6037, longitude=-58.3816, place_label="Synthetic D — Buenos Aires",
            birth_time_known=False, source="synthetic_ux_fixture",
        ),
        "localization": LocalizationProfile(preferred_language="pt-BR", localization_level="off", source="synthetic_ux_fixture"),
    },
    "E": {
        "reader_profile": {
            "language": "en-US",
            "description": "Leitor técnico que testa latitude alta e indisponibilidade explícita de Placidus, sem transformar ausência em convergência.",
            "audit_only": True,
        },
        "birth": BirthData(
            local_datetime="1995-02-13T11:15:00", timezone_name="Arctic/Longyearbyen",
            latitude=78.2232, longitude=15.6469, place_label="Synthetic E — Longyearbyen", source="synthetic_ux_fixture",
        ),
        "localization": LocalizationProfile(preferred_language="en-US", current_country="Norway", localization_level="light", source="synthetic_ux_fixture"),
    },
    "F": {
        "reader_profile": {
            "language": "pt-BR",
            "description": "Profissional de meia-idade que prefere leitura curta; testa uma carta e fase temporal diferentes sem usar perfil como dado interpretativo.",
            "audit_only": True,
        },
        "birth": BirthData(
            local_datetime="1971-12-01T22:40:00", timezone_name="Africa/Johannesburg",
            latitude=-26.2041, longitude=28.0473, place_label="Synthetic F — Johannesburg", source="synthetic_ux_fixture",
        ),
        "localization": LocalizationProfile(preferred_language="pt-BR", localization_level="off", source="synthetic_ux_fixture"),
    },
    "G": {
        "reader_profile": {
            "language": "pt-BR",
            "description": "Leitora bilíngue com contexto venezuelano; testa localização leve como renderização e não como psicologia.",
            "audit_only": True,
        },
        "birth": BirthData(
            local_datetime="2001-06-30T03:25:00", timezone_name="America/Caracas",
            latitude=10.4806, longitude=-66.9036, place_label="Synthetic G — Caracas", source="synthetic_ux_fixture",
        ),
        "localization": LocalizationProfile(preferred_language="pt-BR", current_country="Venezuela", cultural_context="Venezuela", localization_level="light", source="synthetic_ux_fixture"),
    },
    "H": {
        "reader_profile": {
            "language": "en-US",
            "description": "Adulto jovem, leitor rápido e cético; testa leitura em inglês, tom direto e baixa dependência de jargão.",
            "audit_only": True,
        },
        "birth": BirthData(
            local_datetime="2004-04-08T16:10:00", timezone_name="Europe/London",
            latitude=51.5072, longitude=-0.1276, place_label="Synthetic H — London", source="synthetic_ux_fixture",
        ),
        "localization": LocalizationProfile(preferred_language="en-US", current_country="United Kingdom", localization_level="light", source="synthetic_ux_fixture"),
    },
}

JARGON = {
    "whole sign": r"\b(?:whole sign|signo inteiro)\b",
    "placidus": r"\bplacidus\b",
    "profection": r"\b(?:profection|profe[cç][aã]o|profec[cç][aã]o)\w*\b",
    "time lord": r"\b(?:time lord|senhor do ano)\b",
    "dispositor": r"\bdispositor\w*\b",
    "dignity": r"\b(?:dignit\w*|dignidade\w*)\b",
    "orb": r"\b(?:orb|orbe)\b",
    "applying": r"\b(?:applying|aplicando|aplicativo)\b",
    "retrograde": r"\b(?:retrograde|retrograd\w*|retr[oó]grad\w*)\b",
    "angularity": r"\b(?:angularity|angularidade)\b",
    "house": r"\b(?:house|houses|casa|casas)\b",
    "aspect names": r"\b(?:conjunction|square|trine|sextile|opposition|quincunx|conjun[cç][aã]o|quadratura|tr[ií]gono|sextil|oposi[cç][aã]o|quinc[uú]ncio)\b",
}

BARNUM_PATTERNS = {
    "deep feelings": r"\b(?:feel(?:s|ing)? deeply|sente profundamente)\b",
    "freedom": r"\b(?:value(?:s)? freedom|valoriza (?:a )?liberdade)\b",
    "self doubt": r"\b(?:sometimes you doubt yourself|[àa]s vezes voc[eê] duvida de si)\b",
    "strong but sensitive": r"\b(?:strong,? but sensitive|forte,? mas sens[ií]vel)\b",
    "people and space": r"\b(?:like(?:s)? people.*need(?:s)? space|gosta de pessoas.*precisa (?:de )?espa[cç]o)\b",
}

STOPWORDS = set(
    "a an and are as at be because but by can could de da das do dos e em esta este for from has have how i if in is it its na no not of on or o os para por que se the their this to um uma you your você como com mais menos não seu sua seus suas isso essa esse ao aos às ou quando where what which who will with sem sobre entre into under per than then these those they them there here also most muito uma the".split()
)


def primitive(value: object) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return {name: primitive(getattr(value, name)) for name in value.__dataclass_fields__}
    if isinstance(value, dict):
        return {str(key): primitive(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [primitive(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def words(text: str) -> List[str]:
    return re.findall(r"[^\W\d_]+(?:[-’'][^\W\d_]+)*|\d+(?:[.,]\d+)*", text, flags=re.UNICODE)


def _strip_markdown(line: str) -> str:
    line = re.sub(r"<[^>]+>", " ", line)
    line = re.sub(r"[`*_>#|]", " ", line)
    line = re.sub(r"\[[^\]]+\]\([^\)]+\)", " ", line)
    return re.sub(r"\s+", " ", line).strip()


def _prose_paragraphs(text: str) -> List[str]:
    paragraphs: List[str] = []
    in_code = False
    for block in re.split(r"\n\s*\n", text):
        raw_lines = block.splitlines()
        if not raw_lines:
            continue
        cleaned: List[str] = []
        skip_block = False
        for line in raw_lines:
            if line.lstrip().startswith("```"):
                in_code = not in_code
                skip_block = True
                continue
            if in_code:
                skip_block = True
                continue
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "- ", "* ", "|", "<details", "</details", "<summary")) or re.match(r"\d+[.)]\s+", stripped):
                skip_block = True
                continue
            cleaned.append(_strip_markdown(stripped))
        if not skip_block and cleaned:
            paragraph = " ".join(cleaned).strip()
            if len(words(paragraph)) >= 3:
                paragraphs.append(paragraph)
    return paragraphs


def _section_sizes(text: str) -> List[Tuple[str, int]]:
    matches = list(re.finditer(r"(?m)^##\s+(.+?)\s*$", text))
    sizes: List[Tuple[str, int]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sizes.append((match.group(1), len(words(text[start:end]))))
    return sizes


def _details_word_count(text: str) -> int:
    return sum(len(words(match.group(1))) for match in re.finditer(r"<details[^>]*>(.*?)</details>", text, flags=re.I | re.S))


def _without_details(text: str) -> str:
    return re.sub(r"<details[^>]*>.*?</details>", " ", text, flags=re.I | re.S)


def _content_tokens(sentence: str) -> set[str]:
    tokens = {token.casefold() for token in words(sentence)}
    return {token for token in tokens if token not in STOPWORDS and len(token) > 2 and not token.isdigit()}


def _sentences(text: str) -> List[str]:
    plain = re.sub(r"```.*?```", " ", text, flags=re.S)
    plain = re.sub(r"<[^>]+>", " ", plain)
    plain = re.sub(r"(?m)^#{1,6}\s+", "", plain)
    plain = re.sub(r"(?m)^[-*]\s+", "", plain)
    return [re.sub(r"\s+", " ", item).strip() for item in re.split(r"(?<=[.!?])\s+|\n+", plain) if len(words(item)) >= 6]


def _redundant_pairs(text: str, threshold: float = 0.58) -> List[Dict[str, object]]:
    candidates = _sentences(text)
    tokenized = [_content_tokens(item) for item in candidates]
    pairs: List[Dict[str, object]] = []
    for left in range(len(candidates)):
        if len(tokenized[left]) < 5:
            continue
        for right in range(left + 1, len(candidates)):
            if len(tokenized[right]) < 5:
                continue
            union = tokenized[left] | tokenized[right]
            score = len(tokenized[left] & tokenized[right]) / len(union) if union else 0.0
            if score >= threshold:
                pairs.append({"similarity": round(score, 3), "left": candidates[left], "right": candidates[right]})
    return sorted(pairs, key=lambda item: -float(item["similarity"]))[:25]


def report_metrics(text: str) -> Dict[str, object]:
    word_count = len(words(text))
    section_sizes = _section_sizes(text)
    paragraph_sizes = [len(words(item)) for item in _prose_paragraphs(text)]
    bullet_sizes = [
        len(words(re.sub(r"^\s*(?:[-+*]|\d+[.)])\s+", "", line)))
        for line in text.splitlines()
        if re.match(r"^\s*(?:[-+*]|\d+[.)])\s+", line)
    ]
    subheading_texts = [match.group(1).strip() for match in re.finditer(r"(?m)^###\s+(.+?)\s*$", text)]
    details_words = _details_word_count(text)
    lowered = text.casefold()
    jargon = {label: len(re.findall(pattern, lowered, flags=re.I)) for label, pattern in JARGON.items()}
    jargon = {label: count for label, count in jargon.items() if count}
    barnum = {label: len(re.findall(pattern, lowered, flags=re.I)) for label, pattern in BARNUM_PATTERNS.items()}
    barnum = {label: count for label, count in barnum.items() if count}
    return {
        "words": word_count,
        "estimated_pages_at_450_words": round(word_count / WORDS_PER_PAGE, 1),
        "estimated_reading_minutes_at_220_wpm": round(word_count / WORDS_PER_MINUTE, 1),
        "h2_sections": len(section_sizes),
        "all_headings": len(re.findall(r"(?m)^#{1,6}\s+", text)),
        "subheadings": len(subheading_texts),
        "subheading_words": sum(len(words(item)) for item in subheading_texts),
        "average_h2_section_words": round(sum(size for _, size in section_sizes) / len(section_sizes), 1) if section_sizes else 0,
        "largest_h2_sections": sorted(({"section": name, "words": size} for name, size in section_sizes), key=lambda item: -item["words"])[:5],
        "prose_paragraphs": len(paragraph_sizes),
        "average_prose_paragraph_words": round(sum(paragraph_sizes) / len(paragraph_sizes), 1) if paragraph_sizes else 0,
        "maximum_prose_paragraph_words": max(paragraph_sizes, default=0),
        "paragraphs_over_150_words": sum(size > 150 for size in paragraph_sizes),
        "bullets": len(bullet_sizes),
        "average_bullet_words": round(sum(bullet_sizes) / len(bullet_sizes), 1) if bullet_sizes else 0,
        "tables": len(re.findall(r"(?m)^\|.*\|\s*$", text)) // 2,
        "details_blocks": len(re.findall(r"<details", text, flags=re.I)),
        "words_inside_details": details_words,
        "hidden_word_share": round(details_words / word_count, 3) if word_count else 0,
        "visible_words_estimate": max(0, word_count - details_words),
        "jargon_hits": jargon,
        "jargon_total": sum(jargon.values()),
        "barnum_pattern_hits": barnum,
        "semantic_barnum_risk": barnum_risk(text),
        "semantic_redundancy_pairs": _redundant_pairs(text),
        "visible_semantic_redundancy_pairs": _redundant_pairs(_without_details(text)),
    }


def normalized_sentence(sentence: str) -> str:
    return " ".join(token.casefold() for token in words(sentence))


def cross_report_reuse(reports: Dict[str, Dict[str, str]]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for depth in ("executive", "deep", "technical"):
        index: Dict[str, Dict[str, object]] = {}
        for profile_id, by_depth in reports.items():
            for sentence in _sentences(by_depth[depth]):
                normalized = normalized_sentence(sentence)
                if len(words(normalized)) < 7:
                    continue
                item = index.setdefault(normalized, {"sentence": sentence, "profiles": []})
                if profile_id not in item["profiles"]:
                    item["profiles"].append(profile_id)
        reused = [item for item in index.values() if len(item["profiles"]) >= 2]
        result[depth] = sorted(reused, key=lambda item: (-len(item["profiles"]), -len(words(str(item["sentence"])))))
    return result


def individuality_metrics(reports: Dict[str, Dict[str, str]]) -> Dict[str, object]:
    output: Dict[str, object] = {}
    for depth in ("executive", "deep", "technical"):
        selected = {profile: values[depth] for profile, values in reports.items()}
        output[depth] = {
            "exact_interpretive_sentence_reuse": exact_reuse(selected),
            "semantic_cross_report_similarity": semantic_cross_report_similarity(selected),
            "report_swap_pre_screen": report_swap_risk(selected),
        }
    output["llm_semantic_review_prompt"] = llm_semantic_review_prompt()
    return output


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def generate(output: Path, stage: str, as_of: datetime, horizon_days: int, fixture_ids: List[str] | None = None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    selected = fixture_ids or list(FIXTURES)
    unknown = sorted(set(selected) - set(FIXTURES))
    if unknown:
        raise ValueError(f"Unknown UX fixtures: {', '.join(unknown)}")
    reports: Dict[str, Dict[str, str]] = defaultdict(dict)
    metrics: Dict[str, Dict[str, object]] = defaultdict(dict)
    summaries: Dict[str, object] = {}
    methodology_versions = set()

    for profile_id in selected:
        fixture = FIXTURES[profile_id]
        profile_dir = output / profile_id
        profile_dir.mkdir(exist_ok=True)
        birth = fixture["birth"]
        localization = fixture["localization"]
        core_result = None
        for depth in ("executive", "deep", "technical"):
            result = analyse_birth_chart(
                birth,
                localization,
                report_depth=depth,
                include_timing=True,
                as_of=as_of,
                horizon_days=horizon_days,
            )
            if core_result is None:
                core_result = result
            report = str(result["report"])
            reports[profile_id][depth] = report
            metrics[profile_id][depth] = report_metrics(report)
            (profile_dir / f"{depth}.md").write_text(report + "\n", encoding="utf-8")
            methodology_versions.add(str(result["chart"]["methodology_version"]))
        assert core_result is not None
        summaries[profile_id] = {
            "reader_profile_audit_only": fixture["reader_profile"],
            "birth_input": primitive(birth),
            "localization_input": primitive(localization),
            "chart_identity": {
                "utc_datetime": core_result["chart"]["utc_datetime"],
                "methodology_version": core_result["chart"]["methodology_version"],
                "backend": core_result["chart"]["backend"],
            },
            "themes": core_result["themes"],
            "paradoxes": core_result["paradoxes"],
            "current_phase": core_result["timing"]["current_phase"],
            "reasoned_synthesis": core_result["reasoned_synthesis"],
            "narrative_plan": core_result["narrative_plan"],
        }
        (profile_dir / "structured_summary.json").write_text(
            json.dumps(summaries[profile_id], ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        bundle = "\n\n---\n\n".join(reports[profile_id][depth] for depth in ("executive", "deep", "technical"))
        (profile_dir / "complete_bundle.md").write_text(bundle + "\n", encoding="utf-8")
        metrics[profile_id]["full_client_path"] = report_metrics(reports[profile_id]["deep"] + "\n\n" + reports[profile_id]["technical"])
        metrics[profile_id]["all_artifacts"] = report_metrics("\n\n".join(reports[profile_id].values()))

    skill_root = Path(__file__).resolve().parents[1]
    report_source = skill_root / "astrology" / "report.py"
    manifest = {
        "stage": stage,
        "generated_at_protocol_date": as_of.isoformat(),
        "horizon_days": horizon_days,
        "methodology_versions": sorted(methodology_versions),
        "report_renderer_sha256": file_sha256(report_source),
        "word_page_assumption": WORDS_PER_PAGE,
        "reading_speed_wpm": WORDS_PER_MINUTE,
        "fixtures": {profile_id: {"reader_profile_audit_only": FIXTURES[profile_id]["reader_profile"], "birth": primitive(FIXTURES[profile_id]["birth"]), "localization": primitive(FIXTURES[profile_id]["localization"])} for profile_id in selected},
        "guardrail": "Reader profiles were not passed to analyse_birth_chart; only birth and LocalizationProfile were used.",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "cross_report_reuse.json").write_text(json.dumps(cross_report_reuse(reports), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "individuality_metrics.json").write_text(json.dumps(individuality_metrics(reports), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _premium_domain_metrics(
    report: str, manifest: Dict[str, object],
    premium_contract_version: str = PREMIUM_HANDOFF_CONTRACT_VERSION,
) -> Dict[str, object]:
    """Measure the exact publication parser universe; never regenerate a chart."""
    if premium_contract_version == LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION:
        parsed = _parse_premium_narrative_v13(report, manifest)
    elif premium_contract_version == PREMIUM_HANDOFF_CONTRACT_VERSION:
        parsed = _parse_premium_narrative(report, manifest)
    else:
        raise ValueError(f"Unsupported Premium contract version for audit: {premium_contract_version}")
    if parsed.get("errors"):
        raise ValueError("Invalid published Premium narrative: " + ", ".join(parsed["errors"]))
    domains = []
    available_counts = []
    layout_signatures: Dict[str, int] = defaultdict(int)
    for domain in manifest.get("domains", []):
        domain_id = str(domain["id"])
        blocks = parsed["sections"][domain_id]["prose"]
        subheadings = parsed["sections"][domain_id].get("subheadings", [])
        count = sum(len(words(str(block["text"]))) for block in blocks)
        paragraphs = sum(block.get("kind", "paragraph") == "paragraph" for block in blocks)
        list_items = sum(block.get("kind") == "list_item" for block in blocks)
        h3_count = len(subheadings)
        if premium_contract_version == PREMIUM_HANDOFF_CONTRACT_VERSION:
            # ``authored`` is already the physical order, so merge the H3
            # marker back in rather than sorting by kind.
            sequence = [
                "P" if block.get("kind", "paragraph") == "paragraph" else "L" if block.get("kind") == "list_item" else "H3"
                for block in parsed["sections"][domain_id].get("authored", blocks)
            ]
        else:
            sequence = ["P"] * paragraphs
        signature = "-".join(sequence) if sequence else "EMPTY"
        if domain.get("availability") == "available":
            layout_signatures[signature] += 1
        domains.append({
            "domain_id": domain_id,
            "available": domain.get("availability") == "available",
            "words": count,
            "paragraphs": paragraphs,
            "list_items": list_items,
            "coverage_eligible_blocks": paragraphs + list_items,
            "subheadings": h3_count,
            "subheading_words": sum(len(words(str(block["text"]))) for block in subheadings),
            "layout_signature": signature,
        })
        if domain.get("availability") == "available":
            available_counts.append(count)
    domain_median = median(available_counts) if available_counts else 0
    paragraph_frequency: Dict[int, int] = defaultdict(int)
    for item in domains:
        if item["available"]:
            paragraph_frequency[int(item["paragraphs"])] += 1
    same_paragraph_share = max(paragraph_frequency.values(), default=0) / len(available_counts) if available_counts else 0.0
    same_layout_share = max(layout_signatures.values(), default=0) / len(available_counts) if available_counts else 0.0
    active = next((item for item in domains if item["domain_id"] == "active_life_chapter"), {"words": 0})
    prose_total = sum(item["words"] for item in domains)
    h3_total = sum(int(item["subheadings"]) for item in domains)
    return {
        "premium_contract_version": premium_contract_version,
        "canonical_domains": domains,
        "available_domain_word_minimum": min(available_counts, default=0),
        "available_domain_word_median": domain_median,
        "available_domain_word_maximum": max(available_counts, default=0),
        "available_domain_largest_to_median_ratio": round(max(available_counts, default=0) / domain_median, 3) if domain_median else 0.0,
        "maximum_same_paragraph_count_share": round(same_paragraph_share, 3),
        "layout_signature_frequency": dict(sorted(layout_signatures.items())),
        "maximum_same_layout_signature_share": round(same_layout_share, 3),
        "domains_with_subheadings": h3_total,
        "opening_words": sum(len(words(str(item["text"]))) for item in parsed["sections"]["opening"]["prose"]),
        "integration_words": sum(len(words(str(item["text"]))) for item in parsed["sections"]["integration"]["prose"]),
        "active_life_timing_share_of_domain_prose": round(int(active["words"]) / prose_total, 3) if prose_total else 0.0,
    }


def generate_premium_artifacts(output: Path, stage: str, run_dirs: List[Path]) -> None:
    """Audit already-approved Premium runs without generating reading content."""
    output.mkdir(parents=True, exist_ok=True)
    reports: Dict[str, str] = {}
    metrics: Dict[str, Dict[str, object]] = {}
    for run_dir in run_dirs:
        provenance_path = run_dir / "05-provenance-guard.json"
        publication_path = run_dir / "08-publication-guard.json"
        if not provenance_path.is_file() or not publication_path.is_file():
            raise ValueError(f"Premium artifact run requires 05-provenance-guard.json and 08-publication-guard.json: {run_dir}")
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        publication = json.loads(publication_path.read_text(encoding="utf-8"))
        if not provenance.get("approved") or not publication.get("approved"):
            raise ValueError(f"Premium artifact run is not approved by both guards: {run_dir}")
        report = publication.get("report")
        manifest = provenance.get("reader_domain_manifest")
        if not isinstance(report, str) or not isinstance(manifest, dict):
            raise ValueError(f"Premium artifact run lacks final report or canonical manifest: {run_dir}")
        premium_contract_version = provenance.get("premium_handoff_contract_version")
        if premium_contract_version not in {LEGACY_PREMIUM_HANDOFF_CONTRACT_VERSION, PREMIUM_HANDOFF_CONTRACT_VERSION}:
            raise ValueError(f"Premium artifact run lacks a supported handoff contract version: {run_dir}")
        publication_version = publication.get("premium_handoff_contract_version")
        if publication_version is not None and publication_version != premium_contract_version:
            raise ValueError(f"Premium artifact run has mixed contract versions: {run_dir}")
        run_id = run_dir.name
        if run_id in reports:
            raise ValueError(f"Duplicate Premium artifact run id: {run_id}")
        reports[run_id] = report
        metrics[run_id] = {
            **report_metrics(report),
            "premium_canonical": _premium_domain_metrics(report, manifest, str(premium_contract_version)),
        }
    output_manifest = {
        "stage": stage,
        "mode": "premium_artifacts",
        "runs": [str(path) for path in run_dirs],
        "guardrail": "Metrics read approved publication artifacts and their provenance manifests; this mode never regenerates charts or labels deterministic fallback output Premium.",
    }
    (output / "manifest.json").write_text(json.dumps(output_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "cross_report_reuse.json").write_text(json.dumps({"premium": exact_reuse(reports)}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "individuality_metrics.json").write_text(json.dumps({
        "premium": {
            "exact_interpretive_sentence_reuse": exact_reuse(reports),
            "semantic_cross_report_similarity": semantic_cross_report_similarity(reports),
            "report_swap_pre_screen": report_swap_risk(reports),
            "llm_semantic_review_prompt": llm_semantic_review_prompt(),
        },
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--stage", required=True, choices=("before", "after"))
    parser.add_argument("--horizon-days", type=int, default=366)
    parser.add_argument("--fixtures", help="Comma-separated fixture ids; allows bounded CI/audit batches.")
    parser.add_argument("--premium-artifacts", type=Path, nargs="+", help="Approved Premium run directories; incompatible with --fixtures.")
    args = parser.parse_args()
    if args.premium_artifacts and args.fixtures:
        parser.error("--premium-artifacts is incompatible with --fixtures")
    if args.premium_artifacts:
        generate_premium_artifacts(args.output, args.stage, args.premium_artifacts)
        return
    fixture_ids = [item.strip() for item in args.fixtures.split(",") if item.strip()] if args.fixtures else None
    generate(args.output, args.stage, AS_OF, args.horizon_days, fixture_ids)


if __name__ == "__main__":
    main()
