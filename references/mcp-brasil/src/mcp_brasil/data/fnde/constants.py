"""Constants for the FNDE feature."""

# OData API base URL
FNDE_OLINDA_BASE = "https://www.fnde.gov.br/olinda-ide/servico"

# FUNDEB — Matrículas ponderadas para cálculo do fundo
FUNDEB_URL = f"{FNDE_OLINDA_BASE}/FUNDEB_Matriculas/versao/v1/odata/FUNDEBMatriculas"

# PNAE — Programa Nacional de Alimentação Escolar (alunos atendidos)
PNAE_URL = f"{FNDE_OLINDA_BASE}/PNAE_Numero_Alunos_Atendidos/versao/v1/odata/Alunos_Atendidos"

# PNLD — Programa Nacional do Livro e do Material Didático
PNLD_URL = f"{FNDE_OLINDA_BASE}/PNLD/versao/v1/odata/pdaPNLD"

# PNATE — Programa Nacional de Apoio ao Transporte do Escolar
PNATE_URL = f"{FNDE_OLINDA_BASE}/PNATE_Alunos_Atendidos/versao/v1/odata/PNATEAlunosAtendidos"

# Default OData query parameters
ODATA_FORMAT = "json"
ODATA_DEFAULT_TOP = 100
ODATA_MAX_TOP = 1000
