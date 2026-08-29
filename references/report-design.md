# Design narrativo do relatório

## Princípio

O relatório deve ajudar uma pessoa leiga a reconhecer padrões, contexto e possibilidades de escolha. Completude não significa obrigar todos os leitores a atravessar todo o cálculo. A saída é Markdown portátil: legível no Codex, em texto puro e em conversão futura. Não use animação decorativa, fontes externas ou cor como único portador de significado.

## Três camadas editoriais

1. **Executive Reading:** assinatura essencial, 3–4 temas realmente sustentados, dinâmica central (ou centros distribuídos), fase atual e um experimento. Deve ser útil se for a única parte lida.
2. **Deep Reading:** acrescenta dinâmica psicológica, exemplos vividos, áreas da vida, fase atual, ciclos e integração. Cada seção precisa adicionar uma dimensão, não apenas repetir o resumo.
3. **Technical Appendix:** versões, qualidade dos dados, posições, casas Placidus seguras/condicionais, ângulos, condições, aspectos/orbes, configurações, eixo nodal e timing selecionado. A pessoa leiga pode ignorá-lo completamente. Política JSON, claims, `ReasonedSynthesis`, plano narrativo, hashes e registros de guard ficam no audit sidecar interno.

## Ordem da leitura profunda

1. Arquitetura central do mapa em um parágrafo específico; comece por um padrão humano reconhecível quando isso ajudar, mas abra pela estrutura astrológica quando ela for mais clara ou natural.
2. Dinâmica organizadora ou 2–3 dinâmicas distribuídas, somente quando sustentadas.
3. Três ou quatro temas centrais em prosa com movimento variado: recurso, tensão, risco contextual, contrapeso ou integração conforme a carta — nunca fórmula fixa nem quota de cinco.
4. Um exemplo vivido somente quando ele concretiza o mecanismo; normalmente até três no total.
5. Até quatro áreas Placidus mais relevantes; ocupação, proeminência e corpos estruturais informam a escolha sem reforço circular. As doze áreas ficam recolhidas. Regência Whole Sign só aparece dentro de técnica tradicional nomeada.
6. Fase atual em linguagem humana; nomes técnicos ficam recolhidos.
7. Intervalos emergentes de desenvolvimento (por exemplo, 28–31), explicando convergência, pressão possível, potencial e o que não pode ser inferido; o mapa completo de ciclos fica recolhido.
8. Síntese, experimento observável e duas perguntas.
9. Temas secundários, equilíbrio e qualidade dos dados em profundidade opcional.

## Ritmo e carga cognitiva

- Prefira parágrafos de aproximadamente 60–130 palavras para ideias psicológicas completas. Menores são válidos para conclusões; ultrapassar 150 palavras exige razão editorial.
- Não transforme todo modo de expressão em bullet. Use prosa para relações e bullets para escolhas, janelas, passos ou mapeamentos.
- Mantenha somente os 3–4 temas que a assinatura e o plano narrativo sustentam no fluxo principal. Temas restantes ficam recolhidos em tabela compacta.
- Use no máximo um exemplo por tema no corpo principal. Três exemplos totais normalmente bastam.
- Evite mais de dois blocos emocionalmente pesados sem uma passagem por recurso, contexto ou agência.
- Um heading deve responder a uma pergunta diferente. Se a seção só repete um tema anterior, fundir ou cortar.

## Linguagem humana antes da técnica

Comece normalmente por uma capacidade, tensão ou escolha observável quando isso melhorar reconhecimento. Não imponha essa sequência: um aspecto, casa, configuração ou outra estrutura pode abrir a seção quando for mais claro ou natural, desde que seja traduzido imediatamente. Nomes de aspectos importantes podem permanecer visíveis quando ajudarem orientação e vierem acompanhados de linguagem comum.

Placidus fornece o contexto natal psicológico. Whole Sign só aparece no corpo principal quando uma técnica nomeada o exige, como a profecção anual. Nunca apresente os dois como narrativas natais concorrentes nem repita notas de robustez em cada planeta.

