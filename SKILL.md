---
name: interpretar-mapa-astrologico
description: Calcular fatos astrológicos determinísticos e produzir leituras natais, trânsitos, profecções, progressões, arcos solares, Revoluções Solares e timelines com síntese holística rastreável, Signo Inteiro + Placidus e relatórios humanos em português ou inglês. Use quando o usuário pedir leitura de mapa, fases de vida, ciclos, previsão astrológica condicionada, relatório natal, consulta sobre uma pergunta de vida ou comparação técnica entre casas/ângulos.
---

# Astrologia avançada e rastreável

Use este skill como leitura simbólica e reflexiva. A precisão prometida é astronômica e metodológica; não declare validação científica de personalidade ou previsão de eventos.

## Dados necessários

Exigir data local, fuso IANA, latitude e longitude. Para o relatório **premium beta**, exigir hora local ISO conhecida: casas, ângulos e timing tópico são parte da promessa editorial. Quando a hora for desconhecida, aceitar `birth_time_known: false` apenas para a leitura determinística limitada a fatores que sobrevivam à análise do dia inteiro. Aceitar perfil de localização somente se fornecido pela pessoa. Não inferir cultura, país atual ou psicologia pelo local de nascimento.

Leia [references/input-schema.md](references/input-schema.md) antes de preparar a entrada. Para regras interpretativas, leia [references/methodology.md](references/methodology.md). Antes de apresentar o resultado, leia [references/report-design.md](references/report-design.md). Para licença e dependências, leia [references/dependencies.md](references/dependencies.md).

## Fluxo obrigatório

