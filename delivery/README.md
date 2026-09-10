# Renderer local de entrega

Usa somente arquivos e metadados explícitos do cliente atual. Não importa builders antigos, não calcula astrologia e não aprova proveniência. Skill e guards continuam sendo a autoridade de produção.

Comando no runtime local:

```
python delivery/render.py /caminho/do/run/delivery.json
```

Smoke test neutro, sem dados de cliente:

```
python delivery/smoke_test.py
```

O JSON aceita `reading`, `appendix` (caminhos relativos ao JSON), `source_sha256`, `appendix_sha256`, `display_name`, `metadata` (lista de linhas), `output_dir`, `report_filename`, `appendix_filename` e `highlights` opcional. Os dois nomes devem ser basenames PDF distintos. Usar os arquivos finais do próprio run; conservar o original aprovado e sua linhagem.

Instale as dependências opcionais com `pip install -e '.[delivery]'` e o Poppler (`pdftoppm`). O renderer procura Caladea/Carlito no runtime Codex, em `ASTROLOGY_DELIVERY_FONT_DIR` e no caminho Linux usual; sem esses arquivos, usa Times/Helvetica. `CODEX_WORKSPACE_DEPENDENCIES` e `ASTROLOGY_PDFTOPPM` permitem indicar explicitamente o runtime e o executável de renderização. O fallback preserva funcionamento e legibilidade, mas pode alterar paginação; qualquer ambiente precisa fazer seu próprio QA visual.

`highlights` mapeia SHA-256 do texto completo de um parágrafo de apresentação para `example` ou `quote`. A apresentação reúne linhas do parágrafo com espaços; esses hashes são exclusivamente de layout, não substituem os hashes canônicos do guard. Não corta frases nem insere interpretação: o parágrafo inteiro recebe estilo, na mesma posição e uma única vez. H3 previamente aprovado fornece microtítulos. O renderer preserva introdução, sequência das seções e avisos presentes na fonte.

O arquivo `qa.json` identifica os PDFs exatos por caminho e hash, informa geometria e aponta para um diretório novo de imagens. QA de layout não equivale a Publication Guard. Inspecionar todas as páginas antes de entregar, incluindo nomes, datas e apêndice. Não passar dados de outro cliente para o renderer.

`introduction_style` aceita `body` (padrão) ou `small`. A segunda opção reduz apenas a escala da orientação antes do primeiro H2; não corta nem substitui a introdução contratual. Retirar uma quebra forçada depois da introdução permite que a abertura individual comece na mesma página quando houver espaço. Isso não implementa uma introdução contratual mais curta.

`pull_quotes` mapeia o hash de um parágrafo para uma frase literal e única dentro dele. O renderer apresenta antes/frase/depois em ordem, sem repetir a frase. Não combinar com `highlights` no mesmo parágrafo. O QA recompõe o texto extraído para conferir preservação.

`example_excerpts` usa a mesma regra de trecho literal único, com caixa “Na prática” e corpo sem serifa. Não aceita conflito com `pull_quotes` ou `highlights` no mesmo parágrafo. Permite distinguir a cena hipotética da explicação técnica sem reescrever nenhuma delas; a escolha do trecho deve ser feita após revisão do texto aprovado.

`technical_table_widths` aceita larguras em pontos, indexadas pelo cabeçalho completo unido por `|` (por exemplo, `Aspecto|Orbe|Movimento`). O número de larguras deve corresponder às colunas e sua soma ser 463. Cabeçalhos diferentes continuam usando colunas iguais. Não altera dados nem ordem das linhas.

Os H2 técnicos usam escala própria de consulta (19/23 pontos), sem reduzir o corpo das tabelas. `page_break_before` também aceita títulos técnicos existentes, para reunir título, explicação e tabela em páginas planejadas. Conferir novamente o sumário e ambos os PDFs depois dessas escolhas.

O apêndice de consulta pode ser um derivado público do apêndice canônico, desde que seu processo registre as fontes do mesmo cliente, traduções e escolhas, e confira valores e datas. Manter o canônico intacto no pacote do operador. Essa camada pública não herda aprovação de narrativa do Publication Guard.

`period_overview` opcional recebe `before_heading` (H2 existente), `note` e `rows` (três colunas por linha, incluindo cabeçalho). Essa superfície de consulta é externa à narrativa canônica: conferir cada célula contra dados determinísticos e expressões aprovadas do mesmo run, registrar essa conferência no pacote editorial e não atribuir ao guard a aprovação dessa montagem. O renderer apenas apresenta as células; não seleciona interpretações. `page_break_before` permite quebras antes de títulos existentes, sem mudar seu texto.

## Decisão para a próxima leitura

O acabamento de escrita deve acontecer no Author/Reviewer antes da aprovação final. Cards são estilos aplicados a parágrafos completos. Resumos adicionais, títulos interpretativos novos e seleção de frases não são mera decoração.

A página temporal da próxima leitura deve ser preparada como superfície de consulta separada, a partir dos dados determinísticos do cliente e de expressões já aprovadas. Tabelas só no apêndice/superfície não narrativa; não inserir tabelas na narrativa canônica. A montagem dessa página e dos cartões de abertura exige seleção editorial do mapa atual, não automação por palavras-chave. O renderer base não inventa nem seleciona esses conteúdos; a composição será feita com os dados do novo run, sob a mesma revisão visual. A referência v3 não deve entrar no contexto generativo.

## Limites conhecidos

Fontes e Poppler dependem do runtime local documentado, não é um pacote portátil. O parser é de apresentação, não uma réplica do parser de produção. Parágrafos muito longos em cards podem não caber; nesse caso retirar o destaque ou ajustar apenas a diagramação, sem truncar conteúdo. Nenhuma geração nova foi realizada para preparar este renderer.
