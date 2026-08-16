"""Constants for the Saúde feature."""

SAUDE_API_BASE = "https://apidadosabertos.saude.gov.br"
CNES_API_BASE = f"{SAUDE_API_BASE}/cnes"

ESTABELECIMENTOS_URL = f"{CNES_API_BASE}/estabelecimentos"
TIPOS_URL = f"{CNES_API_BASE}/tipounidades"
LEITOS_URL = f"{SAUDE_API_BASE}/assistencia-a-saude/hospitais-e-leitos"

DEFAULT_LIMIT = 20
MAX_LIMIT = 20  # API enforces max 20 for estabelecimentos
MAX_LIMIT_LEITOS = 1000  # API allows up to 1000 for hospitais-e-leitos

# Códigos de tipo de unidade para urgência/emergência (CNES)
TIPOS_URGENCIA: dict[str, str] = {
    "36": "Clínica/Centro de Especialidade",
    "39": "Unidade de Serviço de Apoio de Diagnose e Terapia",
    "40": "Unidade Móvel Terrestre",
    "42": "Unidade Móvel de Nível Pré-Hospitalar na Área de Urgência",
    "73": "Pronto Atendimento",
    "74": "Polo Academia da Saúde",
    "76": "Central de Regulação Médica das Urgências",
}

# ---------------------------------------------------------------------------
# Epidemiologia — InfoDengue / InfoGripe / DATASUS / SINAN
# ---------------------------------------------------------------------------

INFODENGUE_API_BASE = "https://info.dengue.mat.br/api/alertcity"

# CSV com alertas semanais do InfoGripe (Fiocruz)
INFOGRIPE_ALERTA_URL = (
    "https://gitlab.procc.fiocruz.br/mave/repo/-/raw/master/Dados/InfoGripe/atual_SRAG_hosp_se.csv"
)

# Doenças monitoradas pelo InfoDengue (parâmetro disease na API)
DOENCAS_INFODENGUE: dict[str, str] = {
    "dengue": "Dengue",
    "chikungunya": "Chikungunya",
    "zika": "Zika",
}

# Níveis de alerta do InfoDengue (1-4)
NIVEIS_ALERTA_DENGUE: dict[int, str] = {
    1: "Verde",
    2: "Amarelo",
    3: "Laranja",
    4: "Vermelho",
}

# Bases de dados do DATASUS (catálogo de referência)
BASES_DATASUS: list[dict[str, str]] = [
    {
        "sigla": "SIM",
        "nome": "Sistema de Informações sobre Mortalidade",
        "descricao": "Registros de óbitos com causa, local, idade e CID-10.",
        "cobertura": "1979-presente",
        "dimensoes": "Causa, município, idade, sexo, ano",
    },
    {
        "sigla": "SINASC",
        "nome": "Sistema de Informações sobre Nascidos Vivos",
        "descricao": "Declarações de nascidos vivos com peso, Apgar, tipo de parto.",
        "cobertura": "1994-presente",
        "dimensoes": "Município, peso, Apgar, tipo de parto, idade da mãe",
    },
    {
        "sigla": "SIH",
        "nome": "Sistema de Informações Hospitalares do SUS",
        "descricao": "Autorizações de internação hospitalar (AIH) no SUS.",
        "cobertura": "2008-presente",
        "dimensoes": "Procedimento, CID, município, valor, permanência",
    },
    {
        "sigla": "SIA",
        "nome": "Sistema de Informações Ambulatoriais do SUS",
        "descricao": "Produção ambulatorial registrada no SUS.",
        "cobertura": "2008-presente",
        "dimensoes": "Procedimento, CBO, município, quantidade",
    },
    {
        "sigla": "CNES",
        "nome": "Cadastro Nacional de Estabelecimentos de Saúde",
        "descricao": "Estabelecimentos, profissionais, equipamentos e leitos.",
        "cobertura": "2005-presente",
        "dimensoes": "Tipo, município, profissionais, leitos",
    },
    {
        "sigla": "SINAN",
        "nome": "Sistema de Informação de Agravos de Notificação",
        "descricao": "Notificação compulsória de doenças e agravos.",
        "cobertura": "2007-presente",
        "dimensoes": "Agravo, município, semana epidemiológica, idade, sexo",
    },
    {
        "sigla": "PNI",
        "nome": "Programa Nacional de Imunizações",
        "descricao": "Doses aplicadas de vacinas por tipo, faixa etária e local.",
        "cobertura": "2013-presente",
        "dimensoes": "Imunobiológico, dose, município, faixa etária",
    },
    {
        "sigla": "CIHA",
        "nome": "Comunicação de Informação Hospitalar e Ambulatorial",
        "descricao": "Atendimentos hospitalares e ambulatoriais não SUS.",
        "cobertura": "2008-presente",
        "dimensoes": "Procedimento, CID, município, caráter de atendimento",
    },
    {
        "sigla": "SIH-RD",
        "nome": "AIH Reduzida",
        "descricao": "Versão compacta das AIH com dados principais da internação.",
        "cobertura": "1992-presente",
        "dimensoes": "Procedimento, CID, município, valor, dias",
    },
]

