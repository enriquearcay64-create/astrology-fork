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
- Teste a cadeia premium completa: motif autorizado apenas pela claim citada, fator primário suportado pela mesma claim, operação compatível, teto de confiança, `packet_id`, hashes do bundle/rascunho/final, evidência temporal tipada e mapa de fontes de cada parágrafo substantivo. O guard é de proveniência, não uma alegação de prova semântica.
- Teste T-square com ápice explícito e stellium cujos `position.<body>` existem no ledger. Teste que dois aspectos com a mesma palavra (por exemplo, dois quadrados) mas corpos diferentes não geram falsa referência cruzada no planner.
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
- Verifique que cada tema configurado em português e inglês tem expressão diferenciada e exemplo vivido; nenhum tema conhecido pode cair no fallback genérico.

## Individuality e Human Experience

- Excluindo avisos, headings e metodologia fixa, meça reutilização literal e semântica de prosa interpretativa entre mapas estruturalmente distintos.
- Use report-swap como auditoria cega de diferenciação, não como prova da astrologia. Para avaliação humana, use pessoas consentidas e perfis de localização iguais ou desligados.
- Audite primeiros cinco minutos, compreensão leiga, tamanho, ritmo, carga emocional, agência, jargão e cinco ideias que um leitor lembra no dia seguinte.
- Teste Localization ligado/desligado no mesmo mapa. Só linguagem e exemplos podem mudar; temas, fatores, pesos e a interpretação psicológica têm de permanecer equivalentes.

## Limite dos resultados automáticos

Os testes internos provam consistência e diferenciação do software. Eles não provam a validade científica de correspondências astrológicas nem substituem piloto humano independente.

`run_synthetic_natal_pilot()` executa 24 entradas sintéticas variadas com Localization e timing desabilitados. Ele só pode aprovar estabilidade técnica, diferenciação de relatórios, Jaccard temático médio abaixo do limite e ausência de claims bloqueados. Para piloto humano, recrute participantes com consentimento, congele a versão metodológica, use relatórios-isca com o mesmo `LocalizationProfile` e separe quem produz de quem avalia.
