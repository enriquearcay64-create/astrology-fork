# Gates de qualidade v4

O release só é aprovado quando quatro lentes passam: **Technical Truth** (cálculo), **Interpretive Integrity** (dedução dentro do pacote fechado), **Individuality** (diferença real entre cartas) e **Human Experience** (leitura clara, humana e útil). Nenhuma métrica isolada substitui a revisão editorial.

## Technical Truth

- Compare posições, casas e `swe.house_pos` com Swiss Ephemeris de referência.
- Teste timezone IANA, ambiguidade de DST, localizações polares e política de fallback.
- Teste dignidades por tabela, applying/separating com delta curto, invariância à ordem dos pares e limites da faixa das efemérides.
- Reproduza a mesma entrada com a mesma versão de backend, metodologia e tzdata.

## Interpretive Integrity

- Garanta que dispositores e condições estejam na análise compartilhada, não em Whole Sign.
- Garanta que coincidência de casas gere `house_system_robustness`, não uma segunda família de evidência.
- Garanta que feedback, localização e rótulos derivados de retorno não aumentem suporte astrológico.
- Execute ablações Whole Sign, angularidade, pontos secundários, localização, feedback e motivos semânticos.
- Garanta que a hierarquia natal permaneça idêntica quando mudar apenas o horizonte temporal.
- Garanta que idade zero não gere retorno e que passagens do mesmo ciclo sejam agrupadas.
- Compare aspectos de hora desconhecida em 00:01 e 23:59; nenhum aspecto instável pode chegar aos claims.
- Teste incerteza horária acima dos gates e rejeite claims de casas/ângulos sensíveis.
- Teste ASC em 29°59' e 0°01'. Incerteza declarada que torna a topologia condicional não pode expor casas regulares, regentes tópicos, Lots ou profecções; o renderer não deve receber o raw chart. Um stress test contrafactual para hora declarada exata deve gerar divulgação de alta sensibilidade sem reclassificar a hora declarada.
- Teste três passagens retrógradas próximas (uma `activation_instance`), a mesma assinatura quatro anos depois (duas instâncias) e ramos geométricos opostos (instâncias distintas).
- Construa claims forjados com tema, família, suporte e texto adulterados; o verificador deve bloquear todos.
- Construa `ReasonedSynthesis` adversarial: factor id inexistente, `source_claim_id` inexistente, proposição sem fonte, texto semanticamente desconectado e especificidade biográfica. O Synthesis Judge deve bloquear cada caso; uma ablação do claim/factor crítico deve quebrar a cadeia.
- Teste a cadeia premium completa: motif autorizado apenas pela claim citada, fator primário suportado pela mesma claim, operação compatível, teto de confiança, `packet_id`, hashes do bundle/rascunho/final, evidência temporal tipada e mapa de fontes de cada narrative block source-required. Em 1.4, confirme a separação entre paragraphs/list items coverage-eligible e H3 sourced coverage-ineligible, a legalidade individual das syntheses por path e o recheck final do ReaderSelectionPlan. O guard é de proveniência, não uma alegação de prova semântica.
- Teste T-square com ápice explícito e stellium cujos `position.<body>` existem no ledger. Teste que dois aspectos com a mesma palavra (por exemplo, dois quadrados) mas corpos diferentes não geram falsa referência cruzada no planner.
- Teste que Urano, Netuno ou Plutão não ancorem uma `ChartSignature` pessoal apenas por conectividade geracional: sem vínculo seguro a planeta pessoal/ângulo, o modo deve permanecer `distributed`; ao acrescentar esse vínculo, `central` pode ser permitido.
- Teste `exact_at` versus `closest_approach_at`, entrada/saída de orbe e identidade de ciclo retrógrado; não aceite data aproximada apresentada como exata.
- Construa e inspecione o wheel; CLI e efemérides devem estar presentes.

## Narrative Quality