# Doenças de notificação compulsória — SINAN (baseado no PySUS)
DOENCAS_SINAN: list[dict[str, str]] = [
    {
        "codigo": "ACBI",
        "nome": "Acidente de trabalho com exposição a material biológico",
        "categoria": "Ocupacional",
    },
    {"codigo": "ACGR", "nome": "Acidente de trabalho grave", "categoria": "Ocupacional"},
    {"codigo": "ANIM", "nome": "Acidente por animais peçonhentos", "categoria": "Zoonose"},
    {"codigo": "BOTU", "nome": "Botulismo", "categoria": "Alimentar"},
    {"codigo": "CANC", "nome": "Câncer relacionado ao trabalho", "categoria": "Ocupacional"},
    {"codigo": "CHAG", "nome": "Doença de Chagas aguda", "categoria": "Parasitária"},
    {"codigo": "CHIK", "nome": "Chikungunya", "categoria": "Arbovirose"},
    {"codigo": "COLE", "nome": "Cólera", "categoria": "Alimentar"},
    {"codigo": "COQU", "nome": "Coqueluche", "categoria": "Respiratória"},
    {"codigo": "DENG", "nome": "Dengue", "categoria": "Arbovirose"},
    {"codigo": "DERM", "nome": "Dermatose ocupacional", "categoria": "Ocupacional"},
    {"codigo": "DIFT", "nome": "Difteria", "categoria": "Respiratória"},
    {"codigo": "DTA", "nome": "Doença transmitida por alimentos", "categoria": "Alimentar"},
    {"codigo": "ESQU", "nome": "Esquistossomose", "categoria": "Parasitária"},
    {"codigo": "EXAN", "nome": "Doença exantemática", "categoria": "Respiratória"},
    {"codigo": "FAMA", "nome": "Febre amarela", "categoria": "Arbovirose"},
    {"codigo": "FMAC", "nome": "Febre maculosa e rickettsioses", "categoria": "Zoonose"},
    {"codigo": "FTIF", "nome": "Febre tifoide", "categoria": "Alimentar"},
    {"codigo": "HANS", "nome": "Hanseníase", "categoria": "Infecciosa"},
    {"codigo": "HANT", "nome": "Hantavirose", "categoria": "Zoonose"},
    {"codigo": "HEPA", "nome": "Hepatites virais", "categoria": "Infecciosa"},
    {"codigo": "HIV", "nome": "HIV/AIDS", "categoria": "Infecciosa"},
    {"codigo": "IEXO", "nome": "Intoxicação exógena", "categoria": "Ocupacional"},
    {"codigo": "LEIP", "nome": "Leishmaniose tegumentar", "categoria": "Parasitária"},
    {"codigo": "LEIV", "nome": "Leishmaniose visceral", "categoria": "Parasitária"},
    {"codigo": "LEPT", "nome": "Leptospirose", "categoria": "Zoonose"},
    {"codigo": "LER", "nome": "LER/DORT", "categoria": "Ocupacional"},
    {"codigo": "MALA", "nome": "Malária", "categoria": "Parasitária"},
    {"codigo": "MENI", "nome": "Meningite", "categoria": "Respiratória"},
    {
        "codigo": "NTRA",
        "nome": "Notificação de transtorno mental relacionado ao trabalho",
        "categoria": "Ocupacional",
    },
    {
        "codigo": "PAIR",
        "nome": "Perda auditiva por ruído relacionada ao trabalho",
        "categoria": "Ocupacional",
    },
    {"codigo": "PEST", "nome": "Peste", "categoria": "Zoonose"},
    {
        "codigo": "PFAL",
        "nome": "Paralisia flácida aguda/Poliomielite",
        "categoria": "Respiratória",
    },
    {
        "codigo": "PNEU",
        "nome": "Pneumoconiose relacionada ao trabalho",
        "categoria": "Ocupacional",
    },
    {"codigo": "RAIV", "nome": "Raiva humana", "categoria": "Zoonose"},
    {"codigo": "ROTA", "nome": "Rotavírus", "categoria": "Alimentar"},
    {"codigo": "SARA", "nome": "Sarampo", "categoria": "Respiratória"},
    {"codigo": "SIFA", "nome": "Sífilis adquirida", "categoria": "Infecciosa"},
    {"codigo": "SIFC", "nome": "Sífilis congênita", "categoria": "Infecciosa"},
    {"codigo": "SIFG", "nome": "Sífilis em gestante", "categoria": "Infecciosa"},
    {"codigo": "SRAG", "nome": "Síndrome respiratória aguda grave", "categoria": "Respiratória"},
    {"codigo": "TETA", "nome": "Tétano acidental", "categoria": "Infecciosa"},
    {"codigo": "TETN", "nome": "Tétano neonatal", "categoria": "Infecciosa"},
    {"codigo": "TUBE", "nome": "Tuberculose", "categoria": "Respiratória"},
    {"codigo": "VARC", "nome": "Varicela", "categoria": "Respiratória"},
    {"codigo": "VIOL", "nome": "Violência interpessoal/autoprovocada", "categoria": "Externa"},
    {"codigo": "ZIKA", "nome": "Zika vírus", "categoria": "Arbovirose"},
]
