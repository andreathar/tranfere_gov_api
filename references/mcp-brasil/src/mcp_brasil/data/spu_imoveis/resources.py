"""Static reference data for the spu_imoveis feature."""

from __future__ import annotations

import json

from .constants import COLUMNS, ORGAO_SIGLAS


def schema_csv() -> str:
    """Colunas do patrimonio-uniao.csv com descrições resumidas."""
    descricoes = {
        "orgao_superior_codigo_siorg": "Código SIORG do órgão superior (ex: ministério)",
        "orgao_superior_nome": "Nome por extenso do órgão superior",
        "orgao_superior_sigla": "Sigla do órgão superior (MEC, MD, MGI, ...)",
        "orgao_codigo_siorg": "Código SIORG do órgão titular do imóvel",
        "orgao_nome": "Nome por extenso do órgão titular",
        "orgao_sigla": "Sigla do órgão titular",
        "orgao_como_no_raiox_nome": "Nome agrupado no Raio-X (pode consolidar subordinadas)",
        "orgao_como_no_raiox_sigla": "Sigla agrupada no Raio-X",
        "ano_mes_referencia": "AAAAMM (ex: 202405)",
        "regime_utilizacao": (
            "Regime: 'USO EM SERVIÇO PÚBLICO', 'IMÓVEL FUNCIONAL', 'CESSÃO - OUTROS', "
            "'EM REGULARIZAÇÃO - REFORMA AGRÁRIA', etc."
        ),
        "tipo_destinacao": "Finalidade: 'Apartamento', 'Fazenda', 'Terreno', 'Palácio', etc.",
        "tipo_imovel": "Variante detalhada do tipo de imóvel",
        "endereco": "Endereço completo (texto livre)",
        "municipio_nome": "Nome do município",
        "municipio_cod_ibge": "Código IBGE do município (7 dígitos)",
        "uf": "Sigla da UF (DF, SP, RJ, ...)",
        "metro_quadrado_area": "Área do terreno em m²",
        "metro_quadrado_construida": "Área construída em m²",
        "valor_imovel": "Valor contábil do imóvel em BRL",
        "valor_aluguel": "Valor anual de aluguel em BRL (se aplicável)",
    }
    data = {
        "csv_url": "https://repositorio.dados.gov.br/seges/raio-x/patrimonio-uniao.csv",
        "encoding": "UTF-8",
        "separator": ",",
        "columns": [{"name": c, "description": descricoes[c]} for c in COLUMNS],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def catalogo_orgaos() -> str:
    """Catálogo de siglas comuns de órgãos superiores presentes no dataset."""
    return json.dumps(
        {"orgaos_superiores_frequentes": list(ORGAO_SIGLAS)},
        ensure_ascii=False,
        indent=2,
    )


def info_api() -> str:
    """Metadados da fonte de dados."""
    info = {
        "fonte": "Raio-X APF / Gov360 — Ministério da Gestão e Inovação (MGI)",
        "url_base": "https://repositorio.dados.gov.br/seges/raio-x",
        "dataset": "raio-x-da-administracao-publica-federal",
        "arquivo": "patrimonio-uniao.csv",
        "atualizacao": "mensal (republicada pelo MGI; fonte primária: SPUnet/SIAPA)",
        "cobertura": (
            "Imóveis de uso especial da União alocados a órgãos da APF — "
            "NÃO inclui dominiais SIAPA com foreiros/ocupantes (aforamento/ocupação)."
        ),
        "auth": "Sem autenticação — diretório público com autoindex Nginx",
        "lgpd": "Baixo risco — dados patrimoniais institucionais, sem PII",
        "licenca": "Dados abertos (Lei 12.527/2011 + Decreto 8.777/2016)",
    }
    return json.dumps(info, ensure_ascii=False, indent=2)
