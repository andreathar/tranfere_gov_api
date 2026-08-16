"""Pydantic models for Senado Federal API responses."""

from __future__ import annotations

from pydantic import BaseModel


class SenadorResumo(BaseModel):
    """Senador em listagem resumida."""

    codigo: str | None = None
    nome: str | None = None
    nome_completo: str | None = None
    partido: str | None = None
    uf: str | None = None
    foto: str | None = None
    em_exercicio: bool | None = None


class SenadorDetalhe(BaseModel):
    """Detalhes de um senador."""

    codigo: str | None = None
    nome: str | None = None
    nome_completo: str | None = None
    partido: str | None = None
    uf: str | None = None
    email: str | None = None
    foto: str | None = None
    telefone: str | None = None
    mandato_inicio: str | None = None
    mandato_fim: str | None = None


class MateriaResumo(BaseModel):
    """Matéria legislativa em listagem resumida."""

    codigo: str | None = None
    sigla_tipo: str | None = None
    numero: str | None = None
    ano: str | None = None
    ementa: str | None = None
    data_apresentacao: str | None = None
    autor: str | None = None
    situacao: str | None = None


class MateriaDetalhe(BaseModel):
    """Detalhes de uma matéria legislativa."""

    codigo: str | None = None
    sigla_tipo: str | None = None
    numero: str | None = None
    ano: str | None = None
    ementa: str | None = None
    ementa_completa: str | None = None
    data_apresentacao: str | None = None
    autor: str | None = None
    situacao: str | None = None
    casa_origem: str | None = None


class Tramitacao(BaseModel):
    """Evento de tramitação de uma matéria."""

    data: str | None = None
    descricao: str | None = None
    local: str | None = None
    situacao: str | None = None


class VotacaoResumo(BaseModel):
    """Votação resumida."""

    codigo: str | None = None
    data: str | None = None
    descricao: str | None = None
    resultado: str | None = None


class VotacaoDetalhe(BaseModel):
    """Detalhes de uma votação."""

    codigo: str | None = None
    data: str | None = None
    descricao: str | None = None
    resultado: str | None = None
    materia_codigo: str | None = None
    materia_descricao: str | None = None
    sim: int | None = None
    nao: int | None = None
    abstencao: int | None = None


class VotoNominal(BaseModel):
    """Voto individual de um senador."""

    senador_codigo: str | None = None
    senador_nome: str | None = None
    partido: str | None = None
    uf: str | None = None
    voto: str | None = None


class ComissaoResumo(BaseModel):
    """Comissão em listagem resumida."""

    codigo: str | None = None
    sigla: str | None = None
    nome: str | None = None
    tipo: str | None = None


class ComissaoDetalhe(BaseModel):
    """Detalhes de uma comissão."""

    codigo: str | None = None
    sigla: str | None = None
    nome: str | None = None
    tipo: str | None = None
    finalidade: str | None = None
    data_criacao: str | None = None
    data_extincao: str | None = None


class MembroComissao(BaseModel):
    """Membro de uma comissão."""

    codigo_senador: str | None = None
    nome: str | None = None
    partido: str | None = None
    uf: str | None = None
    cargo: str | None = None


class ReuniaoComissao(BaseModel):
    """Reunião de comissão."""

    data: str | None = None
    tipo: str | None = None
    comissao: str | None = None
    pauta: str | None = None
    local: str | None = None


class SessaoPlenario(BaseModel):
    """Sessão plenária."""

    data: str | None = None
    tipo: str | None = None
    numero: str | None = None
    situacao: str | None = None


class LegislaturaInfo(BaseModel):
    """Informações sobre uma legislatura."""

    numero: int | None = None
    data_inicio: str | None = None
    data_fim: str | None = None


class Emenda(BaseModel):
    """Emenda a uma matéria legislativa."""

    codigo: str | None = None
    numero: str | None = None
    identificacao: str | None = None
    tipo: str | None = None
    data_apresentacao: str | None = None
    autor: str | None = None
    colegiado: str | None = None
    decisao: str | None = None
    data_decisao: str | None = None
    url_documento: str | None = None


class BlocoParlamentar(BaseModel):
    """Bloco parlamentar (coalizão)."""

    codigo: str | None = None
    nome: str | None = None
    apelido: str | None = None
    data_criacao: str | None = None
    partidos: list[str] | None = None


class Lideranca(BaseModel):
    """Liderança no Senado."""

    codigo_parlamentar: str | None = None
    nome_parlamentar: str | None = None
    partido: str | None = None
    tipo_lideranca: str | None = None
    unidade_lideranca: str | None = None
    data_designacao: str | None = None


class Relatoria(BaseModel):
    """Relatoria de matéria legislativa."""

    codigo_materia: str | None = None
    identificacao: str | None = None
    ementa: str | None = None
    autor: str | None = None
    tipo_relator: str | None = None
    data_designacao: str | None = None
    colegiado: str | None = None
    tramitando: bool | None = None
