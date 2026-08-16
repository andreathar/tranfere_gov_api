"""Constants for the INEP feature."""

# Base URL for INEP downloads
INEP_DOWNLOAD_BASE = "https://download.inep.gov.br"

# IDEB result files (XLSX)
IDEB_BASE = f"{INEP_DOWNLOAD_BASE}/ideb/resultados"

# IDEB etapas
IDEB_ETAPAS = {
    "anos_iniciais": "Anos Iniciais do Ensino Fundamental (1º ao 5º ano)",
    "anos_finais": "Anos Finais do Ensino Fundamental (6º ao 9º ano)",
    "ensino_medio": "Ensino Médio",
}

# IDEB níveis
IDEB_NIVEIS = {
    "escolas": "Por escola",
    "municipios": "Por município",
    "brasil": "Nacional",
    "regioes_ufs": "Por região e UF",
}

# IDEB URL patterns
IDEB_URLS = {
    "brasil": f"{IDEB_BASE}/divulgacao_brasil_ideb_{{ano}}.xlsx",
    "regioes_ufs": f"{IDEB_BASE}/divulgacao_regioes_ufs_ideb_{{ano}}.xlsx",
    "escolas": f"{IDEB_BASE}/divulgacao_{{etapa}}_escolas_{{ano}}.xlsx",
    "municipios": f"{IDEB_BASE}/divulgacao_{{etapa}}_municipios_{{ano}}.xlsx",
}

# Anos IDEB disponíveis (bienal: 2005-2023)
IDEB_ANOS = [2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023]

# Microdados download URLs
MICRODADOS_URLS = {
    "censo_escolar": f"{INEP_DOWNLOAD_BASE}/dados_abertos/microdados_censo_escolar_{{ano}}.zip",
    "enem": f"{INEP_DOWNLOAD_BASE}/microdados/microdados_enem_{{ano}}.zip",
    "saeb": f"{INEP_DOWNLOAD_BASE}/microdados/microdados_saeb_{{ano}}.zip",
    "censo_superior": (
        f"{INEP_DOWNLOAD_BASE}/microdados/microdados_censo_da_educacao_superior_{{ano}}.zip"
    ),
    "enade": f"{INEP_DOWNLOAD_BASE}/microdados/microdados_enade_{{ano}}.zip",
    "encceja": f"{INEP_DOWNLOAD_BASE}/microdados/microdados_encceja_{{ano}}.zip",
}

# Catálogo de microdados com anos disponíveis
CATALOGO_MICRODADOS: dict[str, dict[str, str | list[int]]] = {
    "censo_escolar": {
        "nome": "Censo Escolar da Educação Básica",
        "descricao": (
            "Dados de escolas, turmas, docentes e matrículas de toda a educação básica brasileira"
        ),
        "frequencia": "Anual",
        "anos_disponiveis": list(range(2007, 2025)),
    },
    "enem": {
        "nome": "Exame Nacional do Ensino Médio",
        "descricao": (
            "Participantes, notas por área de conhecimento, questionário socioeconômico"
        ),
        "frequencia": "Anual",
        "anos_disponiveis": list(range(1998, 2024)),
    },
    "saeb": {
        "nome": "Sistema de Avaliação da Educação Básica",
        "descricao": (
            "Proficiência em Língua Portuguesa e Matemática, "
            "questionários contextuais — base do cálculo do IDEB"
        ),
        "frequencia": "Bienal",
        "anos_disponiveis": [
            2011,
            2013,
            2015,
            2017,
            2019,
            2021,
            2023,
        ],
    },
    "censo_superior": {
        "nome": "Censo da Educação Superior",
        "descricao": "IES, cursos de graduação, docentes e discentes do ensino superior",
        "frequencia": "Anual",
        "anos_disponiveis": list(range(2009, 2025)),
    },
    "enade": {
        "nome": "Exame Nacional de Desempenho dos Estudantes",
        "descricao": "Desempenho de concluintes do ensino superior por área/curso",
        "frequencia": "Trienal por área",
        "anos_disponiveis": list(range(2004, 2024)),
    },
    "encceja": {
        "nome": "Exame Nacional para Certificação de Competências de Jovens e Adultos",
        "descricao": "Participantes, notas e certificação EJA",
        "frequencia": "Variável",
        "anos_disponiveis": [2017, 2018, 2019, 2020, 2022, 2023],
    },
}

# Indicadores educacionais derivados do Censo Escolar
INDICADORES_EDUCACIONAIS = {
    "taxa_distorcao_idade_serie": {
        "nome": "Taxa de Distorção Idade-Série",
        "descricao": "Percentual de alunos com idade acima da esperada para a série",
    },
    "taxa_rendimento": {
        "nome": "Taxas de Rendimento Escolar",
        "descricao": "Taxas de aprovação, reprovação e abandono",
    },
    "adequacao_formacao_docente": {
        "nome": "Adequação da Formação Docente",
        "descricao": "Percentual de docentes com formação adequada à disciplina",
    },
    "esforco_docente": {
        "nome": "Indicador de Esforço Docente",
        "descricao": "Nível de esforço do docente (nº de escolas, turmas, etapas)",
    },
    "complexidade_gestao": {
        "nome": "Indicador de Complexidade de Gestão da Escola",
        "descricao": "Nível de complexidade da gestão escolar (porte, etapas, turnos)",
    },
    "regularidade_docente": {
        "nome": "Indicador de Regularidade do Corpo Docente",
        "descricao": "Regularidade de permanência do docente na escola",
    },
    "nivel_socioeconomico": {
        "nome": "Indicador de Nível Socioeconômico (INSE)",
        "descricao": "Nível socioeconômico dos alunos por escola",
    },
}