Se o teste de sensibilidade torna a topologia Whole Sign condicional, não use casas, profecções ou regentes tópicos para dar cor ao exemplo. Explique a cautela uma vez, em linguagem simples; cenários alternativos pertencem à profundidade opcional ou ao apêndice.

Timing segue a mesma regra: primeiro explique o campo humano e a negociação simbólica; depois forneça datas e técnica. Material tipado é candidato, não quota: omita uma janela segura quando ela não sustentar uma interpretação suficientemente específica. Aspectos, streams e convergência entre técnicas ficam em bloco recolhível ou no apêndice. Data é janela de observação, não promessa de acontecimento.

## Especificidade sem biografia inventada

- Rejeite frases Barnum como “você é forte, mas sensível” ou “valoriza liberdade”.
- Uma interpretação útil descreve mecanismo: necessidades em tensão, estratégia de proteção, custo provável, recurso contido no padrão e movimento de integração.
- Exemplos devem mostrar uma cena ou decisão observável, não apenas renomear funções planetárias.
- “Possível expressão” e “manifestação confirmada” permanecem categorias separadas. O texto nunca converte ressonância em prova.

## Luz, sombra e agência

Luz e sombra são lentes, não campos obrigatórios repetidos mecanicamente. A sombra descreve uma estratégia defensiva contextual, não defeito de caráter. Seja direto sem patologizar e conclua dificuldades com uma possibilidade de observação ou escolha. Não use sanduíche de elogio, guruísmo, espiritualês ou cautela tão repetitiva que torne a leitura inútil.

## Localização e gênero

Localization só altera linguagem, unidades, instituições e exemplos. Um exemplo localizado deve continuar humano se o nome do país for removido. Evite listas caricaturais de instituições locais.

Predominantemente dirija-se à pessoa em segunda pessoa natural, variando a construção quando a repetição soaria mecânica. A voz começa pelo significado humano, traduz imediatamente qualquer termo técnico e evita tom acadêmico, jurídico ou de QA interno. Interpretação vem antes de coaching.

Gênero, idade, ceticismo e estilo de leitura podem orientar auditoria editorial, pronomes e acessibilidade, mas não entram no motor interpretativo nem alteram peso, tema ou ênfase relacional. A astrologia, não o gênero, deve produzir diferenças entre relatórios.

## Gramática visual

- Use tabelas apenas para comparações ou mapeamentos repetidos: cinco temas, áreas da vida e dados técnicos.
- Use `↔` para uma polaridade quando isso melhora a navegação; o símbolo nunca substitui explicação.
- Use `<details>` para as doze áreas, base técnica do timing, ciclos completos, temas secundários, qualidade dos dados e política metodológica.
- Não use emoji em série, animação ou ornamentação que compita com a leitura.

## Alvos de extensão

São faixas de QA para produtos compactos, não quotas de preenchimento. Premium Complete não tem mínimo rígido de palavras: cobertura obrigatória e importância interpretativa decidem a extensão.

- Executive Reading: 450–750 palavras; cerca de 2–4 minutos.
- Deep Reading / Premium Complete: extensão adaptativa; cerca de 6–10 minutos apenas quando a arquitetura do mapa sustenta esse fôlego.
- Fase atual no corpo principal: 150–350 palavras.
- Ciclos visíveis: 120–300 palavras; mapa completo recolhido.
- Technical Appendix: tão longo quanto a auditoria exigir, preferencialmente 2.000–5.000 palavras, com política e listas longas recolhidas.

## Consulta específica

A consulta deve apresentar resposta direta, bases priorizadas, contrapesos recolhidos, timing relevante quando houver, síntese prática e limite. Não despeje o mapa inteiro, não recicle uma conclusão genérica e não substitua decisão profissional.

## Caminho premium

O pedido natural de leitura premium não mostra estágios internos ao leitor. O Codex prepara fatos seguros, um Author cria síntese e rascunho, o `Deterministic Provenance Guard` confirma a cadeia factual, um Reviewer/Editor independente melhora diretamente o texto e o `Publication Guard` confirma hashes, fontes por parágrafo e limites publicáveis. O reviewer, e não um gate por palavras-chave, julga fluidez, especificidade e deriva de significado.
