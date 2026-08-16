"""Pydantic schemas for the DENASUS feature."""

from __future__ import annotations

from pydantic import BaseModel


class AtividadeAuditoria(BaseModel):
    """Atividade de auditoria do DENASUS."""

    titulo: str
    data: str | None = None
    uf: str | None = None
    tipo: str | None = None
    situacao: str | None = None
    resumo: str | None = None
    url_detalhe: str | None = None


class RelatorioAnual(BaseModel):
    """Relatório anual de atividades do DENASUS."""

    ano: int | None = None
    titulo: str
    url_pdf: str | None = None
    resumo: str | None = None


class PlanoAuditoria(BaseModel):
    """Plano anual de auditoria interna."""

    ano: int | None = None
    titulo: str
    url_pdf: str | None = None
