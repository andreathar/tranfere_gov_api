"""Client for INEP data.

The INEP does NOT have a REST API. Data is published as XLSX/CSV/ZIP files
at download.inep.gov.br. This client generates structured download URLs
and provides metadata about available datasets.
"""

from __future__ import annotations

from .constants import (
    CATALOGO_MICRODADOS,
    IDEB_ANOS,
    IDEB_ETAPAS,
    IDEB_NIVEIS,
    IDEB_URLS,
    INDICADORES_EDUCACIONAIS,
    MICRODADOS_URLS,
)
from .schemas import IdebUrl, IndicadorEducacional, MicrodadosDataset

# Estimated file sizes for IDEB downloads
_IDEB_TAMANHOS = {
    "brasil": "~50 KB",
    "regioes_ufs": "~200 KB",
    "municipios": "~10 MB",
    "escolas": "~30-50 MB",
}


async def gerar_urls_ideb(
    *,
    ano: int | None = None,
    etapa: str | None = None,
    nivel: str | None = None,
) -> list[IdebUrl]:
    """Generate IDEB download URLs for the given filters."""
    anos = [ano] if ano else IDEB_ANOS
    niveis = [nivel] if nivel else list(IDEB_NIVEIS.keys())
    etapas = [etapa] if etapa else list(IDEB_ETAPAS.keys())

    urls: list[IdebUrl] = []
    for a in anos:
        if a not in IDEB_ANOS:
            continue
        for n in niveis:
            if n not in IDEB_URLS:
                continue
            template = IDEB_URLS[n]
            if n in ("brasil", "regioes_ufs"):
                urls.append(
                    IdebUrl(
                        nivel=n,
                        etapa=None,
                        ano=a,
                        url=template.format(ano=a),
                        tamanho_estimado=_IDEB_TAMANHOS.get(n, "desconhecido"),
                    )
                )
            else:
                for e in etapas:
                    if e not in IDEB_ETAPAS:
                        continue
                    urls.append(
                        IdebUrl(
                            nivel=n,
                            etapa=e,
                            ano=a,
                            url=template.format(etapa=e, ano=a),
                            tamanho_estimado=_IDEB_TAMANHOS.get(n, "desconhecido"),
                        )
                    )
    return urls


async def listar_microdados() -> list[MicrodadosDataset]:
    """List all available INEP microdata datasets."""
    datasets: list[MicrodadosDataset] = []
    for codigo, info in CATALOGO_MICRODADOS.items():
        datasets.append(
            MicrodadosDataset(
                codigo=codigo,
                nome=str(info["nome"]),
                descricao=str(info["descricao"]),
                frequencia=str(info["frequencia"]),
                anos_disponiveis=list(info["anos_disponiveis"]),  # type: ignore[arg-type]
                url_template=MICRODADOS_URLS[codigo],
            )
        )
    return datasets


async def gerar_url_microdados(dataset: str, ano: int) -> str | None:
    """Generate a download URL for a specific microdata dataset and year."""
    if dataset not in MICRODADOS_URLS:
        return None
    catalogo = CATALOGO_MICRODADOS.get(dataset)
    if catalogo and ano not in catalogo["anos_disponiveis"]:
        return None
    return MICRODADOS_URLS[dataset].format(ano=ano)


async def listar_indicadores() -> list[IndicadorEducacional]:
    """List all INEP educational indicators."""
    return [
        IndicadorEducacional(
            codigo=codigo,
            nome=str(info["nome"]),
            descricao=str(info["descricao"]),
        )
        for codigo, info in INDICADORES_EDUCACIONAIS.items()
    ]
