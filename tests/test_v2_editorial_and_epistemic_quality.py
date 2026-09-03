from __future__ import annotations

import pytest

from astrology.semantics import PAIR_RULES, PLANET_SHORT_FUNCTIONS
from astrology.reasoning import humanization_instructions, humanization_verifier_instructions
from astrology.editorial_qa import grandiosity_and_flattery_risk, medicalization_risk, barnum_risk


def test_planet_short_functions_clean_of_slashes():
    """Verify that all short functions in pt and en use natural connectives instead of slashes."""
    for lang in ("pt", "en"):
        for body, func in PLANET_SHORT_FUNCTIONS[lang].items():
            assert "/" not in func, f"Found slash token in {lang} function for {body}: {func}"


def test_baseline_pair_rules_preserved():
    """Verify that Fork V2 starts from the original baseline of 8 pair rules."""
    assert len(PAIR_RULES) == 8, f"Expected 8 baseline PAIR_RULES, found {len(PAIR_RULES)}"


def test_grandiosity_and_flattery_risk_detection():
    """Verify that grandiosity_and_flattery_risk detects heroic/flattering language and allows sober prose."""
    grand_text = (
        "Você possui uma intensidade vulcânica e uma autoridade penetrante no topo do mundo. "
        "O seu dom extraordinário é uma das configurações mais nobres que existem. "
        "A integridade que é sua marca natural revela uma vocação talhada para liderança excepcional e um destino grandioso. "
        "Você foi desenhado para triunfar e certamente superará tudo com seu brilhantismo natural."
    )
    result = grandiosity_and_flattery_risk(grand_text)
    assert result["share"] > 0.5
    assert len(result["flagged_sentences"]) >= 2

    sober_text = (
        "A configuração do Sol e Plutão sugere uma inclinação para posições de responsabilidade estratégica e gestão de processos complexos. "
        "Sob pressão, uma manifestação possível é o fechamento defensivo, enquanto a expressão mais integrada favorece a firmeza ética. "
        "Essa dinâmica pode ser observada na maneira como você lida com projetos de longo prazo."
    )
    sober_result = grandiosity_and_flattery_risk(sober_text)
    assert sober_result["share"] == 0.0
    assert len(sober_result["flagged_sentences"]) == 0


def test_grandiosity_adversarial_paraphrases():
    """Verify that expanded grandiosity pattern catches paraphrased heroic/flattering claims."""
    paraphrased = (
        "Essa posição confere uma força monumental e uma capacidade sobre-humana de liderança. "
        "O seu brilho incomparável e talento magistral revelam que você é predestinado a grandes feitos. "
        "O seu carisma irresistível e aura fascinante concedem um poder quase ilimitado sobre os outros."
    )
    result = grandiosity_and_flattery_risk(paraphrased)
    assert result["share"] > 0.5
    assert len(result["flagged_sentences"]) >= 2


def test_medicalization_risk_detection():
    """Verify that medicalization_risk detects physiological claims and allows symbolic health/routine prose."""
    medical_text = (
        "Essa quadratura causa problemas digestivos severos no seu sistema digestivo. "
        "A posição de Saturno indica uma exigência fisiológica de isolamento e promove uma regeneração celular acelerada. "
        "A sua resistência física excepcional cura doenças naturalmente."
    )
    result = medicalization_risk(medical_text)
    assert result["share"] > 0.5
    assert len(result["flagged_sentences"]) >= 2

    symbolic_text = (
        "A sexta casa em Câncer convida à observação atenta do ritmo diário e da relação entre o estado emocional e o descanso. "
        "Quando o ambiente de trabalho é acolhedor, a sustentabilidade da sua energia cotidiana tende a ser preservada com mais facilidade. "
        "O desafio reside em dosar a carga de trabalho e respeitar pausas regulares para recomposição."
    )
    sober_result = medicalization_risk(symbolic_text)
    assert sober_result["share"] == 0.0
    assert len(sober_result["flagged_sentences"]) == 0


def test_medicalization_adversarial_paraphrases():
    """Verify that expanded medicalization pattern catches paraphrased physiological claims."""
    paraphrased = (
        "Essa configuração gera uma suscetibilidade a enfermidades e predisposição a úlceras. "
        "O trânsito atual provoca esgotamento fisiológico e vulnerabilidade imunológica no organismo. "
        "O estresse contínuo gera comprometimento do metabolismo e estafa fisiológica."
    )
    result = medicalization_risk(paraphrased)
    assert result["share"] > 0.5
    assert len(result["flagged_sentences"]) >= 2


def test_author_and_reviewer_prompts_contain_v21_protections():
    """Verify that the V2.1 protections, micro-scenes mandate, and technical rules are codified."""
    author_pt = humanization_instructions("pt-BR")
    reviewer_pt = humanization_verifier_instructions("pt-BR")
    author_en = humanization_instructions("en")
    reviewer_en = humanization_verifier_instructions("en")

    # Author checks
    assert "Calibração Epistêmica" in author_pt
    assert "Anti-Grandiosidade" in author_pt
    assert "Não-Medicalização" in author_pt
    assert "Precisão Técnica" in author_pt
    assert "microcenas hipotéticas" in author_pt
    assert "Epistemic Calibration" in author_en
    assert "Anti-Grandiosity" in author_en
    assert "Non-Medicalization" in author_en
    assert "Technical Precision" in author_en
    assert "hypothetical micro-scenes" in author_en

    # Reviewer checks
    assert "grandiosidade" in reviewer_pt
    assert "bajulação" in reviewer_pt
    assert "certeza biográfica" in reviewer_pt
    assert "medicalização" in reviewer_pt
    assert "Tarefa editorial obrigatória" in reviewer_pt
    assert "grandiosity" in reviewer_en
    assert "flattery" in reviewer_en
    assert "medicalization" in reviewer_en
    assert "Mandatory editorial task" in reviewer_en
