"""Constants for the SPU-Imoveis feature."""

SPU_IMOVEIS_API_BASE = "https://repositorio.dados.gov.br/seges/raio-x"
PATRIMONIO_UNIAO_CSV_URL = f"{SPU_IMOVEIS_API_BASE}/patrimonio-uniao.csv"
DATAPACKAGE_JSON_URL = f"{SPU_IMOVEIS_API_BASE}/datapackage.json"

# Cache TTL for the downloaded CSV (in seconds). The dataset is republished
# monthly, so 24h is comfortably fresh while avoiding repeated downloads.
CSV_CACHE_TTL_SECONDS = 24 * 3600

# CSV column names (from the Raio-X patrimonio-uniao dataset header)
COLUMNS: tuple[str, ...] = (
    "orgao_superior_codigo_siorg",
    "orgao_superior_nome",
    "orgao_superior_sigla",
    "orgao_codigo_siorg",
    "orgao_nome",
    "orgao_sigla",
    "orgao_como_no_raiox_nome",
    "orgao_como_no_raiox_sigla",
    "ano_mes_referencia",
    "regime_utilizacao",
    "tipo_destinacao",
    "tipo_imovel",
    "endereco",
    "municipio_nome",
    "municipio_cod_ibge",
    "uf",
    "metro_quadrado_area",
    "metro_quadrado_construida",
    "valor_imovel",
    "valor_aluguel",
)

# Common órgão superior siglas (used in filters)
ORGAO_SIGLAS: tuple[str, ...] = (
    "MGI",
    "MD",
    "MDA",
    "MEC",
    "MS",
    "MT",
    "MMA",
    "MIDR",
    "MPI",
    "MJSP",
    "PR",
    "MF",
    "MRE",
    "MCid",
    "MCT",
    "MCTI",
    "MINC",
    "MC",
    "MTur",
    "MP",
    "MDIC",
    "MME",
    "AGU",
    "CGU",
    "MPU",
)
