# Metodologia versionada

## Regras nucleares

- Use Placidus como sistema canônico de casas para interpretação natal psicológica; calcule posição com `swe.house_pos`, nunca por interpolação zodiacal de cúspides. Para qualificação de cúspide, priorize a fração da posição contínua da casa e registre separadamente a distância zodiacal em longitude.
- Use Whole Sign somente onde a técnica o exige, incluindo profecções anuais e Lots/regências tradicionais explicitamente configurados. Whole Sign não cria uma segunda leitura natal paralela.
- Calcule ASC, DSC, MC, IC, Vertex e Anti-Vertex independentemente da domificação. MC não é sinônimo de cúspide da 10ª em Whole Sign.
- Trate qualquer concordância de casas como nota de robustez, não como duas evidências independentes. Placidus indisponível retira a interpretação natal de casa; Whole Sign não a substitui.
- Mantenha dispositores, dignidades, recepções, secto, velocidade e condições na análise zodiacal compartilhada; eles não dependem de Whole Sign.
- Comece com Fortuna e Espírito. Lots adicionais são avançados e desabilitados por padrão.
- Interceptações, posição contínua dentro da casa, aspectos menores, Vertex, Lilith e Quíron não criam leitura natal central por padrão. O eixo nodal natal (Nodo Norte verdadeiro + Nodo Sul derivado) recebe cobertura Premium como uma única família estrutural, sem virar centro automático; Lilith e Quíron permanecem técnicos. A política de timing 2.3 permite somente conjunção/oposição do Nodo e retorno de Quíron como ciclos nomeados; Lilith permanece excluída. Qualquer uso natal adicional exige política explícita e ablação.
- Separe proeminência natal de relevância tópica/temporal. Alterar o horizonte de previsão nunca pode alterar a hierarquia natal.
- Registre recursos de condição e fricções em campos separados; não transforme dignidade, retrogradação e combustão numa única nota de qualidade. Retrogradação de Mercúrio a Saturno pode somar fricção; Urano, Netuno e Plutão retrógrados permanecem condições técnicas, sem inflar essa nota.
- Calcule elementos, modalidades, polaridades e hipóteses de escassez com Sol–Saturno. Mostre Urano–Plutão na distribuição ampliada, mas não deixe uma assinatura geracional determinar compensação individual.
- Defina stellium explicitamente como três ou mais corpos primários no mesmo signo ou na mesma casa Placidus confiável. Rotule a base; grupos idênticos por signo e Placidus formam uma família estrutural única, sem virar duas evidências independentes.
- Se a hora for desconhecida, use meio-dia apenas como proxy documentado, compare os extremos do dia e retenha somente aspectos estáveis. Desabilite casas, ângulos, secto, Lots e profecção. Exclua do timing natal qualquer corpo que ultrapasse o limiar diário versionado. O **premium beta** exige hora conhecida; esse caminho limitado continua disponível para leitura determinística segura.
- Separe incerteza declarada de stress test. `declared_uncertainty_minutes` descreve a informação recebida e é a única entrada que pode retirar casas, regentes tópicos, profecções e Lots da leitura principal. Os testes padrão ±5/±15/±30 minutos medem fragilidade mesmo quando o horário foi declarado exato; uma travessia de signo do ASC gera `high_boundary_sensitivity`, divulgada uma vez, mas não reclassifica silenciosamente a qualidade declarada. O ângulo calculado continua sujeito ao seu próprio gate.
- Aplique cazimi, combustão e sob os raios somente aos cinco planetas tradicionais não luminares. Planetas modernos e pontos secundários permanecem fora dessa classificação.

## Padrão interpretativo operacional — v4

O princípio é **hard facts, soft synthesis, hard verification**. O núcleo calcula e fecha o universo factual; Author High seleciona e compõe; Reviewer High julga significado e qualidade; os guards verificam integridade sem alegar prova da interpretação simbólica.

1. **Seleção e omissão:** existência não promove um fator. Proeminência estrutural, conectividade, repetição independente, relevância tópica, confiabilidade e ativação informam quais poucos fatores entram; o restante pode ser deliberadamente omitido.
2. **Mecanismos antes de placements:** a leitura humana explica principalmente como funções interagem, não enumera posições.
3. **Repetição sem repetição:** suportes independentes podem fortalecer um insight, mas não gerar paráfrases do mesmo parágrafo.
4. **Sem dupla contagem:** robustez entre casas, rótulos derivados e estruturas agregadas/constituintes não viram votos extras.
5. **Centralidade emergente:** `ChartSignature` governa o planner; use `central` apenas quando poucos fatores explicam várias sínteses. Em mapas `distributed`, preserve centros distintos sem fabricar uma grande história.
6. **Dinâmica antes de valência:** conjunção concentra, sextil coordena, quadratura cria fricção, trígono reduz resistência, quincúncio ajusta e oposição polariza. O contexto decide recurso, automatismo, pressão ou capacidade; geometria não equivale a bom/ruim.
7. **Semântica composicional:** prefira função planetária × dinâmica do aspecto × contexto estrutural/tópico × modificadores × confiabilidade → significado candidato; regras de par são exceções úteis, não catálogo dominante.
8. **Ancestralidade semântica:** toda proposição derivada permanece no espaço autorizado pelas claims, motifs e fatores que cita. IDs válidos em outra parte do mapa não bastam.
9. **Teto de especificidade:** integração e humanidade podem aumentar; especificidade biográfica, certeza e causalidade não. A precisão vem da combinação de mecanismos, nunca de biografia inventada.
10. **Contradição preservada:** tendências válidas podem coexistir, alternar por contexto ou permanecer sem resolução; não force síntese conciliadora.
11. **Contrapesos relevantes:** a camada determinística propõe candidatos por relação estrutural. Author escolhe somente os que qualificam a proposição/domínio; compartilhar um corpo não prova relevância. Reviewer remove contrapeso decorativo.
12. **Exteriores personalizados:** Urano, Netuno e Plutão não ancoram assinatura pessoal apenas por conectividade geracional. Para serem âncora `central`, exigem ligação segura a planeta pessoal ou ângulo principal; ainda podem atuar como contexto ou modificador.
13. **Integridade das casas:** Placidus fornece o contexto natal psicológico. Whole Sign entra somente em técnicas que o exigem. Concordância é robustez, não evidência duplicada; nenhuma divergência permite escolher retrospectivamente a narrativa mais conveniente.
14. **Timing e humanização disciplinados:** timing ativa arquitetura natal e usa evidência tipada; não garante evento. Humanização muda voz, ordem e exemplo, nunca evidência, sentido, certeza ou biografia.
15. **Resistência ao swap:** para cada parágrafo principal, pergunte se ele caberia com plausibilidade semelhante num mapa estruturalmente diferente. Se sim, corrija seleção, composição ou prosa — nunca invente detalhe de vida.

