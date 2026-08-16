"""Constants for the INPE feature."""

QUEIMADAS_API = "https://terrabrasilis.dpi.inpe.br/queimadas/bdqueimadas-data-service"
TERRABRASILIS_API = "https://terrabrasilis.dpi.inpe.br/business-api"

FOCOS_URL = f"{QUEIMADAS_API}/focos"
SATELITES_URL = f"{QUEIMADAS_API}/satelites"
DETER_URL = f"{TERRABRASILIS_API}/deter"
PRODES_URL = f"{TERRABRASILIS_API}/prodes"

DEFAULT_LIMIT = 50

BIOMAS = {
    "amazonia": "Amazônia",
    "cerrado": "Cerrado",
    "mata_atlantica": "Mata Atlântica",
    "caatinga": "Caatinga",
    "pampa": "Pampa",
    "pantanal": "Pantanal",
}

ESTADOS_AMAZONIA_LEGAL = ["AC", "AM", "AP", "MA", "MT", "PA", "RO", "RR", "TO"]
