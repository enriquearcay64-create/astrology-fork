"""Cheap deterministic editorial QA; flags are review prompts, not verdicts."""
from __future__ import annotations

import re
from itertools import combinations
from typing import Dict, Iterable, List


STOPWORDS = frozenset("a an and are as at be because but by can com como de da das do dos e em esta este for from have i if in is it na no not o of on or os para por que se the this to um uma você you your seu sua seus suas".split())
FIXED_SENTENCE_MARKERS = (
    "leitura simbólica", "symbolic reading", "não diagnostica", "does not diagnose", "technical appendix", "apêndice técnico", "**percurso:**", "**path:**",
    # Structural navigation belongs to the report shell, not interpretive prose.
    "elas mostram onde os temas do mapa encontram contextos mais concretos",
    "they show where chart themes meet more concrete contexts",
    "ela é formada pelas janelas calculadas abaixo, não por uma década genérica",
    "it is formed from the calculated windows below, not a generic decade",
)
BROAD_PATTERNS = (
    r"\b(?:você|you) (?:é|are) (?:forte|strong|sens[ií]vel|sensitive)\b",
    r"\b(?:você|you) (?:sente|feel(?:s)?) profundamente\b",
    r"\b(?:você|you) (?:valoriza|value(?:s)?) (?:a )?(?:liberdade|freedom)\b",
    r"\b(?:às vezes|sometimes) (?:você|you)\b",
)


def sentences(text: str) -> List[str]:
    plain = re.sub(r"```.*?```|<details.*?</details>", " ", text, flags=re.S | re.I)
    plain = re.sub(r"^#{1,6}.*$|^[-*].*$|^\|.*\|$", " ", plain, flags=re.M)
    return [re.sub(r"\s+", " ", sentence).strip() for sentence in re.split(r"(?<=[.!?])\s+", plain) if len(tokens(sentence)) >= 7]


def tokens(text: str) -> set[str]:
    return {word.casefold() for word in re.findall(r"[^\W\d_]+", text, flags=re.UNICODE) if len(word) > 2 and word.casefold() not in STOPWORDS}


def interpretive_sentences(text: str) -> List[str]:
    return [sentence for sentence in sentences(text) if not any(marker in sentence.casefold() for marker in FIXED_SENTENCE_MARKERS)]


def similarity(left: str, right: str) -> float:
    left_tokens, right_tokens = tokens(left), tokens(right)
    union = left_tokens | right_tokens
    return len(left_tokens & right_tokens) / len(union) if union else 0.0


def exact_reuse(reports: Dict[str, str]) -> List[Dict[str, object]]:
    index: Dict[str, Dict[str, object]] = {}
    for report_id, text in reports.items():
        for sentence in interpretive_sentences(text):
            normalized = " ".join(sorted(tokens(sentence)))
            if len(tokens(sentence)) < 6:
                continue
            item = index.setdefault(normalized, {"sentence": sentence, "reports": []})
            if report_id not in item["reports"]:
                item["reports"].append(report_id)
    return [item for item in index.values() if len(item["reports"]) > 1]


def semantic_cross_report_similarity(reports: Dict[str, str], threshold: float = 0.58) -> Dict[str, object]:
    pairs = []
    per_pair = {}
    for left_id, right_id in combinations(sorted(reports), 2):
        left, right = interpretive_sentences(reports[left_id]), interpretive_sentences(reports[right_id])
        matches = []
        for sentence in left:
            if not right:
                continue
            candidate, score = max(((other, similarity(sentence, other)) for other in right), key=lambda item: item[1])
            if score >= threshold:
                matches.append({"similarity": round(score, 3), "left": sentence, "right": candidate})
        mean_max = sum(item["similarity"] for item in matches) / len(left) if left else 0.0
        per_pair[f"{left_id}-{right_id}"] = {"mean_matched_similarity": round(mean_max, 3), "interchangeable_sentence_count": len(matches), "matches": matches[:20]}
        pairs.extend(matches)
    return {"method": "token-overlap heuristic; use the LLM evaluator prompt for semantic review", "threshold": threshold, "pairwise": per_pair, "interchangeable_sentence_count": len(pairs)}


def barnum_risk(text: str) -> Dict[str, object]:
    source = interpretive_sentences(text)
    flagged = [sentence for sentence in source if any(re.search(pattern, sentence, re.I) for pattern in BROAD_PATTERNS)]
    return {
        "method": "broad-phrase lint only; a human/LLM reviewer must judge context",
        "flagged_sentences": flagged,
        "share": round(len(flagged) / len(source), 3) if source else 0.0,
    }


def report_swap_risk(reports: Dict[str, str]) -> Dict[str, object]:
    """Heuristic pre-screen for a blind swap test; never a validity claim."""
    similarity_data = semantic_cross_report_similarity(reports)
    candidates = []
    for pair, data in similarity_data["pairwise"].items():
        if data["interchangeable_sentence_count"]:
            candidates.append({"pair": pair, "risk": "review", "count": data["interchangeable_sentence_count"]})
    return {
        "status": "heuristic_pre_screen",
        "pairs_requiring_blind_review": candidates,
        "limit": "A genuine report-swap discrimination test requires independent human readers and identical localization across decoys.",
    }


def llm_semantic_review_prompt() -> str:
    return (
        "Compare only interpretive prose from anonymous reports with localization removed. For each paragraph ask: could it be moved to a decoy chart without materially reducing plausibility? Mark semantic reuse, Barnum risk, unsupported specificity, and whether a conclusion follows the cited ReasonedSynthesis factors. Do not treat agreement as proof of astrology."
    )