1. Rodar o núcleo determinístico; nunca calcular manualmente posições, casas, aspectos, orbes, Lots ou timing.
2. Construir `SafeInterpretiveChart` e aplicar gates de qualidade antes de qualquer interpretação. Casa, ângulo, Lot, profecção ou regente tópico instável não pode chegar à síntese como fato.
3. Construir Claims/motifs autorizados, `ReasonedSynthesis`, `ChartSignature` e `NarrativePlanner` nessa ordem. A assinatura — não a lista de themes — governa seleção, abertura, ordem e áreas prioritárias.
4. Aplicar integralmente o [padrão interpretativo operacional](references/methodology.md#padrão-interpretativo-operacional--v4): selecionar e omitir, compor mecanismos, preservar ancestralidade/contradição, exigir relevância real de contrapesos e resistir ao swap.
5. No premium, o **Author High** cria uma única síntese holística e o rascunho a partir do packet fechado. Cada dedução cita 1–5 fatores existentes; exemplos são hipotéticos e não adicionam biografia. Nas dinâmicas centrais, normalmente parte de um padrão humano reconhecível quando isso ajuda e então revela a astrologia; não força essa ordem quando a estrutura técnica for mais clara. A voz é predominantemente direta em segunda pessoa natural, psicologicamente legível, íntima sem presumir biografia e sem tom acadêmico, jurídico ou de QA interno. Aspectos importantes podem ser nomeados com tradução imediata; timing só entra quando sustenta um campo humano específico.
6. Rodar o `Deterministic Provenance Guard`; ele verifica origem, permissões, operações, tetos, timing, hashes e cobertura por parágrafo, sem alegar prova semântica.
7. Fazer um passe separado de **Reviewer/Editor High**. Ele corrige diretamente relevância, contradições achatadas, Barnum, genericidade, repetição, jargão não traduzido, abstração tecnicamente correta, achatamento emocional, cautela excessiva, coaching antes da interpretação e deriva semântica; remove timing ou desenvolvimento que não justifique espaço leitor. Só bloqueia quando falta dado ou evidência não corrigível editorialmente.
8. Rodar o `Publication Guard` e publicar apenas a versão exata aprovada. Se houver fator, certeza, timing ou extensão não autorizada, reduzir especificidade ou regenerar.
9. Seguir [report-design.md](references/report-design.md) para divulgação progressiva e experiência do leitor. Localization altera somente apresentação; feedback contextualiza exemplos, nunca suporte astrológico. Timing descreve ativações, não eventos garantidos.

## Fluxo premium normal no Codex

Quando a pessoa pedir naturalmente “gere uma leitura premium” ou “faça o relatório natal completo”, faça todo o percurso sem expor operações intermediárias:

```text
núcleo determinístico → SafeInterpretiveChart → Premium Author High
→ Deterministic Provenance Guard → Premium Reviewer/Editor High
→ Publication Guard → relatório final
```

O Author só recebe o pacote factual autorizado e cria `author_bundle` com `packet_id`, `reasoned_syntheses`, rascunho e mapa de fontes por parágrafo. O Reviewer recebe o mínimo necessário, revisa como um leitor novo e entrega `reviewed_bundle` com o relatório final, correções, avisos e hashes. Em ambientes em que não houver contexto separado naturalmente, faça essa revisão como uma segunda fase deliberadamente independente no mesmo task. Python/CLI calculam e validam; o Codex com o modelo selecionado raciocina, escreve e revisa. Não usar API externa nem pedir trabalho adicional ao usuário.

## Fluxo premium manual (debug/auditoria)

O relatório local determinístico é fallback para testes e debug; não o apresente como produto premium. Para a leitura premium no Codex High, execute exatamente:

```bash
python3 scripts/astrology_skill.py /caminho/entrada.json --premium-stage prepare > pacote.json
# No Codex, o Author usa apenas o reasoning_packet para criar author-bundle.json.
python3 scripts/astrology_skill.py /caminho/entrada.json --premium-stage validate-synthesis --premium-synthesis author-bundle.json
# O Reviewer usa as sínteses aprovadas para criar reviewer-bundle.json e corrigir o rascunho diretamente.
python3 scripts/astrology_skill.py /caminho/entrada.json --premium-stage validate-narrative --premium-synthesis author-bundle.json --premium-narrative reviewer-bundle.json --format report
```

`validate-synthesis` é o **Deterministic Provenance Guard**: valida a origem de claims, motifs, fatores, operações e o teto de confiança; não produz nem aprova narrativa. `validate-narrative` é o **Publication Guard**: confirma identidade, hashes, cobertura por parágrafo, fontes e conteúdo proibido; a avaliação de significado, individualidade e fluidez é responsabilidade do Reviewer High. A CLI não chama API externa nem finge que um gate léxico é prova semântica.

## Executar

```bash
python3 scripts/astrology_skill.py /caminho/entrada.json --depth executive --as-of 2026-08-27T12:00:00Z
python3 scripts/astrology_skill.py /caminho/entrada.json --depth deep --horizon-days 1826
python3 scripts/astrology_skill.py /caminho/entrada.json --question "O que o mapa sugere sobre carreira?"
python3 scripts/astrology_skill.py /caminho/entrada.json --solar-return-year 2027
python3 scripts/astrology_skill.py /caminho/entrada.json --depth deep --format report
```

O JSON resultante contém payload técnico, claims, temas, timing e relatório. No Premium Complete, apresente a leitura e o apêndice técnico voltado ao cliente; conserve o audit sidecar, guards e demais registros internos para auditoria.

Bloquear ou reformular trauma, abuso, abandono, diagnóstico, morte, doença, gravidez, divórcio, falência e acontecimentos inevitáveis. Quando faltar suporte, declarar a lacuna em vez de improvisar.

## Recursos

- `scripts/astrology_skill.py`: interface local determinística.
- `astrology/`: núcleo de cálculo, semântica, timing, síntese, consulta e privacidade.
- `references/methodology.md`: políticas versionadas e limites.
- `references/report-design.md`: arquitetura visual e narrativa do relatório.
- `references/dependencies.md`: licença e revisão comercial.
- `references/licensing-notice.md`: gate obrigatório antes de distribuição.
- `references/qa.md`: gates, ablações e limites dos testes internos.
- `scripts/ux_editorial_audit.py`: fixtures A/B reprodutíveis, métricas editoriais e teste de reutilização entre relatórios.
- `astrology/safe_view.py`: gate arquitetural entre Chart bruto e interpretação.
- `astrology/reasoning.py`: pacote factual fechado, ReasonedSynthesis, planner e contrato de humanização.
- `astrology/editorial_qa.py`: lint de Barnum, reutilização literal/semântica e pré-teste de report swap.
