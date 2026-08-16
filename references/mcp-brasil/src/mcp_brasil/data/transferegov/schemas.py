"""Pydantic models for TransfereGov API responses."""

from __future__ import annotations

from pydantic import BaseModel


class TransferenciaEspecial(BaseModel):
    """Transferência especial (emenda pix) — plano de ação."""

    id_plano_acao: int | None = None
    codigo_plano_acao: str | None = None
    ano: int | None = None
    situacao: str | None = None
    nome_parlamentar: str | None = None
    numero_emenda: str | None = None
    ano_emenda: str | None = None
    valor_custeio: float | None = None
    valor_investimento: float | None = None
    cnpj_beneficiario: str | None = None
    nome_beneficiario: str | None = None
    uf_beneficiario: str | None = None
    area_politica_publica: str | None = None
