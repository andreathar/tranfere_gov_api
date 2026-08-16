"""Constants for the TCU feature."""

# API base URLs (múltiplos domínios)
TCU_DADOS_ABERTOS_BASE = "https://dados-abertos.apps.tcu.gov.br/api"
TCU_CONTAS_ORDS_BASE = "https://contas.tcu.gov.br/ords"
TCU_CERTIDOES_BASE = "https://certidoes-apf.apps.tcu.gov.br/api/rest/publico"
TCU_DIVIDA_BASE = "https://divida.apps.tcu.gov.br/api/publico"
TCU_CONTRATA_BASE = "https://contas.tcu.gov.br/contrata2RS/api/publico"

# Endpoints — dados-abertos
ACORDAOS_URL = f"{TCU_DADOS_ABERTOS_BASE}/acordao/recupera-acordaos"
PAUTAS_SESSAO_URL = f"{TCU_DADOS_ABERTOS_BASE}/pautassessao"
CADIRREG_URL = f"{TCU_DADOS_ABERTOS_BASE}/recuperapessoacadirreg"

# Endpoints — ORDS (Oracle REST Data Services)
INABILITADOS_URL = f"{TCU_CONTAS_ORDS_BASE}/condenacao/consulta/inabilitados"
INIDONEOS_URL = f"{TCU_CONTAS_ORDS_BASE}/condenacao/consulta/inidoneos"
PEDIDOS_CONGRESSO_URL = f"{TCU_CONTAS_ORDS_BASE}/api/publica/scn/pedidos_congresso"

# Endpoints — Certidões APF
TIPOS_CERTIDOES_URL = f"{TCU_CERTIDOES_BASE}/tipos-certidoes"
CERTIDOES_URL = f"{TCU_CERTIDOES_BASE}/certidoes"

# Endpoints — Calculadora de débito
CALCULAR_DEBITO_URL = f"{TCU_DIVIDA_BASE}/calculadora/calcular-saldos-debito"

# Endpoints — Termos contratuais
TERMOS_CONTRATUAIS_URL = f"{TCU_CONTRATA_BASE}/termos-contratuais"

# Colegiados do TCU
COLEGIADOS = ["Plenário", "1ª Câmara", "2ª Câmara"]

# Situações de acórdãos
SITUACOES_ACORDAO = ["OFICIALIZADO", "SIGILOSO", "INVALIDADO"]
