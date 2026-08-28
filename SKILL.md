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

1. Rodar o núcleo determinístico, nunca calcular posições, casas, aspectos, orbes, Lots ou datas manualmente.
2. Validar qualidade de dados e os gates de estabilidade antes de interpretar aspectos, ângulos ou casas sensíveis. Aviso sem bloqueio não é suficiente.
3. Tratar Whole Sign como topologia temática e Placidus como análise espacial complementar. Usar os estados versionados de integração, nunca duplicar evidência quando a casa coincide nem escolher sistema depois de conhecer a biografia.
4. Usar ASC/DSC/MC/IC como análise independente. Não confundir angularidade com dignidade, facilidade ou saúde mental.
5. Construir primeiro a `SafeInterpretiveChart`; nunca entregar casa, ângulo, Lot, profecção ou regente tópico instável ao renderer ou à síntese como fato seguro. Diferenciar incerteza declarada de stress tests contrafactuais.
6. Usar o registry como limite semântico, não como roteiro de frases. Produzir `ReasonedSynthesis` a partir do pacote factual fechado: cada inferência emergente deve citar 1–5 fatores existentes, modificadores, contrapesos, leitura alternativa e teto de especificidade.
7. Permitir `derived_claim` em síntese de nível 2 quando o verificador confirmar fatores existentes, suporte adequado e ausência de extensão proibida. Não exigir que a frase final já exista no registry.
8. Antes de redigir, criar `ChartSignature` e `NarrativePlanner`: a assinatura — não a lista de themes — decide dinâmica central sustentada (ou centros distribuídos), ordem, referências cruzadas, áreas prioritárias, detalhes técnicos a ocultar e prevenção de repetição.
9. Aplicar `HumanizationPass` depois da síntese: variar ritmo, exemplos e transições; preservar significado e fatores citados; não acrescentar dado astrológico, biografia, certeza ou timing.
10. Para um pedido premium, executar internamente dois passes cognitivos: um **Premium Author** cria sínteses e rascunho; após o `Deterministic Provenance Guard`, um **Premium Reviewer/Editor** independente corrige diretamente o texto. O reviewer pode cortar, fundir, reordenar e reescrever; só bloqueia se faltar cálculo, dado ou evidência factual. Não expor esses estágios ao usuário nem pedir que ele mova JSON.
11. Executar o `Publication Guard` antes de apresentar o resultado: `packet_id`, hashes, fontes dos parágrafos, evidência de timing, fatores seguros e extensões proibidas precisam passar. O guard confirma integridade operacional; não é uma prova semântica automática.
12. Se a prosa introduzir um fator, uma extensão ou uma certeza não autorizada, reduzir especificidade ou regerar.
13. Distinguir predisposição simbólica, capacidade e manifestação. Feedback do usuário pode contextualizar exemplos, mas nunca altera suporte astrológico ou escolhe sistema de casas.
14. Aplicar Localization somente depois da síntese. Ela só pode alterar linguagem, exemplos, unidades, referências e formato; nunca inferir psicologia da cultura.
15. Ao falar de timing, separar stream tradicional e moderno; usar `activation_instance` para passagens do mesmo ciclo e nunca fundir recorrências distantes pelo mesmo nome de aspecto. Não prometer eventos.
16. Aplicar divulgação progressiva e equilíbrio Logos–Eros: arquitetura humana primeiro; 3–4 temas centrais quando sustentados, sem quota fixa; quatro áreas concretas; timing natal antes do jargão; intervalos emergentes antes de décadas; detalhes técnicos no apêndice; síntese diferente da abertura e com experimento observável.

## Fluxo premium normal no Codex

Quando a pessoa pedir naturalmente “gere uma leitura premium” ou “faça o relatório natal completo”, faça todo o percurso sem expor operações intermediárias:

```text
núcleo determinístico → SafeInterpretiveChart → Premium Author (Sol High)
→ Deterministic Provenance Guard → Premium Reviewer/Editor (Sol High)
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

O JSON resultante contém payload técnico, claims, temas, timing e relatório. Apresente a seção `report` para o usuário e conserve o restante para auditoria ou apêndice técnico.

## Segurança interpretativa

Bloquear ou reformular frases que atribuam trauma, abuso, abandono, diagnóstico, morte, doença, gravidez, divórcio, falência ou qualquer acontecimento inevitável. Evitar "sempre" e "vai acontecer". Se não houver evidência estruturada suficiente, declarar a lacuna em vez de improvisar.

## Profundidade de relatório

- `executive`: leitura autossuficiente de aproximadamente 2–4 minutos, com assinatura do mapa, 3–4 temas quando sustentados, fase atual e experimento.
- `deep`: leitura humana de aproximadamente 6–10 minutos; mecanismos psicológicos, exemplos, áreas, fase atual, ciclos e integração. Profundidade secundária fica recolhida.
- `technical`: apêndice separado para dados, posições, casas seguras/condicionais, aspectos, hierarchy, `ReasonedSynthesis`, evidência, robustez, timing e versões.

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
