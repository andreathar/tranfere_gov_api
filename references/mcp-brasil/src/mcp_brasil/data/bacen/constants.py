"""Constants for the Bacen feature."""

BCB_API_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"

# Categorias disponíveis no catálogo
CATEGORIAS = [
    "Juros",
    "Inflação",
    "Câmbio",
    "Atividade Econômica",
    "Emprego",
    "Fiscal",
    "Setor Externo",
    "Crédito",
    "Agregados Monetários",
    "Poupança",
    "Índices de Mercado",
    "Expectativas",
]

# Indicadores-chave para consulta rápida (bcb_indicadores_atuais)
INDICADORES_CHAVE = [
    {"codigo": 432, "nome": "Selic (a.a.)"},
    {"codigo": 433, "nome": "IPCA mensal (%)"},
    {"codigo": 13522, "nome": "IPCA 12 meses (%)"},
    {"codigo": 3698, "nome": "Dólar PTAX (venda)"},
    {"codigo": 24364, "nome": "IBC-Br"},
]

# Boletim Focus — Expectativas do mercado
FOCUS_API_BASE = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata"
FOCUS_ENDPOINT = f"{FOCUS_API_BASE}/ExpectativasMercadoAnuais"

FOCUS_INDICADORES = ["IPCA", "IGP-M", "Selic", "Câmbio", "PIB"]
