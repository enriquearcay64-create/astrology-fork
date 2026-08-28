# Auditoria de release — v3

Data: 2026-08-28  
Escopo: revisão v3 do skill local, com foco em rigor factual, individualidade e experiência editorial.  
Não é validação científica da astrologia nem teste humano de acerto biográfico.

## Resultado

O motor passou de uma arquitetura que fazia **facts → themes → texto quase-template** para uma que separa fatos, limites, síntese e narrativa:

~~~mermaid
flowchart LR
  A["Raw Chart: cálculo determinístico"] --> B["Stability Gate"]
  B --> C["SafeInterpretiveChart: somente fatos seguros"]
  C --> D["ReasonedSynthesis: fatores + modificadores + contrapesos"]
  D --> E["NarrativePlanner"]
  E --> F["HumanizationPass"]
  F --> G["Verificador factual e semântico"]
~~~

O princípio implementado é: **hard facts, soft synthesis, hard verification**.

## Bugs corrigidos

1. **Vazamento de casas instáveis — corrigido.** O cálculo bruto ainda conserva tudo para auditoria, mas síntese, consulta e renderer recebem apenas SafeInterpretiveChart. Se o stress test ±5/±15/±30 minutos muda o signo do ASC, casas, regentes tópicos, Lots e profecções deixam de ser fatos interpretativos.
2. **Reconstrução indireta da topologia — corrigido.** A hierarquia não volta a derivar regente do ASC de uma topologia Whole Sign condicional; a profecção anual retorna status conditional.
3. **Cluster temporal por família semântica — corrigido.** Eventos trazem semantic_family e activation_instance. Passagens retrógradas próximas pertencem à mesma instância; recorrência distante ou ramo geométrico oposto não é fundido. O renderer preserva essas instâncias.
4. **Revolução Solar — transparência corrigida.** Está marcada como technical_support_available, não como módulo interpretativo completo.

## Nova camada interpretativa

### ReasonedSynthesis e ThemeCompositionEngine

Cada tema recebe um objeto rastreável com observação, 1–5 fatores primários existentes, modificadores de condição/hierarquia, contrapesos, classe de raciocínio, confiança dentro do modelo, expressões hipotéticas, leitura alternativa, extensões proibidas e estado de verificação.

O registry continua existindo, mas agora define alcance semântico, motivos possíveis, teto de especificidade e extrapolações perigosas. Ele não fornece a frase final. O pacote fechado enviado ao modelo inclui funções planetárias, natureza do aspecto, hierarquia, contexto de casa seguro/condicional, dados de timing e regras de liberdade 0–4.

### NarrativePlanner, humanização e verificação

O planner seleciona dinâmica central ou centros distribuídos, ordem, referências cruzadas e tópicos técnicos a ocultar. A camada de humanização pode mudar ritmo, exemplos e transições, mas não acrescentar fator, biografia, evento, diagnóstico, timing ou certeza. O contrato de verificação posterior exige equivalência semântica entre a ReasonedSynthesis e a prosa final.

O CLI local mantém um fallback determinístico legível. A síntese realmente livre depende do modelo de alto raciocínio que consome o reasoning_packet; o skill fornece esse contrato e suas validações, mas não chama uma API externa automaticamente.

## UX e individualidade: dados reais

Foram gerados os mesmos três mapas sintéticos A/B/C, sem informações biográficas no pipeline:

- A: adulto, leigo, objetivo; pt-BR/Brasil.
- B: adulta, leiga, interessada em profundidade; pt-BR/Portugal. A lente de gênero não entra no motor.
- C: pessoa de 63 anos, gênero não especificado, leitora cética; en-US/Canadá. Escolhida para testar idade, idioma, ceticismo e neutralidade de gênero.

Artefatos finais: ux-audit-v3-2026-08-28/final4/.

| Métrica | Antes (v2.4) | Depois (v3) | Leitura honesta |
|---|---:|---:|---|
| Reuso literal interpretativo — deep | 15 | 5 | melhoria forte |
| Similaridade semântica heurística — deep | 19 | 7 | melhoria forte, mas ainda requer revisão humana/LLM |
| Reuso literal interpretativo — executive | 5 | 6 | piora pequena; a nova orientação ainda é repetitiva |
| Similaridade semântica heurística — executive | 7 | 7 | sem ganho mensurável |
| Barnum lint | 0% A/B/C | 0% A/B/C | lint limitado; não prova ausência de generalidade |
| Tempo médio deep | 7,6 min | 6,1 min | mais conciso; B ficou ligeiramente abaixo da faixa ideal |
| Jargão médio deep | 11,7 | 10,7 | pequena melhoria; técnica segue no apêndice |
| Erros de casa instável no fixture de fronteira | 1 conhecido | 0 nos testes-alvo | corrigido arquiteturalmente |
| Erros de cluster temporal nos fixtures | 1 conhecido | 0 nos três testes-alvo | corrigido |
| Report-swap | não executado com pessoas | pré-screen A–B: 7 sentenças | não equivale a teste cego humano |

