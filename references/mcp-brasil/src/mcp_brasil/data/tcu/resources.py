"""Static reference data for the TCU feature."""

from __future__ import annotations

import json

from .constants import COLEGIADOS, SITUACOES_ACORDAO


def catalogo_endpoints() -> str:
    """Catálogo dos endpoints disponíveis do TCU."""
    endpoints = [
        {
            "nome": "Acórdãos",
            "descricao": "Decisões colegiadas do TCU",
            "status": "ATIVO",
        },
        {
            "nome": "Inabilitados",
            "descricao": "Pessoas inabilitadas para função pública",
            "status": "ATIVO",
        },
        {
            "nome": "Inidôneos",
            "descricao": "Licitantes declarados inidôneos",
            "status": "ATIVO",
        },
        {
            "nome": "Certidões APF",
            "descricao": "Certidões consolidadas (TCU + CNJ + CGU)",
            "status": "ATIVO",
        },
        {
            "nome": "Pedidos do Congresso",
            "descricao": "Solicitações do Congresso ao TCU",
            "status": "ATIVO",
        },
        {
            "nome": "Cálculo de Débito",
            "descricao": "Calculadora de débito com correção SELIC",
            "status": "ATIVO",
        },
        {
            "nome": "Termos Contratuais",
            "descricao": "Contratos firmados pelo TCU",
            "status": "ATIVO",
        },
        {
            "nome": "CADIRREG",
            "descricao": "Cadastro de responsáveis com contas irregulares",
            "status": "ATIVO",
        },
    ]
    return json.dumps(endpoints, ensure_ascii=False, indent=2)


def colegiados() -> str:
    """Colegiados do TCU que emitem acórdãos."""
    return json.dumps(COLEGIADOS, ensure_ascii=False)


def situacoes_acordao() -> str:
    """Situações possíveis de um acórdão do TCU."""
    return json.dumps(SITUACOES_ACORDAO, ensure_ascii=False)
