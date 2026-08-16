"""Pydantic schemas for the TCE-RJ feature."""

from __future__ import annotations

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Licitações
# ---------------------------------------------------------------------------


class Licitacao(BaseModel):
    """Licitação municipal no RJ."""

    ente: str | None = None
    unidade: str | None = None
    ano: int | None = None
    modalidade: str | None = None
    tipo: str | None = None
    processo_licitatorio: str | None = None
    numero_edital: str | None = None
    objeto: str | None = None
    valor_estimado: float | None = None
    data_publicacao_oficial: str | None = None
    data_homologacao: str | None = None


class LicitacaoResultado(BaseModel):
    """Resultado paginado de licitações."""

    licitacoes: list[Licitacao] = []
    total: int = 0


# ---------------------------------------------------------------------------
# Contratos municipais
# ---------------------------------------------------------------------------


class ContratoMunicipio(BaseModel):
    """Contrato municipal no RJ."""

    ente: str | None = None
    numero_contrato: str | None = None
    ano_contrato: int | None = None
    contratado: str | None = None
    cpf_cnpj_contratado: str | None = None
    objeto: str | None = None
    tipo_contrato: str | None = None
    valor_contrato: float | None = None
    data_assinatura_contrato: str | None = None
    data_vencimento_contrato: str | None = None


class ContratoMunicipioResultado(BaseModel):
    """Resultado paginado de contratos municipais."""

    contratos: list[ContratoMunicipio] = []
    total: int = 0


# ---------------------------------------------------------------------------
# Compras diretas
# ---------------------------------------------------------------------------


class CompraDireta(BaseModel):
    """Compra direta (dispensa/inexigibilidade)."""

    processo: str | None = None
    ano_processo: str | None = None
    unidade: str | None = None
    objeto: str | None = None
    afastamento: str | None = None
    fornecedor_vencedor: str | None = None
    valor_processo: float | None = None
    data_aprovacao: str | None = None
    enquadramento_legal: str | None = None


# ---------------------------------------------------------------------------
# Obras paralisadas
# ---------------------------------------------------------------------------


class ObraParalisada(BaseModel):
    """Obra pública paralisada."""

    ente: str | None = None
    tipo_ente: str | None = None
    nome: str | None = None
    funcao_governo: str | None = None
    numero_contrato: str | None = None
    nome_contratada: str | None = None
    cnpj_contratada: str | None = None
    valor_total_contrato: float | None = None
    valor_pago_obra: float | None = None
    tempo_paralisacao: str | None = None
    motivo_paralisacao: str | None = None
    data_paralisacao: str | None = None
    data_inicio_obra: str | None = None
    status_contrato: str | None = None
    classificacao_obra: str | None = None


# ---------------------------------------------------------------------------
# Penalidades
# ---------------------------------------------------------------------------


class Penalidade(BaseModel):
    """Penalidade ou ressarcimento aplicado pelo TCE-RJ."""

    processo: str | None = None
    ano_condenacao: int | None = None
    valor_penalidade: float | None = None
    condenacao: str | None = None
    ente: str | None = None
    nome_orgao: str | None = None
    tipo_ente: str | None = None
    grupo_natureza: str | None = None
    data_sessao: str | None = None


# ---------------------------------------------------------------------------
# Prestação de contas
# ---------------------------------------------------------------------------


class PrestacaoContas(BaseModel):
    """Prestação de contas municipal."""

    municipio: str | None = None
    regiao: str | None = None
    ano: int | None = None
    indicador: str | None = None
    processo: str | None = None
    responsavel: str | None = None


# ---------------------------------------------------------------------------
# Concessões públicas
# ---------------------------------------------------------------------------


class Concessao(BaseModel):
    """Concessão pública municipal."""

    ente: str | None = None
    unidade: str | None = None
    numero: str | None = None
    objeto: str | None = None
    data_assinatura: str | None = None
    data_execucao_final: str | None = None
    situacao_concessao: str | None = None
    natureza: str | None = None
    segmento_servico: str | None = None
    nome_razao_social: str | None = None
    valor_total_outorga: float | None = None


class ConcessaoMunicipio(BaseModel):
    """Concessões agrupadas por município."""

    municipio: str
    concessoes: list[Concessao] = []
