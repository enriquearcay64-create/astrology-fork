# Metodologia versionada

## Regras nucleares

- Use Whole Sign para topologia, tópicos, regentes tópicos, profecções e Lots tradicionais configurados.
- Use Placidus como análise espacial complementar; calcule posição com `swe.house_pos`, nunca por interpolação zodiacal de cúspides. Para qualificação de cúspide, priorize a fração da posição contínua da casa e registre separadamente a distância zodiacal em longitude.
- Calcule ASC, DSC, MC, IC, Vertex e Anti-Vertex independentemente da domificação. MC não é sinônimo de cúspide da 10ª em Whole Sign.
- Trate `house_system_robustness` como robustez à escolha de sistema, não como duas evidências independentes. Classifique a integração como `robust_same_house`, `whole_topic_placidus_qualifier`, `complementary_emphases`, `material_divergence` ou `placidus_unavailable` por regra pré-biográfica. `robust_same_house` nunca é “convergência forte” nem voto extra; é apenas uma nota de robustez.
- Mantenha dispositores, dignidades, recepções, secto, velocidade e condições na análise zodiacal compartilhada; eles não dependem de Whole Sign.
- Comece com Fortuna e Espírito. Lots adicionais são avançados e desabilitados por padrão.
- Interceptações, posição contínua dentro da casa, aspectos menores, Vertex, Lilith, Nodo e Quíron não criam leitura natal central por padrão. Eles ficam no apêndice técnico. A política de timing 2.3 permite somente conjunção/oposição do Nodo e retorno de Quíron como ciclos nomeados; Lilith permanece excluída. Qualquer uso natal adicional exige política explícita e ablação.
- Separe proeminência natal de relevância tópica/temporal. Alterar o horizonte de previsão nunca pode alterar a hierarquia natal.
- Registre recursos de condição e fricções em campos separados; não transforme dignidade, retrogradação e combustão numa única nota de qualidade. Retrogradação de Mercúrio a Saturno pode somar fricção; Urano, Netuno e Plutão retrógrados permanecem condições técnicas, sem inflar essa nota.
- Calcule elementos, modalidades, polaridades e hipóteses de escassez com Sol–Saturno. Mostre Urano–Plutão na distribuição ampliada, mas não deixe uma assinatura geracional determinar compensação individual.
- Defina stellium explicitamente como três ou mais corpos primários no mesmo signo ou na mesma casa de Signo Inteiro. Rotule a base; um mesmo agrupamento pode aparecer nas duas categorias, sem virar duas evidências independentes.
- Se a hora for desconhecida, use meio-dia apenas como proxy documentado, compare os extremos do dia e retenha somente aspectos estáveis. Desabilite casas, ângulos, secto, Lots e profecção. Exclua do timing natal qualquer corpo que ultrapasse o limiar diário versionado.
- Separe incerteza declarada de stress test. `declared_uncertainty_minutes` descreve a informação recebida e é a única entrada que pode retirar casas, regentes tópicos, profecções e Lots da leitura principal. Os testes padrão ±5/±15/±30 minutos medem fragilidade mesmo quando o horário foi declarado exato; uma travessia de signo do ASC gera `high_boundary_sensitivity`, divulgada uma vez, mas não reclassifica silenciosamente a qualidade declarada. O ângulo calculado continua sujeito ao seu próprio gate.
- Aplique cazimi, combustão e sob os raios somente aos cinco planetas tradicionais não luminares. Planetas modernos e pontos secundários permanecem fora dessa classificação.

## Inferência e narrativa — v4

O princípio é **hard facts, soft synthesis, hard verification**.

1. Calcule fatos astronômicos e gates de estabilidade de forma determinística.
2. Construa `SafeInterpretiveChart`; o renderer e a síntese nunca recebem `raw_chart.house`.
3. Produza factors, `Claim` e registry como limites semânticos — não como frases prontas.
4. Dê ao modelo apenas um pacote factual fechado. Em `ReasonedSynthesis`, ele pode compor fatores existentes, criar `derived_claim` rastreável, indicar `source_claim_ids`, `source_motif_ids`, operações de composição, proposições derivadas, modificadores, contrapesos, alternativa e nível de confiança dentro do modelo astrológico.
5. O Synthesis Judge valida fatores, proveniência, limites semânticos e escalada biográfica. O Narrative Judge compara a prosa humanizada com a síntese autorizada. São gates distintos.
6. `ChartSignature` está upstream do `NarrativePlanner`: pontua proeminência, regente do ASC, angularidade, focos configuracionais, dispositor final, conexões entre sínteses e domínios seguros. Um modo `central` exige um corpo estrutural que conecte pelo menos três sínteses autorizadas; caso contrário o modo é `distributed` e não força uma grande história. O planner escolhe abertura, ordem, referências cruzadas e áreas prioritárias a partir dessa assinatura, usando corpos e ids tipados, nunca fragmentos de texto de aspectos.
7. `HumanizationPass` decide voz, ritmo e exemplos hipotéticos; não pode adicionar fator, biografia, evento, diagnóstico, timing ou certeza. O verificador factual/semântico bloqueia fato novo, casa condicional tratada como fato, biografia inventada, diagnóstico, evento ou previsão.