Os valores de similaridade são heurística de sobreposição de tokens, não embeddings nem veredito de um avaliador LLM. O relatório inclui o prompt para a próxima etapa de avaliação semântica cega.

## Testes executados

- **73 testes automatizados passaram.**
- Casos de ASC em fronteira e stress test; nenhum conteúdo de casa regular chegou ao safe view.
- Três casos de instância temporal: loop retrógrado próximo, repetição após quatro anos e ramos opostos.
- Teste do próprio renderer para confirmar que não reagrupa instâncias distantes.
- 24 mapas sintéticos: 24 concluídos, 24 hashes de relatório únicos, 0 claims bloqueados no rendering, Jaccard médio de temas 0,4845.
- Wheel v3 construído e CLI do wheel instalado/testado em ambiente isolado.

## Leitura como cliente: crítica brutal

### As 10 melhores decisões

1. A separação raw/safe remove uma classe de erro perigosa.
2. Timing deixou de sugerir janelas de vários anos como se fossem uma ativação única.
3. Casas Whole Sign e Placidus são integradas sem contagem dupla.
4. Dados incertos aparecem como incerteza, não omissão silenciosa.
5. O pacote de raciocínio dá ao modelo margem para síntese sem margem para inventar fatos.
6. Contraevidência e leitura alternativa estão modeladas, não só pedidas em prompt.
7. O relatório começa pela pessoa, não pela metodologia.
8. Timing e timeline adotam linguagem de possibilidade e agência.
9. Localization permanece exclusivamente renderização.
10. O apêndice técnico tornou-se auditável sem poluir a leitura principal.

### Os 10 maiores problemas restantes

1. O fallback local ainda é mais formulaico que uma boa leitura feita pelo Sol em High Thinking.
2. Aberturas A e B ainda têm cadência parecida; o pré-screen continua apontando troca possível.
3. Alguns exemplos de aspecto são corretos, mas pouco vivos.
4. O executive agora alcança 2,0 minutos, mas ainda fica em 430–436 palavras, pouco abaixo da faixa editorial de 450–750.
5. O deep B mede 5,7 minutos — muito próximo, mas abaixo da faixa de 6–10 minutos.
6. A avaliação Barnum atual é lint; falta avaliador semântico integrado com modelo.
7. O HumanizationPass tem contrato/verificador, mas o CLI não executa modelo remoto por privacidade e reprodutibilidade.
8. Localization está extensível e seguro, mas espanhol/holandês/japonês ainda não têm renderer completo; o contexto pode ser entregue ao modelo, porém o fallback só é pt/en.
9. Progressões e arcos solares têm cálculo e contexto, mas ainda não possuem a profundidade interpretativa composicional dos trânsitos.
10. Revolução Solar permanece suporte técnico; não é leitura completa.

## O que não foi maquiado

- Nenhuma métrica de UX foi usada como prova de validade astrológica.
- Não houve participação humana fingida no report-swap.
- A nacionalidade não foi usada para inferir personalidade.
- Casas condicionais não foram salvas por linguagem suave; foram removidas do objeto interpretável.
- Solar Return não foi promovida artificialmente a produto maduro.

## Avaliação de valor percebido

No estado **fallback local**, a leitura parece um produto na faixa de **US$30–50**: cálculo, segurança, apêndice e timing são fortes, mas a voz ainda deixa perceber estrutura gerada. Com o **Sol em High Thinking** seguindo o pacote, planner e verificador v3, ela pode justificar **US$50–75** se a revisão semântica cega confirmar diferenciação real. Eu não prometeria **US$75+** ainda: faltam piloto humano, humanização efetiva em produção e módulos de progressões/retorno solar igualmente maduros.

## Nota

- **Antes da auditoria v3: 7,2/10.**
- **Depois das correções v3: 8,3/10 para skill local; 8,8/10 como arquitetura pronta para Sol High Thinking.**

Não é 10/10. Para chegar lá, faltam execução real do modelo de síntese com verificador semântico automático, teste cego humano de report-swap, melhoria dos exemplos e produção editorial em idiomas além de pt/en. A base técnica, porém, já está em nível de produto: o modelo pode pensar mais livremente sem receber permissão para inventar.
