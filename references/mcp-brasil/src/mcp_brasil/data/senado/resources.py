"""Resources for the Senado feature — static reference data for LLM context."""

from __future__ import annotations

import json

from .constants import SENADO_API_BASE, TIPOS_MATERIA


def tipos_materia() -> str:
    """Tipos de matéria legislativa do Senado Federal com siglas e descrições."""
    data = [
        {"sigla": sigla, "descricao": descricao}
        for sigla, descricao in sorted(TIPOS_MATERIA.items())
    ]
    return json.dumps(data, ensure_ascii=False)


def info_api() -> str:
    """Informações gerais sobre a API de Dados Abertos do Senado."""
    data = {
        "nome": "API de Dados Abertos do Senado Federal",
        "url_base": SENADO_API_BASE,
        "autenticacao": "Não requer autenticação",
        "documentacao": "https://legis.senado.leg.br/dadosabertos/docs",
        "formato": "JSON via Accept header (application/json)",
        "observacoes": [
            "Respostas podem ser profundamente aninhadas",
            "Um único resultado pode vir como dict ao invés de lista",
            "Tipos de matéria mais comuns: PEC, PLS, PLC, MPV, PLP, PDL",
        ],
    }
    return json.dumps(data, ensure_ascii=False)


def comissoes_permanentes() -> str:
    """Comissões permanentes do Senado Federal."""
    data = [
        {"sigla": "CAE", "nome": "Comissão de Assuntos Econômicos"},
        {"sigla": "CAS", "nome": "Comissão de Assuntos Sociais"},
        {"sigla": "CCJ", "nome": "Comissão de Constituição, Justiça e Cidadania"},
        {
            "sigla": "CCT",
            "nome": "Comissão de Ciência, Tecnologia, Inovação, Comunicação e Informática",
        },
        {"sigla": "CDH", "nome": "Comissão de Direitos Humanos e Legislação Participativa"},
        {"sigla": "CDR", "nome": "Comissão de Desenvolvimento Regional e Turismo"},
        {"sigla": "CE", "nome": "Comissão de Educação, Cultura e Esporte"},
        {"sigla": "CI", "nome": "Comissão de Serviços de Infraestrutura"},
        {"sigla": "CMA", "nome": "Comissão de Meio Ambiente"},
        {"sigla": "CRA", "nome": "Comissão de Agricultura e Reforma Agrária"},
        {"sigla": "CRE", "nome": "Comissão de Relações Exteriores e Defesa Nacional"},
        {"sigla": "CSF", "nome": "Comissão Senado do Futuro"},
        {
            "sigla": "CTFC",
            "nome": "Comissão de Transparência, Governança, Fiscalização e "
            "Controle e Defesa do Consumidor",
        },
    ]
    return json.dumps(data, ensure_ascii=False)
