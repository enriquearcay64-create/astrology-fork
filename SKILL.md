---
name: interpretar-mapa-astrologico
description: Calcular fatos astrológicos determinísticos e produzir leituras natais, trânsitos, profecções, progressões, arcos solares, Revoluções Solares e timelines com síntese holística rastreável, Signo Inteiro + Placidus e relatórios humanos em português ou inglês. Use quando o usuário pedir leitura de mapa, fases de vida, ciclos, previsão astrológica condicionada, relatório natal, consulta sobre uma pergunta de vida ou comparação técnica entre casas/ângulos.
---

# Astrologia avançada e rastreável

Use este skill como leitura simbólica e reflexiva. A precisão prometida é astronômica e metodológica; não declare validação científica de personalidade ou previsão de eventos.

## Dados necessários

Exigir data local, fuso IANA, latitude e longitude. Solicitar hora local ISO quando conhecida; quando desconhecida, exigir `birth_time_known: false` e aplicar somente fatores que sobrevivam à análise do dia inteiro. Aceitar perfil de localização somente se fornecido pela pessoa. Não inferir cultura, país atual ou psicologia pelo local de nascimento.

Leia [references/input-schema.md](references/input-schema.md) antes de preparar a entrada. Para regras interpretativas, leia [references/methodology.md](references/methodology.md). Antes de apresentar o resultado, leia [references/report-design.md](references/report-design.md). Para licença e dependências, leia [references/dependencies.md](references/dependencies.md).

## Fluxo obrigatório

1. Rodar o núcleo determinístico, nunca calcular posições, casas, aspectos, orbes, Lots ou datas manualmente.
2. Validar qualidade de dados e os gates de estabilidade antes de interpretar aspectos, ângulos ou casas sensíveis. Aviso sem bloqueio não é suficiente.
3. Tratar Whole Sign como topologia temática e Placidus como análise espacial complementar. Usar os estados versionados de integração, nunca duplicar evidência quando a casa coincide nem escolher sistema depois de conhecer a biografia.
4. Usar ASC/DSC/MC/IC como análise independente. Não confundir angularidade com dignidade, facilidade ou saúde mental.
5. Construir primeiro a `SafeInterpretiveChart`; nunca entregar casa, ângulo, Lot, profecção ou regente tópico instável ao renderer ou à síntese como fato seguro. Diferenciar incerteza declarada de stress tests contrafactuais.
6. Usar o registry como limite semântico, não como roteiro de frases. Produzir `ReasonedSynthesis` a partir do pacote factual fechado: cada inferência emergente deve citar 1–5 fatores existentes, modificadores, contrapesos, leitura alternativa e teto de especificidade.
7. Permitir `derived_claim` em síntese de nível 2 quando o verificador confirmar fatores existentes, suporte adequado e ausência de extensão proibida. Não exigir que a frase final já exista no registry.
8. Antes de redigir, criar `NarrativePlanner`: dinâmica central sustentada (ou centros distribuídos), ordem dos temas, interações, detalhes técnicos a ocultar e prevenção de repetição.
9. Aplicar `HumanizationPass` depois da síntese: variar ritmo, exemplos e transições; preservar significado e fatores citados; não acrescentar dado astrológico, biografia, certeza ou timing.
10. Verificar factual e semanticamente a saída final. Se a prosa introduzir um fator, uma extensão ou uma certeza não autorizada, reduzir especificidade ou regerar.
11. Distinguir predisposição simbólica, capacidade e manifestação. Feedback do usuário pode contextualizar exemplos, mas nunca altera suporte astrológico ou escolhe sistema de casas.
12. Aplicar Localization somente depois da síntese. Ela só pode alterar linguagem, exemplos, unidades, referências e formato; nunca inferir psicologia da cultura.
13. Ao falar de timing, separar stream tradicional e moderno; usar `activation_instance` para passagens do mesmo ciclo e nunca fundir recorrências distantes pelo mesmo nome de aspecto. Não prometer eventos.
14. Aplicar divulgação progressiva e equilíbrio Logos–Eros: arquitetura humana primeiro; 3–4 temas centrais quando sustentados, sem quota fixa; quatro áreas concretas; timing natal antes do jargão; intervalos emergentes antes de décadas; detalhes técnicos no apêndice; síntese diferente da abertura e com experimento observável.

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
