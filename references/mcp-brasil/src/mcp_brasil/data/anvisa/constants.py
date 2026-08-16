"""Constants for the ANVISA feature."""

# Bulário Eletrônico API (reverse-engineered from frontend at consultas.anvisa.gov.br)
BULARIO_API_BASE = "https://consultas.anvisa.gov.br/api/consulta"

BULARIO_BUSCA_URL = f"{BULARIO_API_BASE}/bulario"
BULARIO_MEDICAMENTO_URL = f"{BULARIO_API_BASE}/bulario/medicamento"

# Rate limiting: 1 request per second to be respectful
RATE_LIMIT_DELAY = 1.0

# Default pagination
DEFAULT_LIMIT = 10
MAX_LIMIT = 100

# Categorias regulatórias de medicamentos no Brasil
CATEGORIAS_MEDICAMENTO: dict[str, str] = {
    "1": "Novo",
    "2": "Genérico",
    "3": "Similar",
    "4": "Biológico",
    "5": "Específico",
    "6": "Fitoterápico",
    "7": "Dinamizado",
    "8": "Radiofármaco",
}

# Tipos de bula
TIPOS_BULA: dict[str, str] = {
    "PACIENTE": "Bula do Paciente",
    "PROFISSIONAL": "Bula do Profissional de Saúde",
}

# Seções padrão de uma bula de medicamento
SECOES_BULA: list[str] = [
    "Identificação do medicamento",
    "Informações ao paciente",
    "Indicações",
    "Contraindicações",
    "Advertências e precauções",
    "Interações medicamentosas",
    "Posologia e modo de usar",
    "Reações adversas",
    "Superdose",
    "Armazenamento",
]
