"""Constants for the Fórum Brasileiro de Segurança Pública DSpace API."""

API_BASE = "https://publicacoes.forumseguranca.org.br/server/api"

# Endpoints
SEARCH_URL = f"{API_BASE}/discover/search/objects"
COMMUNITIES_URL = f"{API_BASE}/core/communities"
ITEM_URL = f"{API_BASE}/core/items"  # + /{uuid}

# Defaults
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50

# Comunidades temáticas (UUID → nome)
COMUNIDADES: dict[str, str] = {
    "ae73bbbc-55dd-45e0-8c3e-d351cfb96cb1": "Amazônia e segurança pública",
    "d044c00f-7c26-4249-8da4-336e953fe557": "Anuário Brasileiro de Segurança Pública",
    "068d69a5-d8e3-4d70-a218-22c60acdbf61": "Atlas da Violência",
    "1c2a4641-c556-47a0-99f2-06b819b8256e": "Democracia e segurança pública",
    "abda3c48-f977-478c-bdc2-227c2e6cd4c4": "Encontro do Fórum Brasileiro de Segurança Pública",
    "8f424527-643e-4d97-99f1-b27dbf593290": "Financiamento e gastos com segurança pública",
    "d03b839a-46fd-4662-a35c-ed29eaea4f3b": "Juventude e violência",
    "89db75a3-de54-400e-aa9b-05c445e6b910": "Políticas de segurança pública",
    "b5364b6c-25c5-4648-89b9-1d069065ae3f": "Prevenção da violência",
    "40a19dcb-00a6-420d-a2b8-11667ff12aad": "Produção de informação",
    "e7057d2b-1548-4671-a972-d97426d4f556": "Profissionais de segurança pública",
    "37400926-4625-44c1-84c5-fe1a4f316f2b": "Racismo e segurança pública",
    "da266936-812e-462d-b512-d6d50299886a": "Selo FBSP de Práticas Inovadoras - Casoteca",
    "028b6542-7b8b-4979-8cc6-80c1304c93c2": "Sistema prisional e encarceramento",
    "c5d1a51f-2757-45c2-95e2-d1d329d7293f": "Violência contra meninas e mulheres",
}
