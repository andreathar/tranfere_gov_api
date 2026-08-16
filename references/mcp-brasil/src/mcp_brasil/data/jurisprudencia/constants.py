"""Constants for the Jurisprudência feature (STF, STJ, TST)."""

# === STF — Supremo Tribunal Federal ===
STF_API_BASE = "https://jurisprudencia.stf.jus.br/api/search/pesquisar"
STF_SEARCH_PARAMS = {
    "base": "acordaos",
    "pesquisa_inteiro_teor": "false",
    "sinonimo": "true",
    "plural": "true",
    "radicais": "false",
    "buscaExata": "true",
}

# === STJ — Superior Tribunal de Justiça ===
STJ_API_BASE = "https://scon.stj.jus.br/SCON/pesquisar.jsp"
STJ_SEARCH_PARAMS = {
    "tipo_visualizacao": "null",
    "thesaurus": "JURIDICO",
    "p": "true",
    "operador": "e",
    "processo_origem": "",
    "livreMinistro": "",
}

# === TST — Tribunal Superior do Trabalho ===
TST_API_BASE = "https://jurisprudencia-backend.tst.jus.br/rest/documentos"

# Tamanhos padrão
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50

# Operadores de busca disponíveis por tribunal
OPERADORES_BUSCA: dict[str, dict[str, str]] = {
    "stf": {
        "E": "Operador AND (ambos os termos)",
        "OU": "Operador OR (qualquer termo)",
        "NÃO": "Operador NOT (excluir termo)",
        "~": "Busca fuzzy (variações de escrita)",
        "$": "Curinga (múltiplos caracteres)",
        "?": "Curinga (um caractere)",
        '""~N': "Proximidade (termos a N palavras de distância)",
        '""': "Expressão exata",
    },
    "stj": {
        "e": "Operador AND",
        "ou": "Operador OR",
        "não": "Operador NOT",
        "mesmo": "Termos no mesmo campo",
        "com": "Termos no mesmo documento",
        "PROX(N)": "Proximidade (N palavras)",
        "ADJ(N)": "Adjacência (N palavras, em ordem)",
        "$": "Curinga (múltiplos caracteres)",
        "?": "Curinga (um caractere)",
        '""': "Expressão exata",
    },
    "tst": {
        '""': "Expressão exata",
        "E": "Operador AND",
        "OU": "Operador OR",
    },
}

# Informações sobre os tribunais
TRIBUNAIS_SUPERIORES: dict[str, dict[str, str]] = {
    "stf": {
        "nome": "Supremo Tribunal Federal",
        "competencia": "Guarda da Constituição Federal. Julga questões constitucionais.",
        "tipos_decisao": "Acórdãos, Súmulas Vinculantes, Repercussão Geral",
        "site": "https://portal.stf.jus.br",
    },
    "stj": {
        "nome": "Superior Tribunal de Justiça",
        "competencia": "Uniformização da legislação infraconstitucional federal.",
        "tipos_decisao": "Acórdãos, Súmulas, Informativos",
        "site": "https://www.stj.jus.br",
    },
    "tst": {
        "nome": "Tribunal Superior do Trabalho",
        "competencia": "Uniformização da jurisprudência trabalhista.",
        "tipos_decisao": "Acórdãos, Súmulas, Orientações Jurisprudenciais",
        "site": "https://www.tst.jus.br",
    },
}
