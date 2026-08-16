"""Prompts for the Senado feature — analysis templates for LLMs."""

from __future__ import annotations


def acompanhar_materia(sigla_tipo: str, numero: str, ano: str) -> str:
    """Gera um acompanhamento completo de uma matéria legislativa no Senado.

    Cria um template que orienta o LLM a consultar dados da matéria,
    tramitação e votações no Senado Federal.

    Args:
        sigla_tipo: Tipo da matéria (ex: PEC, PLS, PLC, MPV).
        numero: Número da matéria.
        ano: Ano da matéria.
    """
    materia = f"{sigla_tipo} {numero}/{ano}"
    return (
        f"Faça um acompanhamento completo da matéria {materia} "
        "usando os dados do Senado Federal.\n\n"
        "Passos:\n"
        f"1. Use buscar_materia(sigla_tipo='{sigla_tipo}', numero='{numero}', "
        f"ano='{ano}') para encontrar a matéria e obter o código\n"
        "2. Com o código, use detalhe_materia(codigo=CÓDIGO) "
        "para ver a ementa completa e autor\n"
        "3. Use consultar_tramitacao_materia(codigo=CÓDIGO) "
        "para ver o histórico de tramitação\n"
        "4. Use votos_materia(codigo=CÓDIGO) para verificar votações\n"
        "5. Use textos_materia(codigo=CÓDIGO) para obter links dos documentos\n\n"
        "Apresente:\n"
        f"- Resumo da {materia}: ementa, autor e situação atual\n"
        "- Histórico de tramitação (principais eventos)\n"
        "- Resultado das votações (se houver)\n"
        "- Links para textos e documentos oficiais\n"
        "- Próximos passos previstos na tramitação"
    )


def perfil_senador(codigo: str) -> str:
    """Gera um perfil completo de um senador.

    Cria um template com dados pessoais e votações do senador.

    Args:
        codigo: Código do senador na API do Senado.
    """
    return (
        f"Monte um perfil completo do senador código {codigo} "
        "usando os dados do Senado Federal.\n\n"
        "Passos:\n"
        f"1. Use buscar_senador(codigo='{codigo}') "
        "para obter os dados básicos\n"
        f"2. Use votacoes_senador(codigo='{codigo}') "
        "para verificar as votações recentes\n\n"
        "Apresente:\n"
        "- Dados do senador: nome, partido, UF, mandato\n"
        "- Participação em votações recentes e posicionamentos públicos"
    )


def analise_votacao_senado(codigo_sessao: str) -> str:
    """Gera uma análise detalhada de uma votação no Senado.

    Cria um template que analisa o resultado e contexto de uma votação.

    Args:
        codigo_sessao: Código da sessão de votação.
    """
    return (
        f"Analise detalhadamente a votação {codigo_sessao} "
        "no Senado Federal.\n\n"
        "Passos:\n"
        f"1. Use detalhe_votacao(codigo_sessao='{codigo_sessao}') "
        "para obter o resultado e placar\n\n"
        "Apresente:\n"
        "- Resultado geral: aprovada ou rejeitada\n"
        "- Placar: votos Sim, Não e Abstenção\n"
        "- Matéria votada e seu contexto\n"
        "- Análise: qual o impacto desta votação?"
    )
