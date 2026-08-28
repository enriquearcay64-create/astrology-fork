# Aviso de distribuição e licenciamento

Este skill inclui PySwissEph e três arquivos de efemérides Swiss Ephemeris. A distribuição deve cumprir AGPL-3.0-or-later ou usar uma licença profissional/comercial compatível adquirida do mantenedor. A presença deste aviso não concede liberação comercial.

Fontes oficiais: [licença do Swiss Ephemeris](https://github.com/aloistr/swisseph/blob/master/LICENSE), [documentação técnica e licenciamento](https://www.astro.com/swisseph/swisseph.pdf) e [pacote PySwissEph](https://pypi.org/project/pyswisseph/).

Antes de distribuir um produto proprietário:

1. decidir entre cumprir integralmente a AGPL e adquirir licença comercial;
2. confirmar que os arquivos de efemérides podem acompanhar a distribuição escolhida;
3. incluir os textos de licença e avisos exigidos pelo regime escolhido;
4. revisar o produto completo, inclusive qualquer serviço que interaja com o backend pela rede.

Para uso local, manter este aviso e `assets/ephe/SHA256SUMS`. O código verifica em runtime se Swiss Ephemeris foi realmente usado e recusa fallback silencioso.

`zoneinfo` usa os dados IANA fornecidos pelo sistema quando o pacote Python `tzdata` não está instalado. Nesse caso o payload registra `system-zoneinfo-unpinned`; reproduções estritas devem fixar a imagem do sistema ou instalar e registrar uma versão de `tzdata`.
