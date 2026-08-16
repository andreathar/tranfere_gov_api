"""Constants for the anp_precos dataset feature."""

from __future__ import annotations

ANP_BASE = "https://www.gov.br/anp/pt-br/centrais-de-conteudo/dados-abertos/arquivos/shpc/dsan"

# Fuel type → base filename (without year/month)
FUEL_FILE_PREFIX: dict[str, str] = {
    "gasolina_etanol": "precos-gasolina-etanol",
    "diesel_gnv": "precos-diesel-gnv",
    "glp": "precos-glp",
}

# Ano coberto pelo pilot (ajustável via env no futuro)
ANO_COBERTURA = 2024
MESES_COBERTOS = tuple(range(1, 13))  # 01..12


def _build_sources() -> tuple[tuple[str, str | None, str], ...]:
    """Generate (url, zip_member, suffix) tuples for each month and fuel type."""
    out: list[tuple[str, str | None, str]] = []
    for fuel, prefix in FUEL_FILE_PREFIX.items():
        for mes in MESES_COBERTOS:
            url = f"{ANP_BASE}/{ANO_COBERTURA}/{prefix}-{mes:02d}.csv"
            suffix = f"{fuel}_{ANO_COBERTURA}_{mes:02d}"
            out.append((url, None, suffix))
    return tuple(out)


SOURCES = _build_sources()

# Nomes renomeados das colunas (ordem idêntica à do CSV fonte)
COLUMN_NAMES: list[str] = [
    "regiao",
    "estado",
    "municipio",
    "revenda",
    "cnpj_revenda",
    "rua",
    "numero",
    "complemento",
    "bairro",
    "cep",
    "produto",
    "data_coleta",
    "valor_venda",
    "valor_compra",
    "unidade",
    "bandeira",
]

# Colunas filtráveis via valores_distintos_anp
COLUNAS_DISTINCT_PERMITIDAS: frozenset[str] = frozenset(
    {"produto", "bandeira", "estado", "regiao", "unidade"}
)

# Produtos típicos encontrados na base (para referência — pode haver variações)
PRODUTOS_COMUNS: tuple[str, ...] = (
    "GASOLINA",
    "GASOLINA ADITIVADA",
    "ETANOL",
    "DIESEL",
    "DIESEL S10",
    "GNV",
    "GLP",
)