Níveis de liberdade: cálculo 0; inferência técnica 1; síntese astrológica 2; narrativa/exemplos 3; afirmação biográfica 4 (bloqueada sem contexto voluntariamente fornecido).

Nunca infira trauma, abuso, abandono, diagnóstico, divórcio, morte, gravidez, doença, falência ou evento inevitável a partir do mapa.

O verificador deve checar existência da evidência, família canônica, tema, tipo, suporte, teto de especificidade, contrapesos, limites de incerteza e linguagem proibida em português e inglês. Uma blacklist isolada não é considerada verificação suficiente. O registry delimita alcance permitido, motivos usuais e extrapolações perigosas; ele não dita a frase do relatório.

## Streams de timing

- Tradicional: profecção anual → senhor do tempo → trânsito relevante → síntese tradicional.
- Moderno: trânsitos maiores e ciclos; depois progressões secundárias e arcos solares.
- Síntese cruzada: agrupa técnicas sem contar o mesmo fenômeno duas vezes. Um Saturn Return é rótulo derivado do trânsito de Saturno conjunto a Saturno natal, não nova evidência.
- Contato natal na idade zero é baseline e nunca um retorno de desenvolvimento. Cada janela conserva `closest_approach_at`, `minimum_orb`, `perfected`, `exact_at` (somente quando uma raiz geométrica segura é refinada) e entrada/saída de orbe, refinadas por busca binária a 0,0001°. Uma aproximação muito próxima continua sendo `closest_approach`, não uma perfeição. Passagens de um mesmo ciclo retrógrado são agrupadas pela identidade do ciclo direto–retrógrado–direto; recorrências separadas ou ramos geométricos distintos formam `activation_instance` independentes, mesmo que tenham a mesma `semantic_family`.
- Revolução Solar: o instante pode ser calculado sem local. Casas e ângulos exigem uma política explícita (`birth_place`, `habitual_residence` ou `actual_physical_location`) e localização conhecida.

## Localization e consulta

Localization ocorre depois do core. Pode alterar idioma, exemplos, unidades, datas e referências; nunca temas, pesos, personalidade ou previsão. Use somente perfil fornecido pela pessoa. Consulta contextual usa fatos voluntariamente informados, mas não os reclassifica como suporte astrológico.

## Entrega psicologicamente responsável

- Comece por padrões estruturais e escolhas observáveis, não por rótulos identitários.
- Apresente expressão construtiva, defensiva, excessiva, subdesenvolvida e integrada sem tratar “sombra” como defeito moral.
- Ofereça exemplos como hipóteses para testar e sempre inclua a possibilidade de não ressonância.
- Use linguagem calibrada: “pode”, “tende a”, “em certos contextos”; nunca converta suporte interno em probabilidade estatística.
- Convide contraprovas concretas e diferencie o que a pessoa relata do que o sistema calculou.
- Em consulta, responda à pergunta usando hierarquia tópica; não despeje o mapa inteiro nem substitua decisão, terapia ou aconselhamento profissional.
- Equilibre Logos e Eros na escrita: dados, estrutura e limites devem sustentar — não preceder nem sufocar — contexto humano, relação, nuance e integração. Essa é uma regra editorial, não uma inferência de anima/animus sobre a pessoa.

## Variações que exigem versionamento

- backend e versão de efemérides;
- tzdata/ZoneInfo;
- orbes, aspectos e regências;
- variantes de Nodo e Lilith;
- fórmulas de Lots;
- regras de cúspide;
- política de casas e Revolução Solar;
- registry semântico e template do relatório.

O payload inclui um `policy` serializável com todas essas convenções e um `schema_version` independente.
