"""Constants for the spu_siapa feature.

Values here are derived from observed distinct values in the live SIAPA
dataset (2026-04 snapshot, 812.868 rows). Do not invent values — use
``valores_distintos_siapa(coluna)`` at runtime to discover current ones.
"""

# Classe — 92% "Dominial", 8% "Uso Especial"
CLASSES: tuple[str, ...] = ("Dominial", "Uso Especial")

# Regime de utilização — top valores observados, ordenados por frequência
REGIMES_COMUNS: tuple[str, ...] = (
    "Aforamento",
    "Inscrição de Ocupação",
    "Termo  de Autorização de Uso Sustentável",  # note: double space in source
    "Sem Destinação Definida",
    "Em Processso de Destinação",  # sic — typo no dado original
    "Uso próprio em serviço público",
    "Entrega",
    "Reservado para uso residencial funcional",
    "Concessão de Direito Real de Uso",
    "Cessão de uso gratuita",
    "Locação De Terceiros",
    "Concessão de Uso Especial para fins de Moradia",
)

# Conceituação do terreno — valores reais (Ilha NÃO existe aqui; use spu_geo)
CONCEITUACOES: tuple[str, ...] = (
    "Marinha",
    "Acrescido de Marinha",
    "Nacional Interior",
    "Marinha com Acrescido",
    "Marginal de Rio",
    "Não Informado",
    "Marinha com Nacional Interior",
    "Nacional Interior com Marinha e Acrescido de Marinha",
    "Acrescido de Marginal de Rio",
    "Terra Indigena",
    "Marginal de Rio com Acrescido",
    "Superfície Contígua de Água Exposta",
)

# Proprietário oficial — ~97% é "União (Adm. Pub. Fed. direta)"
PROPRIETARIOS: tuple[str, ...] = (
    "União (Adm. Pub. Fed. direta)",
    "Fundação ou Autarquia (Adm. Pub. Fed. indireta)",
    "Outros",
    "Empresa Estatal dependente (Adm. Pub. Fed. indireta)",
)

# Colunas filtráveis (para valores_distintos_siapa)
COLUNAS_DISTINCT_PERMITIDAS: frozenset[str] = frozenset(
    {
        "classe",
        "regime_utilizacao",
        "conceituacao_terreno",
        "tipo_imovel",
        "proprietario_oficial",
        "nivel_precisao",
        "uf",
    }
)