`SafeInterpretiveChart` é a única visão entregue à interpretação; registry e `Claim` são limites semânticos, não frases prontas. A regência de casa natal é um fato de encaminhamento: cúspide Placidus → signo da cúspide → regente tradicional configurado → contexto já autorizado do planeta. Ela só entra na visão segura quando o signo da cúspide-base coincide com os dois extremos da incerteza declarada; testes de estresse são apenas divulgação. Esse Claim não pesa hierarquia, proeminência ou confiança. `ReasonedSynthesis` registra claims, motifs, fatores, operações, modificadores, contrapesos, alternativa, confiança e proposições derivadas. A `ChartSignature` Premium é preparada e congelada antes do roteamento leitor; sínteses usadas para cobrir domínios não podem recalculá-la nem criar votos de centralidade. O manifest de domínios registra somente caminhos legais já autorizados e ênfase categórica derivada dessa assinatura. O **Deterministic Provenance Guard** prova existência, ancestralidade estrutural, permissões, operações, tetos, timing, hashes e coverage por narrative block. O contrato Premium 1.4 permite `claim_ids` somente para o Claim atômico explicitamente renderizável em paragraph ou list item; toda composição continua exigindo síntese aprovada. H3 é sourced e synthesis-only, mas não coverage-eligible. Ele também exige propriedade física de abertura, 16 domínios e integração sobre o mesmo universo canônico de narrative blocks do mapa de fontes, além de um plano canônico que contabiliza cada caminho legal como representado, integrado diretamente a uma rota representada ou editorialmente omitido. O **Premium Reviewer/Editor** julga se a dedução realmente faz sentido, se um contrapeso importa, se a contradição foi achatada, se há Barnum sofisticado e se o texto resiste ao swap. O **Publication Guard** confirma que o relatório publicado é exatamente o aprovado.

Níveis de liberdade: cálculo 0; inferência técnica 1; síntese astrológica 2; narrativa/exemplos 3; afirmação biográfica 4 (bloqueada sem contexto voluntariamente fornecido). Nunca infira trauma, abuso, abandono, diagnóstico, divórcio, morte, gravidez, doença, falência ou evento inevitável a partir do mapa.

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

## ReaderSelectionPlan e narrativa rastreável — contrato 1.4

O Author deve inspecionar o manifest completo e construir prospectivamente o `ReaderSelectionPlan` antes de escrever qualquer prosa. Cada legal path é decidida uma vez como `represented`, `merged_with_represented` ou `omitted_no_distinct_reader_value`; o plano não pode ser uma justificativa retrospectiva. A ordem das paths é apenas serialização e não expressa prioridade, centralidade ou preferência pela primeira path.

Seleção e omissão controlam centralidade, suporte redundante e repetição, mas no Premium Complete não podem apagar um mecanismo humano distinto exposto por uma legal path apenas porque seu fator é secundário à `ChartSignature`. Um merge precisa preservar a contribuição distinta em conteúdo integrado; compartilhar planeta, regente, classe de raciocínio, operação ou tópico amplo não basta. Uma omissão exige atestado do Reviewer de que nenhuma consequência humana distinta permanece.

No contrato 1.4, a unidade física é o narrative block: `paragraph`, `list_item` ordered/unordered ou H3 `subheading`. Paragraphs e list items são coverage-eligible; H3 é synthesis-only, semanticamente revisado, mas excluído de mandatory coverage, domain coverage e reader-selection provenance. O H3 deve pertencer a domínio disponível, citar syntheses legalmente pertinentes e ser seguido por paragraph ou list item. Cada bloco source-required tem uma row e um hash produzidos pelo mesmo `canonical_narrative_block_payload()`; H2 canônico, introdução fixa e aviso de indisponibilidade continuam estrutura determinística fora da proveniência autoral. Nested lists, tabelas, blockquotes, HTML blocks, code fences, separators, metadata e H4+ são ilegais. Bullets anexados a um parágrafo são separados em itens independentes.

Python prova somente invariantes determinísticos: shape, ordem, IDs, hashes, syntheses aprovadas, provenance física de paragraphs/list items, legalidade individual de sínteses, ancestry e conjuntos de timing, ownership, source-map integrity e coverage. O Reviewer prova por julgamento humano se a consequência distinta está materialmente expressa, se a convergência é real, se a prosa preserva o mecanismo e se a omissão é semanticamente redundante. A Publication Guard repete a validação completa do plan contra o relatório final usando somente paragraphs/list items; H3 sourced sozinho nunca resgata coverage, selection ou um domínio. O contrato 1.3 permanece congelado para validation/replay-only e não inicia novas linhagens.

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
