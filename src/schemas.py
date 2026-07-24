"""
Schemas Pydantic para os dados do Transferegov.

Validação de registros extraídos da API pública.
Usado por: transferegov_extract.py, db_import.py
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator


class PlanoAcaoSchema(BaseModel):
    """Schema de validação para um plano de ação extraído da API pública."""

    planoAcaoId: int
    planoAcaoCodigo: str = ""
    planoAcaoSituacao: str = ""
    planoTrabalhoSituacao: str | None = None

    objetoId: int | None = None
    objetoDescricao: str = ""

    programaId: int | None = None
    programaCodigo: str = ""

    beneficiarioId: int | None = None
    beneficiarioNome: str = ""
    beneficiarioCnpj: str = ""
    uf: str = ""
    enteId: int | None = None

    codigoEmendaFormatado: str = ""
    politicasPublicas: str = ""
    motivoImpedimento: str | None = None
    numeroParceria: str | None = None

    valorCusteio: float = 0.0
    valorInvestimento: float = 0.0
    valorTotal: float = 0.0

    dataAtualizacaoPlanoAcao: str | None = None
    dataAtualizacaoPlanoTrabalho: str | None = None

    # Campos extra que a API pode retornar (ignorados se presentes)
    model_config = {"extra": "ignore"}

    @field_validator("uf", mode="before")
    @classmethod
    def normalize_uf(cls, v: str) -> str:
        if v is None:
            return ""
        return v.strip().upper()

    @field_validator("valorCusteio", "valorInvestimento", "valorTotal", mode="before")
    @classmethod
    def coerce_float(cls, v) -> float:
        if v is None:
            return 0.0
        if isinstance(v, str):
            v = v.strip()
            # Handle BRL format: "1.234,56" → 1234.56
            if "," in v and "." in v:
                v = v.replace(".", "").replace(",", ".")
            elif "," in v:
                v = v.replace(",", ".")
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @property
    def is_negado(self) -> bool:
        return self.planoAcaoSituacao in {"REPROVADO", "IMPEDIDO", "CANCELADO", "NAO_CUMPROU"}

    @property
    def valor_total_real(self) -> float:
        return (self.valorCusteio or 0) + (self.valorInvestimento or 0)


def validate_records(
    records: list[dict],
    strict: bool = False,
) -> tuple[list[PlanoAcaoSchema], list[str]]:
    """
    Valida uma lista de registros brutos (dicts) contra o schema.

    Args:
        records: Lista de dicts da API
        strict: Se True, levanta exceção no primeiro erro.
                Se False, loga warnings e pula registros inválidos.

    Returns:
        (validos, erros) — lista de schemas válidos e lista de msgs de erro
    """
    validos: list[PlanoAcaoSchema] = []
    erros: list[str] = []

    for i, rec in enumerate(records):
        try:
            plano = PlanoAcaoSchema.model_validate(rec)
            validos.append(plano)
        except Exception as e:
            pid = rec.get("planoAcaoId", "?")
            msg = f"Registro {i} (id={pid}): {e}"
            if strict:
                raise ValueError(msg) from e
            erros.append(msg)

    return validos, erros
