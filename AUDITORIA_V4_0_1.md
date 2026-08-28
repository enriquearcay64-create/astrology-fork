# Auditoria V4.0.1 — qualidade e orquestração premium

Base comparada: `7d339a0ddf7d4be3317e4a21bee1ffed04bfd492`.

Esta é uma patch curta de integridade e de caminho editorial. Não adiciona técnica, ponto, aspecto, casa ou método temporal.

## O que foi verificado

- Suíte local: **89/89 testes passaram**; não há testes ignorados nem falhas conhecidas.
- Cinco cartas UX congeladas foram geradas com o mesmo `as_of` e horizonte de 366 dias: A, B, C, E e G.
- A carta D, de hora desconhecida e assinatura `distributed`, foi testada separadamente: continua produzindo a leitura segura limitada e é corretamente recusada pelo caminho premium beta.
- O smoke local exerce cálculo, pacote, assinatura, sínteses, hashes e guards. Ele não afirma ter chamado Sol High automaticamente: por desenho, nenhuma API ou modelo é chamado pelo Python. O passe cognitivo real acontece quando o Codex segue `SKILL.md` em um pedido premium.

## Integridade corrigida

1. **Cadeia premium fechada.** `packet_id`, hash das sínteses, hash do rascunho e hash do relatório final viajam de Author a Reviewer e à publicação. Mistura de execução, bundle, rascunho ou relatório bloqueia.
2. **Proveniência de síntese.** Motifs precisam pertencer às claims citadas; fatores primários precisam ser evidência dessas mesmas claims; operações precisam corresponder à geometria/fator; uma fonte fraca não pode virar `strong` sem suporte estrutural adicional.
3. **Timing tipado.** Ativações seguras entram no namespace `timing.activation.*`; referências inventadas bloqueiam. `exact_at` de ciclos só é preenchido quando há raiz refinada; aproximação permanece aproximação.
4. **Fonte por parágrafo.** Todo parágrafo substantivo recebe hash e IDs de síntese/timing aprovados. Heading, aviso e estrutura curta não exigem mapeamento.
5. **ChartSignature.** A regência de dois signos não infla mais a centralidade de Mercúrio/Vênus/Marte/Júpiter/Saturno. A autoridade tópica de uma casa não devolve o score completo do planeta a ela. Contagens internas permanecem no apêndice, fora da prosa do cliente.
6. **Intervalos de desenvolvimento.** Agrupamento agora conserva `max_end_seen`; A 2025–2030, B 2026–2027 e C 2029–2031 formam corretamente um intervalo contínuo.
7. **Localização.** Os seeds que associavam país a uma situação humana específica foram removidos. Localização pode alterar apresentação, não psicologia nem interpretação.
8. **Hora desconhecida.** O beta premium exige hora conhecida. A alternativa segura continua disponível, sem casas/ângulos/timing tópico inseguros.

## Evidência dos fixtures

| Fixture | Assinatura | Corpos estruturais iniciais | Temas escolhidos | Situação técnica |
| --- | --- | --- | --- | --- |
| A | `central` | Júpiter, Sol, Lua | competência; transformação; segurança/exploração | Placidus disponível |
| B | `central` | Marte, Netuno, Sol | significado; transformação; segurança/exploração | stress test ±30 min cruza ASC; divulgado, não usado como certeza |
| C | `central` | Saturno, Sol, Mercúrio | cuidado; propósito; significado | inglês direto, sem mudança por perfil do leitor |
| E | `central` | Lua, Júpiter, Mercúrio | significado; transformação; razão/sentimento | Placidus indisponível, sem falsa convergência |
| G | `central` | Urano, Saturno, Vênus | autonomia/proximidade; estabilidade/mudança; significado | stress test ±5 min cruza ASC; topologia não é tratada como certeza extra |
| D (gate) | `distributed` | — | até quatro, sem narrativa totalizante | hora desconhecida: leitura limitada passa; premium bloqueado |

## Before/after verificável

Os números abaixo usam a mesma seleção A/B/C/E/G, Localization congelada e o mesmo protocolo. Similaridade é um pré-filtro lexical/por sobreposição, não “prova semântica”.

| Métrica | V4 base | V4.0.1 |
| --- | ---: | ---: |
| Executive — palavras médias | 318 | 397 |
| Executive — minutos médios a 220 ppm | 1,44 | 1,78 |
| Executive — frases interpretativas idênticas reutilizadas | 1 | 0 |
| Executive — sentenças potencialmente intercambiáveis | 7 | 6 |
| Deep — frases interpretativas idênticas reutilizadas | 2 | 1 |
| Deep — sentenças potencialmente intercambiáveis | 12 | 9 |
| Falhas técnicas conhecidas no conjunto | 0 | 0 |
| Vazamento de casa insegura | 0 | 0 |
| Clusters temporais incorretos no teste regressivo | 1 cenário protegido | 0 |

A abertura A, por exemplo, deixou de exibir `Júpiter (3), Sol (5)` e agora traduz a relação estrutural entre crescimento/sentido e direção pessoal. A leitura executiva ganhou uma ponte interpretativa substantiva, não uma seção ou tabela adicional. O alvo editorial de 2–3 minutos continua sendo uma faixa: estes mapas específicos ficam em 1,7–1,9 min no renderer local e o Author High deve completar a densidade com síntese individual, não com preenchimento.

## Auditoria editorial dos cinco rascunhos locais

O renderer local continua sendo deliberadamente um fallback/debug. Ele é adequado para conservar estrutura e para o Reviewer comparar, mas não deve ser apresentado como o produto premium.

| Fixture | Diagnóstico do rascunho | Correção que o Reviewer premium deve aplicar |
| --- | --- | --- |
| A | A abertura é específica, mas competência e transformação reaparecem perto demais. | Fundir a passagem final em uma escolha concreta que una construção e mudança. |
| B | A distinção entre imaginação e critério está clara; o aviso de sensibilidade não deve dominar. | Manter a cautela em uma única nota e usar o conflito Sol–Netuno como mecanismo, não como rótulo. |
| C | Funciona para um leitor cético porque promete reflexão, não verdade factual. | Reduzir técnica residual e preservar o exemplo de escutar antes de solucionar como hipótese, não biografia. |
| E | A ausência de Placidus está corretamente silenciosa no corpo principal. | Não tentar compensar a falta com linguagem de “convergência”; priorizar a combinação Marte–Netuno já autorizada. |
| G | É a mais individual entre as cinco; autonomia/proximidade e estabilidade/mudança se conectam. | Evitar repetir “espaço” em todas as seções e preservar a fronteira de ASC como condicional. |

O passe de Reviewer é uma etapa cognitiva exigida antes da publicação: ele pode reescrever, cortar, fundir e reorganizar diretamente. A CI garante que, depois disso, a versão publicada seja exatamente a que foi revisada e continue rastreável; ela não declara que um teste de tokens substitui leitura humana.

## Limite honesto

O ponto ainda abaixo de 10/10 não é cálculo: é a validação com leitores reais. O fallback local ainda tem cadência mais uniforme do que um relatório premium de Sol High, e similaridade heurística detecta risco, mas não mede percepção humana.

## Conclusão

O caminho normal agora é um pedido único no Codex: cálculo seguro → Author High → Provenance Guard → Reviewer/Editor High → Publication Guard → relatório. A próxima ação indicada, após esta patch, é **beta humano com consentimento**, não nova feature.
