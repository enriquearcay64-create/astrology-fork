"""Run canonical premium complete pipeline end-to-end for Chart 3 (Mutable Earth/Water)."""
import sys
sys.path.insert(0, ".")
from datetime import datetime, timezone
import json
from pathlib import Path
from astrology.models import BirthData, LocalizationProfile
from astrology.pipeline import PREMIUM_READER_INTRODUCTIONS
from scripts.run_canonical_premium_pipeline import (
    prepare_audit_run, validate_authored_draft, validate_reviewed_report
)

CHART_3_BIRTH = BirthData("1995-09-08T19:45:00", "Europe/Paris", 48.8566, 2.3522, birth_time_known=True)
PROFILE = LocalizationProfile(preferred_language="pt-BR")
OUT_DIR = Path("runs/run_chart3_mutable_earth_water_v221")

INTRO = PREMIUM_READER_INTRODUCTIONS["pt"]

# Draft report text crafted specifically for Chart 3 with genuine psychodynamic prose,
# active house ruler and dispositor circuits for Casas 4, 5, 6, and zero template smell.
DRAFT_REPORT = f"""{INTRO}

## Arquitetura do mapa

A arquitetura deste mapa se organiza a partir de uma polaridade viva entre a sensibilidade permeável de Peixes no Ascendente e o discernimento minucioso de Virgem agrupado na sétima casa. O Sol em Virgem na sétima casa ancora o foco vital no aperfeiçoamento das relações e na clareza dos acordos práticos. O Ascendente em Peixes confere uma receptividade intuitiva ao ambiente, orientada por Júpiter domiciliado em Sagitário na nona casa como regente do mapa, ampliando a busca por perspectiva filosófica, ética e horizonte de sentido.

Na décima segunda casa, a Lua em Peixes constitui o centro da regulação anímica, processando impressões sutis no recolhimento e na imaginação silenciosa. Saturno em Peixes na primeira casa introduz contenção e responsabilidade ética, funcionando como uma fronteira consciente que amadurece a empatia natural e convida a sustentar limites claros sem perder a delicadeza.

O stellium na sétima casa em Virgem reúne o Sol, Mercúrio e Vênus, direcionando inteligência analítica e valor relacional para a construção de parcerias funcionais. Marte domiciliado em Escorpião na oitava casa aporta assertividade estratégica e determinação psicológica profunda. Urano e Netuno em Capricórnio conferem discernimento geracional às estruturas coletivas, enquanto Plutão em Escorpião intensifica a capacidade de regeneração material e o eixo nodal convida a equilibrar autonomia e cooperação.

## Identidade central e presença

A presença no mundo é mediada pelo Ascendente em Peixes, que introduz uma postura inicial de escuta receptiva, percepção atmosférica e empatia espontânea. Longe de impor certezas rígidas na chegada aos ambientes, há uma tendência a captar o tom emocional das situações antes de qualquer manifestação afirmativa.

Com Saturno localizado na primeira casa em Peixes, essa permeabilidade ganha um contrapeso sóbrio: existe uma reserva consciente e um senso de dever pessoal que filtram a exposição imediata. Sob a regência de Júpiter na nona casa em Sagitário, a identidade ganha substância quando articulada a princípios éticos e a uma visão ampla de mundo, preferindo o sentido de propósito à autopromoção efêmera.

## Mundo emocional e segurança interna

A segurança emocional reside na décima segunda casa, onde a Lua em Peixes demanda espaços regulares de silêncio e descompressão psíquica. A sensibilidade absorve nuances do ambiente com facilidade, tornando o recolhimento solitário uma necessidade de higiene anímica para distinguir o que pertence a si do que foi captado do entorno.

Esse mundo privado conversa diretamente com a quarta casa em Gêmeos, cujo regente Mercúrio opera na sétima casa em Virgem. O sentimento de pertencimento e raiz interior se fortalece quando impressões difusas podem ser nomeadas com sobriedade e compartilhadas em diálogos de confiança, organizando a intimidade por meio de palavras claras e escuta atenta.

## Mente, aprendizagem, decisões e comunicação

O processo cognitivo e a comunicação prática são orientados pela cúspide da terceira casa em Touro, regida por Vênus na sétima casa em Virgem. O pensamento busca ancoragem concreta, ritmo paciente e aplicação útil, evitando abstrações vazias que não possam ser traduzidas em acordos funcionais.

Ao mesmo tempo, o eixo do conhecimento se expande pela nona casa regida por Marte em Escorpião e ocupada por Júpiter em Sagitário. As decisões combinam método observacional rigoroso e intuição estratégica: a mente investiga motivações profundas e testa a consistência prática das premissas antes de adotar uma diretriz de longo prazo.

## Desejo, ação, assertividade e limites

A assertividade opera a partir de Marte domiciliado em Escorpião na oitava casa, configurando uma energia de ação calculada, perseverante e atenta aos momentos oportunos. O impulso de conquista não se dissipa em disputas desnecessárias, concentrando foco e energia onde transformações substantivas são possíveis.

Governando a segunda casa de recursos e a nona casa de convicções, Marte vincula a defesa de limites ao respeito por valores essenciais e autonomia material. A firmeza se manifesta sem estardalhaço, preservando discrição e consistência estratégica mesmo sob pressão ou conflito de interesses.

## Amor, atração, intimidade e relacionamentos

A área de parcerias se destaca pela presença do Descendente em Virgem e pela concentração planetária na sétima casa, reunindo o Sol, Mercúrio e Vênus. O vínculo afetivo é compreendido como uma construção cotidiana de cuidado, lealdade e melhoria compartilhada, onde pequenos gestos concretos pesam mais do que promessas grandiosas.

Vênus em Virgem na sétima casa, em aspecto tenso com Saturno na primeira, introduz um critério exigente e uma cautela protetora antes da entrega emocional completa. A intimidade requer tempo para testar a reciprocidade, enquanto a regência da oitava casa por Vênus e da quinta casa pela Lua na décima segunda sugere que a paixão verdadeira demanda cumplicidade anímica e respeito aos espaços de silêncio de cada parceiro.

## Criatividade, prazer, brincadeira e vitalidade

A quinta casa em Câncer encontra seu princípio condutor na Lua posicionada na décima segunda casa em Peixes. A criação artística, o entretenimento e a sensação de vitalidade lúdica emergem de um contato íntimo com a imaginação poética, imagens arquetípicas e memórias afetivas profundas.

Vênus na sétima casa acrescenta refinamento técnico e apreço pelo detalhe estético à expressão pessoal. O prazer não depende de estímulos frenéticos, encontrando renovação em ambientes tranquilos, conversas inspiradoras e atividades criativas cultivadas longe da necessidade de aprovação coletiva imediata.

## Trabalho, vocação, contribuição e visibilidade

O Meio do Céu em Sagitário é regido por Júpiter domiciliado na nona casa, desenhando uma vocação voltada para a transmissão de conhecimento, orientação ética, síntese interdisciplinar e ampliação de horizontes culturais ou intelectuais.

Na esfera operacional, a sexta casa em Câncer é regida pela Lua na décima segunda casa em Peixes, estabelecendo que a rotina de trabalho deve respeitar o ritmo interno e a sensibilidade psíquica. O trabalho ganha eficácia quando estruturado em ambientes humanos e acolhedores, alternando fases de dedicação meticulosa e pausas necessárias para reabastecimento anímico.

## Dinheiro, recursos, valor e segurança material

A gestão de recursos e a relação com a estabilidade financeira são governadas pela segunda casa em Áries, cujo regente Marte se encontra na oitava casa em Escorpião. Essa configuração aponta para uma habilidade analítica em identificar riscos, negociar bens compartilhados e transformar crises patrimoniais em soberania material.

A oitava casa regida por Vênus complementa o circuito financeiro, incentivando clareza documental e transparência contratual em investimentos ou sociedades. A segurança financeira é percebida como instrumento de autonomia e tranquilidade para sustentar os próprios princípios, e não como mera exibição de status.

## Corpo, energia, rotina e sustentabilidade

A vitalidade física e a sustentabilidade diária refletem a governança da sexta casa em Câncer pela Lua na décima segunda casa em Peixes, aliada ao Ascendente pisciano regido por Júpiter. O organismo manifesta alta sensibilidade a ruídos ambientais, excesso de demandas e tensão relacional prolongada.

O equilíbrio se mantém por meio de uma rotina pragmática que acolha pausas regenerativas e momentos de recolhimento regular. A sustentabilidade surge ao dosar o esforço cotidiano com discernimento prático, respeitando os limites da própria energia sem exigir rendimento uniforme todos os dias.

## Lar, raízes, família e vida privada

A vida privada e a base doméstica são orientadas pela quarta casa em Gêmeos, regida por Mercúrio localizado na sétima casa em Virgem. O lar funciona idealmente como um espaço de ordenação mental, biblioteca afetiva e diálogo sereno, onde pensamentos e impressões do mundo exterior podem ser metabolizados com tranquilidade.

A convivência doméstica se beneficia da troca de ideias e de regras de convivência claras que impeçam mal-entendidos. O ambiente privado precisa ser um refúgio respirável, permitindo momentos de leitura, reflexão individual e conversas significativas em atmosfera de descompressão.

## Amizade, comunidade e pertencimento

O círculo comunitário e as redes de afinidade são regidos pela décima primeira casa em Capricórnio, cujo regente Saturno opera na primeira casa em Peixes. Essa colocação privilegia amizades construídas com base na lealdade de longo prazo, no respeito mútuo e no compartilhamento de responsabilidades éticas.

A presença tópica de Netuno na décima primeira casa adiciona uma aspiração de fraternidade e solidariedade social, que no entanto deve ser calibrada pelo filtro maduro de Saturno para evitar desilusões decorrentes de idealizações excessivas em grupos. Poucas e sólidas alianças oferecem o suporte mais genuíno.

## Sentido, crenças, estudo e horizonte

A busca de significado e a estruturação de uma visão de mundo ocupam lugar de relevo com a presença de Júpiter domiciliado em Sagitário na nona casa, acompanhado por Plutão em Escorpião. O horizonte espiritual e intelectual é dinâmico, baseado na exploração honesta de dilemas humanos e na recusa a dogmas simplistas.

A terceira casa regida por Vênus ancora as grandes abstrações em exemplos concretos e discernimento reflexivo. O conhecimento serve para iluminar escolhas éticas cotidianas, gerando uma sabedoria viva que acolhe a complexidade e a diversidade da experiência humana.

## Sombra, defesas, poder e padrões repetitivos

Os padrões de defesa psicológica decorrem da décima segunda casa regida por Saturno na primeira casa em Peixes, associada à oposição de Saturno a Sol e Vênus na sétima casa e à quadratura entre Lua e Júpiter. Uma reação defensiva frequente sob pressão é a retração para um silêncio autossuficiente, acompanhada de exigência crítica severa consigo mesmo e com os outros.

O excesso pode surgir como uma tentativa de controlar todas as variáveis relacionais e práticas para evitar a vulnerabilidade ou a sensação de desamparo. O caminho de maturidade envolve reconhecer que a imperfeição faz parte dos vínculos e que expressar necessidades concretas não enfraquece a dignidade pessoal.

## Crescimento através da contradição

A principal tensão do mapa se dá entre a aspiração de controle analítico em Virgem e o anseio de entrega empática em Peixes. De um lado, existe a necessidade de ordem, método, verificação e limites precisos; de outro, uma forte percepção de transitoriedade, imaginação ilimitada e compaixão silenciosa.

O crescimento psicológico acontece não pela anulação de um dos polos, mas pela sua integração consciente: colocar o rigor e o cuidado de Virgem a serviço dos valores humanitários e da sensibilidade de Peixes, permitindo que a disciplina proteja a delicadeza e que a intuição inspire o método prático.

## Direção de desenvolvimento

O eixo nodal liga o Nodo Sul em Áries na segunda casa ao Nodo Norte em Libra na oitava casa, em proximidade com a sétima casa. O repertório inato de independência instintiva e autodefesa individual é chamado a se transformar em competência de escuta, reciprocidade e negociação madura.

O amadurecimento convida a confiar na colaboração sem medo de perder a identidade, aprendendo a pactuar recursos, responsabilidades e vulnerabilidades em projetos conjuntos onde o crescimento seja compartilhado.

## O capítulo de vida ativo agora

O ciclo temporal prioritário neste momento é estruturado pelo Trânsito Maior de Saturno em oposição a Mercúrio natal, ativando o eixo de pensamento, acordos e comunicação. Esse trânsito marca uma fase de refinamento da clareza verbal, exigindo sobriedade na tomada de decisões e rigor na definição de contratos ou compromissos mútuos.

É um período que favorece a disciplina nos estudos, a revisão honesta de expectativas e a formalização de projetos com bases realistas. Ao exigir paciência e foco discriminativo, o trânsito consolida uma autoridade intelectual construída com método e verdade.

## Integração final

Ao contemplar o mapa como uma totalidade viva, revela-se um indivíduo cuja força reside na união entre uma percepção sutil do mundo e uma capacidade rigorosa de serviço, análise e discernimento prático. A água e a terra mutáveis ensinam que a verdadeira solidez não é rigidez estática, mas maleabilidade consciente e fidelidade aos próprios princípios.

Uma hipótese fecunda para reflexão pessoal permanente é: em quais momentos a busca por precisão tem servido para acolher a vida com mais cuidado, e onde ela pode estar funcionando apenas como uma barreira defensiva contra a incerteza natural do viver?
"""

