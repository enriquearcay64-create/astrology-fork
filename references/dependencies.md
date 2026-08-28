# Dependências e licença

| Dependência | Versão | Finalidade | Licença / decisão |
|---|---:|---|---|
| PySwissEph | 2.10.3.2 | posições, casas, ângulos, eclipses | Swiss Ephemeris é AGPL-3.0-or-later ou requer licença comercial. Revisar antes de produto fechado/comercial. |
| Python zoneinfo | stdlib | fuso IANA local | Dados dependem do sistema/tzdata instalado. |
| PyYAML | 6.0.2 | dependência de desenvolvimento/validador | MIT. |
| pytest | 8.3.5 | dependência de desenvolvimento/testes | MIT. |

O skill não envia dados de nascimento automaticamente a qualquer serviço. Geocodificação externa é deliberadamente ausente: use coordenadas fornecidas ou uma base offline futura.

Os três arquivos empacotados cobrem 1800–2399 CE. Fora dessa faixa, o núcleo interrompe o cálculo e solicita as efemérides correspondentes; não faz fallback silencioso para uma fonte com outra precisão.

Leia [licensing-notice.md](licensing-notice.md) antes de distribuir. Verifique a integridade dos binários com `assets/ephe/SHA256SUMS`. Este pacote ainda não possui liberação jurídica para distribuição proprietária.

## Alternativas futuras

- Licença comercial do Swiss Ephemeris, caso a distribuição seja proprietária.
- Backend astronômico permissivo para posições, combinado com uma implementação de casas validada. Não substituir o backend sem uma suíte de paridade astronômica.
