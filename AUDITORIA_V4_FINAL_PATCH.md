# Auditoria final — V4 quality patch

Baseline: `e5a72c349d367afe705c4b311f5844103b1187ab`.

Esta patch não adiciona técnicas, pontos ou sistemas. Ela corrige o caminho entre fatos verificados, assinatura do mapa, planejamento, prosa e precisão temporal.

## Resultado dos gates

- Suite: **84/84 passed**, 0 failed, 0 skipped.
- Lint de diff: limpo.
- Fixtures A–H: regenerados com os mesmos dados e `as_of` congelado em `2026-08-27T00:00:00Z`.
- Os artefatos before/after ficam fora do repositório, em `Documents/ChatGPT/Astrology/v4-final-quality-*`, para não publicar relatórios de fixtures junto do skill.

## Alterações que sobreviveram à auditoria

1. `ChartSignature` é agora upstream do `NarrativePlanner`. Um modo central exige corpo estrutural que conecte três ou mais sínteses; caso contrário o plano é distribuído. O renderer preserva a ordem do planner, não apenas filtra a lista de themes.
2. A abertura nasce da assinatura e da primeira síntese priorizada por ela. O fixture A abre pela arquitetura Jupiter/Sun; o fixture D, sem hora conhecida, declara centros distribuídos sem uma história totalizante.
3. O fallback genérico recebe átomos de função planetária e dinâmica de aspecto. Mercury–Uranus e Venus–Uranus não recebem mais a mesma dedução por conterem Uranus.
4. Trine/sextile e square/opposition/quincunx são registrados como geometrias de baixa resistência ou fricção/polaridade; a síntese decide a valência contextual.
5. O relatório executivo passa de tabela de themes para arquitetura → dinâmicas → áreas prioritárias → capítulo atual → experimento. A tabela deixou de organizar a leitura principal.
6. Áreas concretas usam hierarchy e prioridades da assinatura; uma casa vazia pode subir por regência estrutural.
7. `orb_entry_at` e `orb_exit_at` são refinados por busca binária a 0,0001°. `exact_at` só existe quando a raiz do aspecto é demonstrada no ramo geométrico; oposição no cusp de 180° permanece `closest_approach` mesmo com orbe mínimo zero.
8. O workflow premium manual tem três comandos/gates: pacote, Synthesis Judge e Narrative Judge. O último declara explicitamente que a aprovação High é uma atestação semântica, não “prova” determinística.

## Evidência da assinatura

| Fixture | Modo | Corpos estruturais | Temas escolhidos pelo plano | Razão |
|---|---|---|---|---|
| A | central | Jupiter, Sun, Moon | competence, security_exploration, transformation | Sun conecta 5 sínteses, Jupiter 3 e Moon 4; os temas selecionados cobrem esse núcleo. |
| D | distributed | Mercury, Jupiter, Moon, Neptune | security_exploration, reason_feeling, stability_change, transformation | nenhum corpo estrutural conecta três sínteses; hora desconhecida também bloqueia casas/ângulos. |
| E | central | Moon | spirituality, reason_feeling, transformation | Moon conecta 5 sínteses e organiza a abertura; as áreas são qualificadas por contextos seguros. |

## Timing: validação de honestidade

No fixture A, `Jupiter quincunx Neptune` tem raiz refinada: `exact_at=2026-08-28T15:54:50+00:00`, com bordas de orbe `2026-08-23T23:31:20+00:00` e `2026-09-02T09:50:21+00:00`.

No mesmo fixture, `Jupiter opposition IC` atingiu `minimum_orb=0.0`, mas `perfected=false` e `exact_at=null`: a geometria de oposição não foi tratada como raiz branch-safe. Isso é intencional e mais honesto que uma data aparentemente exata.

## Before / after editorial

### A — assinatura central

Antes: “O eixo inicial liga transformação a competência e estrutura.”

Depois: “A arquitetura deste mapa se organiza sobretudo em torno de Jupiter, Sol… abrindo primeiro o tema competence.” A abertura passa a explicar por que estas dinâmicas entram primeiro e liga o Sol/Lua aos signos e funções envolvidas.

### D — centros distribuídos / hora desconhecida

Antes: “O eixo inicial liga segurança e exploração a razão e sentimento.”

Depois: “Este mapa não pede uma explicação única: Mercury, Jupiter, Moon formam centros diferentes…” A versão final preserva quatro threads sem fingir uma causa única e não usa casas na leitura.

### E — assinatura lunar central

Antes: a abertura ligava “meaning and transcendence” a “competence and structure” por ranking de themes.

Depois: “This chart's architecture is organised chiefly around Moon… opening first through autonomy and closeness.” Isso fornece a lógica estrutural antes das categorias editoriais.

## Métricas observadas, não otimizadas cegamente

| Métrica | Baseline V4 | Final patch | Leitura honesta |
|---|---:|---:|---|
| Testes | 78/78 | 84/84 | Foram adicionados testes de assinatura, ablação, semântica, orbe e workflow premium. |
| Reuso literal interpretativo executivo A–D | 0 | 0 | Sem regressão. |
| Similaridade semântica heurística executiva A–D | 1 | 2 | Detector por sobreposição de tokens; a nova abertura contém mais linguagem estrutural comum, apesar de fatores distintos. |
| Reuso literal interpretativo deep A–D | 0 | 0 | Sem regressão. |
| Similaridade semântica heurística deep A–D | 3 | 5 | Ainda há frases de theme/move determinístico parecidas em mapas que compartilham fatores. Isso permanece risco do fallback, não foi escondido. |
| Tempo médio executivo A–H | 1,75 min | 1,39 min | Mais curto, mas continua abaixo da meta editorial de 2–4 min. |
| Tempo médio deep A–H | 5,83 min | 6,02 min | Próximo da meta de 6–10 min. |
| Jargão visível executivo A–H | 0,38 hits | 0 | A técnica ficou fora do corpo principal. |
| Vazamento de casas inseguras | 0 | 0 | Coberto por gates existentes e fixture D. |
| Erros de cluster temporal | 0 | 0 | A patch não reabriu o agrupamento por activation instance. |

O teste de swap continua um pré-screen heurístico: não é evidência de que uma leitura “acertou” uma pessoa. A discriminação cega real requer leitores humanos e localização idêntica entre iscas.

## Avaliação brutal

| Dimensão | Nota |
|---|---:|
| Correção técnica | 9.3/10 |
| Especificidade semântica do fallback | 7.8/10 |
| Síntese holística | 8.6/10 |
| Individualidade | 8.0/10 |
| UX do relatório | 8.4/10 |
| Honestidade do timing | 9.4/10 |
| Rastreabilidade | 9.2/10 |
| Workflow High | 8.5/10 |
| Prontidão para beta Reddit | 8.4/10 |

**Maior fraqueza restante:** sem o passe manual Sol High, a prosa profunda ainda pode reutilizar movimentos de theme em mapas que compartilham uma mesma configuração, mesmo quando a assinatura e a evidência são diferentes.

**Próxima ação:** iniciar beta fechado com leitores humanos usando obrigatoriamente o workflow premium Sol High e recolher feedback estruturado de compreensão, especificidade e abandono.
