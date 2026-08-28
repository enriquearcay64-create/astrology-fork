# Auditoria V4 — qualidade, integridade e experiência

Data: 2026-08-28  
Branch: `v4-quality-pass`  
Princípio: **hard facts, soft synthesis, hard verification**.

## Resultado executivo

A V4 corrige os dois bloqueadores técnicos encontrados na auditoria anterior e desloca a interpretação de um renderer guiado por themes para uma cadeia rastreável: `SafeInterpretiveChart → ReasonedSynthesis → ChartSignature → NarrativePlanner → relatório`. Os cálculos continuam determinísticos; a síntese pode ser emergente, desde que cite factos fechados e passe por verificação.

O núcleo local passou de 73 para **78 testes**. A suíte UX tem oito cartas sintéticas deliberadamente diferentes, executadas em dois lotes reproduzíveis de quatro para respeitar o limite de execução: `v4-final3-A-D` e `v4-final-E-H` no diretório de auditoria local.

## Correções implementadas

1. **Vazamento de casas instáveis.** O renderer recebe apenas `SafeInterpretiveChart`. Incerteza declarada pode ocultar casas, regentes tópicos, Lots e profecções; um stress test contrafactual para hora declarada exata apenas divulga alta sensibilidade, sem fingir que a hora informada é incerta.
2. **Whole Sign + Placidus.** `robust_same_house` substitui a linguagem enganadora `convergence_strong`; não conta como evidência dupla. Divergências materiais são mostradas como domínios diferentes, sem síntese falsa. Indisponibilidade de Placidus é declarada explicitamente.
3. **Timing.** Cada janela agora conserva `closest_approach_at`, `minimum_orb`, `perfected`, `exact_at` somente quando há perfeição, entrada/saída de orbe e identidade de ciclo. Instâncias são separadas por ramo geométrico e ciclo direto–retrógrado–direto, não por uma lacuna arbitrária de dias. Saturn Return continua um rótulo, não evidência adicional.
4. **ReasonedSynthesis.** Cada unidade conserva claims, motivos, operações de composição, proposições derivadas, factores primários, modificadores, contrapesos e alternativa. O Synthesis Judge bloqueia ids inexistentes, proposições sem fonte, desconexão semântica e escalada biográfica. O contrato do Narrative Judge verifica a prosa humanizada separadamente.
5. **Planner e assinatura.** Referências cruzadas usam corpos em factors tipados; duas quadraturas diferentes já não são conectadas por conterem a palavra “square”. O relatório pode apresentar uma dinâmica central ou reconhecer uma carta distribuída, sem forçar cinco temas.
6. **Estrutura.** T-squares incluem ápice explícito. Stellia usam ids `position.<body>` que existem de facto no ledger.
7. **Editorial/localização.** A leitura executiva e profunda exibem 3–4 temas quando sustentados. Localização é um pequeno contexto aplicado a um exemplo do mapa, não substitui o exemplo, não escolhe theme e nunca produz psicologia cultural.
8. **CI.** Há workflow de GitHub para instalação e `pytest`.

## Before / After — métricas reais

Fonte: os três mapas UX comuns A–C; baseline em `baseline/`, depois em `v4-final3-A-D/`. A reutilização semântica é um detector por sobreposição lexical, não uma alegação de validade astrológica.

| Métrica (média A–C) | Antes | Depois |
|---|---:|---:|
| Executive: palavras / minutos | 432 / 2.0 | 381 / 1.7 |
| Executive: jargon | 0.7 | 0.3 |
| Executive: frases interpretativas literalmente reutilizadas | 6 | 0 |
| Executive: pares semanticamente intercambiáveis | 7 | 1 |
| Deep: palavras / minutos | 1.344 / 6.1 | 1.292 / 5.9 |
| Deep: pares redundantes visíveis por relatório | 5.0 | 1.3 |
| Deep: frases literalmente reutilizadas | 5 | 0* |
| Deep: pares semanticamente intercambiáveis | 7 | 3* |
| Deep: Barnum-risk semântico | 0.0 | 0.0 |
| Technical: palavras / minutos | 3.430 / 15.6 | 3.909 / 17.8 |
| Testes automatizados | 73 | 78 |
| Vazamento de casas instáveis | defeito observado | 0 nos fixtures de regressão |
| Erros de cluster temporal conhecidos | defeito observado | 0 nos fixtures A/B/C de timing |

\* As ocorrências restantes eram frases de navegação fixa; o filtro de QA v4 as exclui da prosa interpretativa. Restam três matches semânticos de revisão, sobretudo quando duas cartas realmente partilham Lua–Plutão/tema de transformação; eles não devem ser tratados como aprovação automática.

## Leitura como cliente

**Pontos fortes.** A primeira página começa pela dinâmica humana, não por metodologia; o apêndice continua ignorável; as dificuldades têm agência; a tabela de áreas é concreta; Whole Sign/Placidus só aparece quando altera a leitura. A carta de hora desconhecida não finge saber casas. A carta de latitude alta declara Placidus indisponível.

**Pontos a vigiar.** O fallback local ainda pode repetir cadência de “capacidade / cuidado / integração” quando vários themes partilham o mesmo registry. A leitura por Sol deve substituir essa prosa fallback pelo `ReasonedSynthesis` autorizado, mantendo os ids internos. O apêndice técnico ficou maior porque passou a expor proveniência; isto é aceitável para auditoria, mas não deve ser apresentado como leitura de cliente.

## Crítica brutal e nota

**Nota de engenharia local: 8.5/10.**

Não é 10/10 por quatro razões concretas:

1. O CLI local contém um fallback determinístico; ele prepara o pacote e as instruções para Sol, mas não invoca por si só GPT-5.6 Sol. Sem a passagem de síntese no Codex, ainda há traços de cadência template.
2. O Synthesis Judge semântico é heurístico. Ele bloqueia ataques simples, mas uma revisão por modelo continua necessária para equivalência semântica real depois da HumanizationPass.
3. A identidade do ciclo retrógrado é calculada a partir de estações próximas; precisa de fixtures adicionais validados contra efemérides para planetas lentos em bordas de estação.
4. A localização é segura e extensível, mas pequena. A forma ideal é o Sol criar contexto leve a partir do perfil fornecido, sem um catálogo cultural rígido.

O próximo passo para 9.5+ é ligar o `ReasoningPacket` ao Sol High dentro do fluxo Codex, exigir `ReasonedSynthesis` estruturada na resposta interna, aplicar o Narrative Judge ao texto e bloquear publicação em caso de diferença material. A nota 10 exigiria ainda avaliação editorial humana cega com leitores consentidos; testes internos medem software, não valor psicológico nem validade científica.
