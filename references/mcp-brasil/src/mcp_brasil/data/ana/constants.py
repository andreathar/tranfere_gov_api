"""Constants for the ANA feature."""

HIDROWEB_API = "https://www.snirh.gov.br/hidroweb/rest/api"
SAR_API = "https://www.ana.gov.br/sar0"

ESTACOES_URL = f"{HIDROWEB_API}/estacao/codigoestacao"
TELEMETRIA_URL = f"{HIDROWEB_API}/estacao/telemetrica"
RESERVATORIOS_URL = f"{SAR_API}/Medicao"

TIPOS_ESTACAO = {
    1: "Fluviométrica",
    2: "Pluviométrica",
}
