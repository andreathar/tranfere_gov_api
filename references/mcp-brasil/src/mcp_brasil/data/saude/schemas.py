"""Pydantic schemas for the Saúde feature."""

from __future__ import annotations

from pydantic import BaseModel


class Estabelecimento(BaseModel):
    """Estabelecimento de saúde CNES."""

    codigo_cnes: str | None = None
    nome_fantasia: str | None = None
    nome_razao_social: str | None = None
    natureza_organizacao: str | None = None
    tipo_gestao: str | None = None
    codigo_tipo: str | None = None
    descricao_tipo: str | None = None
    codigo_municipio: str | None = None
    codigo_uf: str | None = None
    endereco: str | None = None


class Profissional(BaseModel):
    """Profissional de saúde CNES."""

    codigo_cnes: str | None = None
    nome: str | None = None
    cns: str | None = None
    cbo: str | None = None
    descricao_cbo: str | None = None


class TipoEstabelecimento(BaseModel):
    """Tipo de estabelecimento de saúde."""

    codigo: str | None = None
    descricao: str | None = None


class Leito(BaseModel):
    """Leito hospitalar CNES."""

    codigo_cnes: str | None = None
    tipo_leito: str | None = None
    especialidade: str | None = None
    existente: int | None = None
    sus: int | None = None


class EstabelecimentoDetalhe(BaseModel):
    """Detalhe completo de um estabelecimento de saúde CNES."""

    codigo_cnes: str | None = None
    nome_fantasia: str | None = None
    nome_razao_social: str | None = None
    natureza_organizacao: str | None = None
    tipo_gestao: str | None = None
    codigo_tipo: str | None = None
    descricao_tipo: str | None = None
    codigo_municipio: str | None = None
    codigo_uf: str | None = None
    endereco: str | None = None
    bairro: str | None = None
    cep: str | None = None
    telefone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    cnpj: str | None = None
    data_atualizacao: str | None = None


class ResumoRedeMunicipal(BaseModel):
    """Resumo da rede de saúde de um município."""

    codigo_municipio: str
    total_estabelecimentos: int = 0
    por_tipo: dict[str, int] = {}
    total_leitos_existentes: int = 0
    total_leitos_sus: int = 0
    total_profissionais: int = 0


# ---------------------------------------------------------------------------
# Epidemiologia — InfoDengue / InfoGripe / DATASUS / SINAN
# ---------------------------------------------------------------------------


class AlertaDengue(BaseModel):
    """Alerta epidemiológico de arbovirose (InfoDengue)."""

    semana_epidemiologica: int | None = None
    data_inicio_se: str | None = None
    casos_estimados: float | None = None
    casos_notificados: int | None = None
    nivel: int | None = None
    nivel_descricao: str | None = None
    incidencia_100k: float | None = None
    rt: float | None = None
    populacao: float | None = None
    receptividade: int | None = None
    transmissao: int | None = None


class AlertaGripe(BaseModel):
    """Alerta epidemiológico de síndrome gripal (InfoGripe)."""

    uf: str | None = None
    semana_epidemiologica: int | None = None
    ano: int | None = None
    situacao: str | None = None
    nivel: str | None = None
    casos_estimados: float | None = None
    casos_notificados: int | None = None
    limite_inferior: float | None = None
    limite_superior: float | None = None


class BaseDATASUS(BaseModel):
    """Base de dados do DATASUS (metadados de referência)."""

    sigla: str
    nome: str
    descricao: str
    cobertura: str
    dimensoes: str


class DoencaNotificavel(BaseModel):
    """Doença de notificação compulsória (SINAN)."""

    codigo: str
    nome: str
    categoria: str


class MunicipioGeocode(BaseModel):
    """Município com geocódigo IBGE."""

    nome: str
    uf: str
    geocodigo: str
