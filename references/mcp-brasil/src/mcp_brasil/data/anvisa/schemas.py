"""Pydantic schemas for the ANVISA feature."""

from __future__ import annotations

from pydantic import BaseModel


class MedicamentoBulario(BaseModel):
    """Medicamento encontrado no Bulário Eletrônico da ANVISA."""

    id_produto: str | None = None
    nome_produto: str | None = None
    razao_social: str | None = None
    cnpj: str | None = None
    numero_registro: str | None = None
    data_vencimento_registro: str | None = None
    principio_ativo: str | None = None
    categoria_regulatoria: str | None = None
    numero_processo: str | None = None


class BulaMedicamento(BaseModel):
    """Informações de bula de um medicamento."""

    id_bula: str | None = None
    id_produto: str | None = None
    nome_produto: str | None = None
    empresa: str | None = None
    tipo_bula: str | None = None
    data_publicacao: str | None = None
    url_bula: str | None = None


class CategoriaMedicamento(BaseModel):
    """Categoria regulatória de medicamento."""

    codigo: str
    descricao: str
