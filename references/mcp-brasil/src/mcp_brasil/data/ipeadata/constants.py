"""Constants for the IPEADATA feature."""

from __future__ import annotations

IPEADATA_API_BASE = "http://ipeadata.gov.br/api/odata4"

# Themes — used for discovery
TEMAS = {
    "macroeconomico": "Macroeconômico",
    "regional": "Regional",
    "social": "Social",
}

# Popular series (SERCODIGO → descrição) — curadoria verificada
SERIES_POPULARES: dict[str, str] = {
    "SGS12_IBCBR12": "IBC-Br — Índice de Atividade Econômica do BC (mensal)",
    "SGS12_IBCBRDESSAZ12": "IBC-Br — dessazonalizado (mensal)",
    "BM12_TJOVER12": "Taxa de juros — Selic over (mensal)",
    "PRECOS12_IPCA12": "IPCA — Índice de Preços ao Consumidor Amplo (mensal)",
    "BM12_TJCDI12": "CDI — Taxa média diária (mensal)",
    "BM12_ERC12": "Taxa de câmbio comercial para venda — R$/US$ (mensal)",
}