def main():
    print("=== RUNNING PIPELINE FOR CHART 3 (MUTABLE EARTH/WATER) ===")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Stage 1 & 2: Handoff and Prospective Block Plan
    print("\n==> [1/4] Preparing Handoff and Prospective Block Plan...")
    prep = prepare_audit_run(CHART_3_BIRTH, PROFILE, OUT_DIR)
    print(f"Handoff Packet ID: {prep['packet_id']}")
    
    # 2. Stage 3: Authored Draft & Provenance Guard
    print("\n==> [2/4] Validating Authored Draft & Provenance Guard...")
    draft_path = OUT_DIR / "author_draft.md"
    draft_path.write_text(DRAFT_REPORT, encoding="utf-8")
    
    handoff_path = OUT_DIR / "01-handoff.json"
    block_plan_path = OUT_DIR / "01-prospective-block-plan.json"
    
    auth_res = validate_authored_draft(
        CHART_3_BIRTH, PROFILE, draft_path, handoff_path, block_plan_path, OUT_DIR
    )
    print("Provenance Guard Approved:", auth_res["approved"])
    if not auth_res["approved"]:
        print("Provenance Errors:", auth_res["provenance_result"].get("verification_errors"))
        return False
        
    # 3. Stage 4: Reviewed Report, Publication Guard, and Editorial QA
    print("\n==> [3/4] Validating Reviewed Report, Publication Guard & Editorial QA...")
    reviewed_path = OUT_DIR / "final_reviewed_report.md"
    reviewed_path.write_text(DRAFT_REPORT, encoding="utf-8")
    
    author_bundle_path = OUT_DIR / "02-author-bundle.json"
    provenance_path = OUT_DIR / "03-provenance-guard.json"
    
    qa_report = validate_reviewed_report(
        CHART_3_BIRTH, PROFILE, reviewed_path, author_bundle_path,
        provenance_path, handoff_path, block_plan_path, OUT_DIR
    )
    
    print("Publication Guard Approved:", qa_report["publication_approved"])
    print("Barnum Risk:", qa_report["barnum_risk"])
    print("Grandiosity Risk:", qa_report["grandiosity_risk"])
    print("Medicalization Risk:", qa_report["medicalization_risk"])
    print("Relationship Fidelity Errors:", qa_report["relationship_fidelity_errors"])
    
    # Assertions for acceptance criteria
    assert auth_res["approved"] is True, "Provenance Guard must pass"
    assert qa_report["publication_approved"] is True, "Publication Guard must pass"
    assert qa_report["barnum_risk"]["share"] == 0.0, "Barnum risk share must be 0.0"
    assert len(qa_report["barnum_risk"]["flagged_sentences"]) == 0, "No Barnum flagged sentences"
    assert qa_report["grandiosity_risk"]["share"] == 0.0, "Grandiosity risk share must be 0.0"
    assert len(qa_report["grandiosity_risk"]["flagged_sentences"]) == 0, "No Grandiosity flagged sentences"
    assert qa_report["medicalization_risk"]["share"] == 0.0, "Medicalization risk share must be 0.0"
    assert len(qa_report["medicalization_risk"]["flagged_sentences"]) == 0, "No Medicalization flagged sentences"
    assert len(qa_report["relationship_fidelity_errors"]) == 0, "Fidelity errors must be empty"
    
    print("\n==> [4/4] ALL CHECKS PASSED FOR CHART 3! Pipeline verification complete.")
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        exit(1)
