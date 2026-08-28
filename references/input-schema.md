# Schema de entrada local

```json
{
  "local_datetime": "1990-07-12T14:30:00",
  "timezone_name": "America/Sao_Paulo",
  "latitude": -23.5505,
  "longitude": -46.6333,
  "time_uncertainty_minutes": 5,
  "sensitivity_test_minutes": [5, 15, 30],
  "dst_fold": null,
  "birth_time_known": true,
  "place_label": "São Paulo, Brasil",
  "source": "user_provided",
  "localization_profile": {
    "preferred_language": "pt-BR",
    "current_country": "Brazil",
    "cultural_context": "Brazil",
    "source": "user_provided",
    "localization_level": "light"
  }
}
```

`timezone_name`, latitude e longitude são obrigatórios. `time_uncertainty_minutes` descreve a qualidade declarada do horário e aciona gates de interpretação em ± esse intervalo. `sensitivity_test_minutes` são stress tests contrafactuais: não rebaixam por si só uma hora declarada como exata, mas expõem fronteiras em que casas de Signo Inteiro ou Placidus devem ser omitidas ou apresentadas como condicionais. Em horário local ambíguo por DST, informar `dst_fold` como `0` ou `1`; o núcleo recusa escolher silenciosamente. Não derive país, idioma ou cultura do local de nascimento. Se o horário for aproximado, registre-o e trate ângulos/casas como sensíveis.

Quando a hora for desconhecida, usar `birth_time_known: false` e fornecer a data em `local_datetime`. O núcleo usa 12:00 local apenas como proxy técnico, compara 00:01 e 23:59 locais, retém somente aspectos presentes nos dois extremos e desabilita ASC, MC, casas, secto, Vertex e Lots. Corpos que percorrem mais de 1° no dia não podem servir como alvos natais precisos de timing. Trânsitos e ciclos restantes continuam disponíveis com rastreabilidade da exclusão.

Para Revolução Solar fora do local natal, declarar também:

```json
{"solar_return_location": {"latitude": 38.7223, "longitude": -9.1393}}
```

`preferred_language` aceita `pt-BR` ou uma variante inglesa como `en-US`. Localization altera somente apresentação e exemplos.
