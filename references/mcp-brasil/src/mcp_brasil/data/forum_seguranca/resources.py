"""Resources for the Fórum Segurança feature — thematic community catalog.

Provides a static catalog of the 15 thematic communities in the FBSP repository,
so LLMs can reference community UUIDs without making API calls.
"""

from __future__ import annotations

import json

from .constants import COMUNIDADES

# Descriptions for communities (where available from DSpace metadata)
_DESCRICOES: dict[str, str] = {
    "d044c00f-7c26-4249-8da4-336e953fe557": (
        "Dados e análises anuais sobre criminalidade, violência e segurança pública no Brasil."
    ),
    "068d69a5-d8e3-4d70-a218-22c60acdbf61": (
        "Indicadores de violência produzidos pelo Ipea e FBSP com análise territorial."
    ),
    "c5d1a51f-2757-45c2-95e2-d1d329d7293f": (
        "Pesquisas sobre feminicídio, violência doméstica e outras formas de violência de gênero."
    ),
    "028b6542-7b8b-4979-8cc6-80c1304c93c2": (
        "Estudos sobre encarceramento, condições prisionais e políticas penitenciárias."
    ),
    "8f424527-643e-4d97-99f1-b27dbf593290": (
        "Transparência e análise dos gastos públicos com segurança."
    ),
    "d03b839a-46fd-4662-a35c-ed29eaea4f3b": (
        "Jovens como vítimas e autores de violência, homicídios de jovens."
    ),
    "89db75a3-de54-400e-aa9b-05c445e6b910": (
        "Análise de políticas e programas de segurança pública."
    ),
    "b5364b6c-25c5-4648-89b9-1d069065ae3f": ("Estratégias e programas de prevenção à violência."),
    "e7057d2b-1548-4671-a972-d97426d4f556": (
        "Condições de trabalho, saúde e vitimização de policiais e agentes."
    ),
    "37400926-4625-44c1-84c5-fe1a4f316f2b": (
        "Racismo institucional, violência racial e segurança pública."
    ),
    "da266936-812e-462d-b512-d6d50299886a": (
        "Acervo de práticas inovadoras reconhecidas pelo FBSP."
    ),
    "ae73bbbc-55dd-45e0-8c3e-d351cfb96cb1": ("Segurança pública na região amazônica."),
    "1c2a4641-c556-47a0-99f2-06b819b8256e": (
        "Relação entre instituições democráticas e segurança pública."
    ),
    "abda3c48-f977-478c-bdc2-227c2e6cd4c4": ("Artigos e documentos dos encontros anuais do FBSP."),
    "40a19dcb-00a6-420d-a2b8-11667ff12aad": (
        "Metodologias e sistemas de produção de dados sobre segurança."
    ),
}


def catalogo_comunidades() -> str:
    """Catálogo das 15 comunidades temáticas do Fórum Brasileiro de Segurança Pública.

    Contém UUID, nome e descrição de cada comunidade para referência.
    Use o UUID com a tool buscar_por_tema_seguranca para filtrar publicações por tema.
    """
    data = [
        {
            "uuid": uuid,
            "nome": nome,
            "descricao": _DESCRICOES.get(uuid, ""),
        }
        for uuid, nome in COMUNIDADES.items()
    ]
    return json.dumps(data, ensure_ascii=False)