- Verifique rastreabilidade de cada claim.
- Bloqueie inferência biográfica, diagnóstica, causal e fatalista.
- Execute ataques semânticos em português e inglês e rejeite perguntas sensíveis na consultoria.
- Execute contrafactual de horário/ASC: relatório não pode permanecer idêntico após mudança material.
- Faça report-swap e blind matching somente com participantes reais e consentimento; desabilite Localization ou mantenha o mesmo perfil em todos os relatórios-isca.
- Leia a saída fora do código: introdução, temas humanos, áreas, técnica, timing e conclusão devem formar uma progressão compreensível.
- Verifique equilíbrio editorial Logos–Eros: fatos e rastreabilidade permanecem acessíveis, mas não antecedem nem sufocam contexto, nuance e integração.
- Garanta que a conclusão não repita a introdução, que múltiplas passagens do mesmo trânsito formem uma janela e que a consulta termine com experimento sustentado pelos temas selecionados.
- Execute `python3 scripts/ux_editorial_audit.py --stage before|after --output DIRETÓRIO` com mapas congelados antes e depois de alterações editoriais. O perfil de leitor no manifest é somente lente de auditoria e nunca pode ser passado ao pipeline.
- Meça palavras, minutos, seções, parágrafos, bullets, conteúdo recolhido, jargão e reutilização entre relatórios. Leia os artefatos integralmente; métricas não substituem julgamento editorial.
- Meça também reutilização semântica, sobreposição de temas, repetição de exemplos, similaridade de abertura/conclusão e Barnum-risk. São detectores, não metas para otimização cega.
- Faça ablação de fator dominante, angularidade, Whole Sign, Placidus, pontos menores e hierarquia. A narrativa deve mudar nos mecanismos dependentes da evidência retirada, não de forma aleatória.
- Em `HumanizationPass`, preserve citações internas; o verificador precisa comparar a `ReasonedSynthesis` pré-prosa com o significado e limites da prosa final.
- No report-swap, trate frases idênticas de metodologia como esperadas, mas penalize mecanismos psicológicos, exemplos, paradoxos ou conclusões intercambiáveis.
- Para cada 1.4, inspecione a assinatura de layout (por exemplo `P-H3-L-L-P`) e a proporção descritiva de domínios com a mesma assinatura. Uniformidade visual alta é sinal para inspeção humana, nunca erro automático. Jargon, Barnum, genericidade, idioma e métricas de palavras reader-visible incluem H3; profundidade e coverage contam somente paragraphs/list items.
- Verifique que cada tema configurado em português e inglês tem expressão diferenciada e exemplo vivido; nenhum tema conhecido pode cair no fallback genérico.

## Individuality e Human Experience

- Excluindo avisos, headings e metodologia fixa, meça reutilização literal e semântica de prosa interpretativa entre mapas estruturalmente distintos.
- Use report-swap como auditoria cega de diferenciação, não como prova da astrologia. Para avaliação humana, use pessoas consentidas e perfis de localização iguais ou desligados.
- Audite primeiros cinco minutos, compreensão leiga, tamanho, ritmo, carga emocional, agência, jargão e cinco ideias que um leitor lembra no dia seguinte.
- Teste Localization ligado/desligado no mesmo mapa. Só linguagem e exemplos podem mudar; temas, fatores, pesos e a interpretação psicológica têm de permanecer equivalentes.

## Protocolo qualitativo Premium Complete

Depois de produzir artefatos Premium aprovados pelos dois guards, registre para cada run `pass`, `concern` ou `fail`, com trecho e nota curta, para voz 4 e cuidado humano percebido; profundidade irregular ganha pela carta; consideração de mecanismos e caminhos distintos; continuidade entre domínios; completude e convergência do timing; localidade de atribuição semântica; vazamento de linguagem de QA/roteamento; neutralidade de gênero e consistência de locale; registro corporativo/executivo; e síntese whole-person memorável.

**Referência humana de Voice 4:** numa escala editorial de 1 a 10, `1` é muito místico, suave e emocionalmente saturado; `10` é técnico, diagnóstico, distante e executivo. O alvo permanece aproximadamente `4`: quente, receptivo, íntimo sem familiaridade presumida, fluido e psicologicamente legível, reflexivo em vez de diagnóstico, mas ainda preciso, inteligente e grounded. `3–5` é somente tolerância de aceitação, não uma faixa que o Author deva variar deliberadamente. Esta escala pertence apenas ao QA humano e nunca vira instrução numérica para o Author nem gate automático.

As métricas de `ux_editorial_audit.py --premium-artifacts` são descritivas, não gates numéricos. Um `fail` de integridade, segurança, autoridade, linhagem, timing, idioma ou atribuição semântica bloqueia a liberação. Preocupações editoriais são lidas através da matriz de runs; não viram meta numérica nem justificam mudar código durante a fase de aceitação.

No ciclo V4.1.4, o dispatcher seleciona o parser pelo `premium_handoff_contract_version` do handoff authoritative: 1.3 usa o parser congelado de paragraph/replay; 1.4 usa o parser de narrative blocks. Não se inicia nova linhagem 1.3 e não se aceita substitution, downgrade, mixed fields ou bundle de versão cruzada.

## Limite dos resultados automáticos

Os testes internos provam consistência e diferenciação do software. Eles não provam a validade científica de correspondências astrológicas nem substituem piloto humano independente.

`run_synthetic_natal_pilot()` executa 24 entradas sintéticas variadas com Localization e timing desabilitados. Ele só pode aprovar estabilidade técnica, diferenciação de relatórios, Jaccard temático médio abaixo do limite e ausência de claims bloqueados. Para piloto humano, recrute participantes com consentimento, congele a versão metodológica, use relatórios-isca com o mesmo `LocalizationProfile` e separe quem produz de quem avalia.
