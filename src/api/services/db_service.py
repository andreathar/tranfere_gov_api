"""
Serviço de consultas PostgreSQL para o Painel de Deputados.

Consulta o banco transferegov_db para dados de parlamentares,
planos de ação (emendas pix) e municípios beneficiários.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from src.db_utils import get_real_dict_connection

log = logging.getLogger(__name__)


def _get_connection():
    """Cria conexão com o PostgreSQL transferegov_db."""
    return get_real_dict_connection()


def _rows_to_list(rows: list) -> list[dict]:
    """Converte RealDictRow para dicts serializáveis (Decimal → float)."""
    result = []
    for row in rows:
        d = {}
        for k, v in dict(row).items():
            d[k] = float(v) if isinstance(v, Decimal) else v
        result.append(d)
    return result


def _row_to_dict(row) -> dict | None:
    """Converte um RealDictRow único para dict serializável."""
    if row is None:
        return None
    d = {}
    for k, v in dict(row).items():
        d[k] = float(v) if isinstance(v, Decimal) else v
    return d


# ---------------------------------------------------------------------------
# Busca e perfil de deputados
# ---------------------------------------------------------------------------


def search_deputados(query: str) -> list[dict]:
    """Busca deputados por nome (ILIKE) na tabela parlamentares_dados."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT deputado_id, nome, nome_urna, sigla_partido, uf, url_foto
                   FROM parlamentares_dados
                   WHERE nome ILIKE %s OR nome_urna ILIKE %s
                   ORDER BY nome
                   LIMIT 20""",
            (f"%{query}%", f"%{query}%"),
        )
        return _rows_to_list(cur.fetchall())


def get_perfil_deputado(deputado_id: int) -> dict | None:
    """Retorna perfil completo do deputado pelo ID da Câmara."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM parlamentares_dados WHERE deputado_id = %s",
            (deputado_id,),
        )
        return _row_to_dict(cur.fetchone())


def get_nome_by_id(deputado_id: int) -> str | None:
    """Retorna o nome do parlamentar associado ao deputado_id."""
    perfil = get_perfil_deputado(deputado_id)
    if perfil:
        return perfil.get("nome_urna") or perfil.get("nome")
    return None


# ---------------------------------------------------------------------------
# Emendas (planos de ação)
# ---------------------------------------------------------------------------


def get_emendas_deputado(parlamentar_nome: str) -> list[dict]:
    """Retorna todos os planos de ação do parlamentar com dados do beneficiário."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    codigo_emenda AS emenda_codigo,
                    codigo_emenda AS codigo_emenda_formatado,
                    status_execucao AS plano_acao_situacao,
                    valor_total,
                    beneficiario_nome,
                    beneficiario_uf,
                    beneficiario_cnpj,
                    beneficiario_ibge,
                    objeto AS objeto_descricao,
                    modalidade
                FROM v_emendas_unificadas
                WHERE parlamentar_nome ILIKE %s
                ORDER BY valor_total DESC
            """,
            (parlamentar_nome,),
        )
        return _rows_to_list(cur.fetchall())


def get_resumo_emendas(parlamentar_nome: str) -> dict:
    """Retorna KPIs agregados das emendas do parlamentar."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    COUNT(*) AS total_planos,
                    COALESCE(SUM(valor_total), 0) AS valor_total,
                    COUNT(DISTINCT beneficiario_nome) AS municipios,
                    COUNT(DISTINCT objeto) AS objetos,
                    COUNT(DISTINCT codigo_emenda) AS emendas,
                    SUM(CASE WHEN status_execucao IN (
                        'IMPEDIDO', 'IMPEDIDO_REJEICAO_PLANO_TRABALHO',
                        'REPROVADO', 'CANCELADO', 'NAO_CUMPROU'
                    ) THEN 1 ELSE 0 END) AS negados,
                    SUM(CASE WHEN status_execucao = 'EM_EXECUCAO'
                        THEN 1 ELSE 0 END) AS em_execucao,
                    SUM(CASE WHEN status_execucao = 'CONCLUIDO'
                        THEN 1 ELSE 0 END) AS concluidos,
                    SUM(CASE WHEN status_execucao = 'CIENTE'
                        THEN 1 ELSE 0 END) AS cientes
                FROM v_emendas_unificadas
                WHERE parlamentar_nome ILIKE %s
            """,
            (parlamentar_nome,),
        )
        row = cur.fetchone()
        if not row:
            return {}
        res = _row_to_dict(row)
        if not res:
            return {}
        total = res.get("total_planos", 0)
        negados = res.get("negados", 0)
        res["taxa_sucesso"] = round(100.0 * (total - negados) / total, 1) if total > 0 else 0
        return res


def get_municipios_deputado(parlamentar_nome: str) -> list[dict]:
    """Retorna municípios beneficiários com dados IBGE."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    b.nome AS municipio,
                    b.uf,
                    mi.regiao,
                    mi.populacao,
                    mi.idhm,
                    COUNT(*) AS planos,
                    SUM(pa.valor_total) AS valor_total,
                    STRING_AGG(DISTINCT pa.plano_acao_situacao, ', ') AS situacoes
                FROM planos_acao pa
                JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
                LEFT JOIN beneficiario_ibge_map bm ON pa.beneficiario_id = bm.beneficiario_id
                LEFT JOIN municipios_ibge mi ON bm.municipio_id = mi.municipio_id
                WHERE pa.parlamentar_nome ILIKE %s
                GROUP BY b.nome, b.uf, mi.regiao, mi.populacao, mi.idhm
                ORDER BY valor_total DESC
            """,
            (parlamentar_nome,),
        )
        return _rows_to_list(cur.fetchall())


# ---------------------------------------------------------------------------
# Prefeitos & Inteligência Municipal
# ---------------------------------------------------------------------------


def search_prefeitos(query: str) -> list[dict]:
    """Busca prefeitos por nome do prefeito, cidade ou UF."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT municipio_id, municipio_nome, uf, prefeito_nome, prefeito_partido,
                       ibge_populacao, valor_total_emendas, emendas_per_capita
                FROM v_prefeitos_completo
                WHERE prefeito_nome ILIKE %s OR municipio_nome ILIKE %s OR uf ILIKE %s
                ORDER BY valor_total_emendas DESC
                LIMIT 20
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        )
        return _rows_to_list(cur.fetchall())


def get_perfil_prefeito(municipio_id: int) -> dict | None:
    """Retorna perfil completo do prefeito, indicadores do município e CNPJ da prefeitura."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT * FROM v_prefeitos_completo WHERE municipio_id = %s
            """,
            (municipio_id,),
        )
        res = _row_to_dict(cur.fetchone())
        if res:
            cur.execute(
                """
                    SELECT b.cnpj, b.nome AS razao_social
                    FROM beneficiarios b
                    JOIN beneficiario_ibge_map bim ON b.beneficiario_id = bim.beneficiario_id
                    WHERE bim.municipio_id = %s AND (b.nome ILIKE 'MUNICIPIO%%' OR b.nome ILIKE 'PREFEITURA%%' OR b.nome ILIKE 'GOVERNO%%')

                    LIMIT 1
                """,
                (municipio_id,),
            )
            cnpj_row = cur.fetchone()
            if cnpj_row:
                res["prefeitura_cnpj"] = cnpj_row["cnpj"]
                res["prefeitura_razao_social"] = cnpj_row["razao_social"]
            else:
                res["prefeitura_cnpj"] = None
                res["prefeitura_razao_social"] = None
        return res


def get_ranking_prefeitos(limit: int = 20) -> list[dict]:
    """Retorna ranking de prefeituras por captação de emendas."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT municipio_id, municipio_nome, uf, prefeito_nome, prefeito_partido,
                       ibge_populacao, valor_total_emendas, emendas_per_capita
                FROM v_prefeitos_completo
                ORDER BY valor_total_emendas DESC
                LIMIT %s
            """,
            (limit,),
        )
        return _rows_to_list(cur.fetchall())


def get_emendas_municipio(municipio_id: int, ano: int | None = None, limit: int = 100) -> dict:
    """Retorna as emendas destinadas ao município com o nome do parlamentar autor, filtrado opcionalmente por ano."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT DISTINCT pa.emenda_ano AS emenda_ano
                FROM planos_acao pa
                JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
                JOIN beneficiario_ibge_map bim ON b.beneficiario_id = bim.beneficiario_id
                WHERE bim.municipio_id = %s AND pa.emenda_ano IS NOT NULL
                ORDER BY pa.emenda_ano DESC
            """,
            (municipio_id,),
        )
        anos_disponiveis = [
            r["emenda_ano"] for r in cur.fetchall() if r.get("emenda_ano") is not None
        ]

        query = """
                SELECT
                    pa.plano_acao_id,
                    pa.emenda_codigo,
                    COALESCE(pa.parlamentar_nome, 'Não informado') AS parlamentar_nome,
                    COALESCE(o.descricao, 'Sem descrição') AS objeto_nome,
                    pa.plano_acao_situacao,
                    pa.valor_total,
                    pa.emenda_ano,
                    b.cnpj AS beneficiario_cnpj
                FROM planos_acao pa
                LEFT JOIN objetos o ON pa.objeto_id = o.objeto_id
                JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
                JOIN beneficiario_ibge_map bim ON b.beneficiario_id = bim.beneficiario_id
                WHERE bim.municipio_id = %s
            """
        params: list[int] = [municipio_id]

        if ano and ano > 0:
            query += " AND pa.emenda_ano = %s"
            params.append(ano)

        query += " ORDER BY pa.valor_total DESC LIMIT %s"
        params.append(limit)

        cur.execute(query, tuple(params))
        emendas = _rows_to_list(cur.fetchall())

        total_valor = sum(float(e["valor_total"] or 0) for e in emendas)
        total_planos = len(emendas)

        return {
            "anos_disponiveis": anos_disponiveis,
            "ano_selecionado": ano,
            "total_valor": total_valor,
            "total_planos": total_planos,
            "emendas": emendas,
        }


# ---------------------------------------------------------------------------
# Votações da Câmara
# ---------------------------------------------------------------------------


def get_votacoes_deputado(deputado_id: int, limit: int = 50, ano: int | None = None) -> list[dict]:
    """Retorna votações em que o deputado participou, com seu voto."""
    with _get_connection() as conn, conn.cursor() as cur:
        query = """
            SELECT
                v.votacao_id,
                v.tipo_voto,
                v.deputado_id,
                v.deputado_urna,
                v.sigla_partido,
                v.sigla_uf,
                vc.data_registro,
                vc.descricao,
                vc.aprovacao,
                vc.sigla_orgao,
                vc.proposicao_ementa,
                vc.tipo_evento
            FROM votos_camara v
            JOIN votacoes_camara vc ON v.votacao_id = vc.votacao_id
            WHERE v.deputado_id = %s
        """
        params: list = [deputado_id]
        if ano:
            query += " AND EXTRACT(YEAR FROM vc.data_registro) = %s"
            params.append(ano)
        query += " ORDER BY vc.data_registro DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, tuple(params))
        return _rows_to_list(cur.fetchall())


def get_resumo_votos_deputado(deputado_id: int) -> dict:
    """Retorna resumo agregado dos votos do deputado."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT * FROM v_resumo_votos_deputado
                WHERE deputado_id = %s
            """,
            (deputado_id,),
        )
        return _row_to_dict(cur.fetchone()) or {}


def get_resumo_votacao(votacao_id: str) -> dict:
    """Retorna resumo de uma votação específica."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT * FROM v_resumo_votacao
                WHERE votacao_id = %s
            """,
            (votacao_id,),
        )
        return _row_to_dict(cur.fetchone()) or {}


def get_votacoes_recentes(ano: int | None = None, limit: int = 20) -> list[dict]:
    """Retorna as votações mais recentes."""
    with _get_connection() as conn, conn.cursor() as cur:
        query = """
            SELECT vc.*, COALESCE(rv.total_votos, 0) AS total_votos,
                   rv.sims, rv.naos, rv.abstencoes, rv.obstrucoes
            FROM votacoes_camara vc
            LEFT JOIN v_resumo_votacao rv ON vc.votacao_id = rv.votacao_id
        """
        params: list = []
        if ano:
            query += " WHERE EXTRACT(YEAR FROM vc.data_registro) = %s"
            params.append(ano)
        query += " ORDER BY vc.data_registro DESC LIMIT %s"
        params.append(limit)
        cur.execute(query, tuple(params))
        return _rows_to_list(cur.fetchall())


def get_votos_por_votacao(votacao_id: str) -> list[dict]:
    """Retorna todos os votos de uma votação específica."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    deputado_id, deputado_nome, deputado_urna,
                    sigla_partido, sigla_uf, tipo_voto, em_segredo
                FROM votos_camara
                WHERE votacao_id = %s
                ORDER BY sigla_partido, deputado_nome
            """,
            (votacao_id,),
        )
        return _rows_to_list(cur.fetchall())


# ---------------------------------------------------------------------------
# Vereadores em Exercício (TSE / Eleições Municipais)
# ---------------------------------------------------------------------------


def search_vereadores(query: str) -> list[dict]:
    """Busca vereadores eleitos por nome, município, partido ou UF."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT sq_candidato, municipio_nome, uf, nome_completo,
                       nome_urna, partido, ano_eleicao, votos, percentual_votos,
                       situacao_candidatura, coligacao, ibge_populacao, ibge_regiao
                FROM v_vereadores_em_exercicio
                WHERE nome_completo ILIKE %s
                   OR nome_urna ILIKE %s
                   OR municipio_nome ILIKE %s
                   OR partido ILIKE %s
                   OR uf ILIKE %s
                ORDER BY votos DESC
                LIMIT 30
            """,
            (f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%", f"%{query}%"),
        )
        return _rows_to_list(cur.fetchall())


def get_ranking_vereadores(
    limit: int = 30,
    partido: str | None = None,
    uf: str | None = None,
) -> list[dict]:
    """Ranking de vereadores por votos, com filtros opcionais."""
    with _get_connection() as conn, conn.cursor() as cur:
        where_parts: list[str] = ["1=1"]
        params: list = []
        if partido:
            where_parts.append("partido = %s")
            params.append(partido.upper())
        if uf:
            where_parts.append("uf = %s")
            params.append(uf.upper())
        where_sql = " AND ".join(where_parts)
        params.append(limit)
        cur.execute(
            f"""
                SELECT sq_candidato, municipio_nome, uf, nome_completo,
                       nome_urna, partido, ano_eleicao, votos, percentual_votos,
                       situacao_candidatura, coligacao, ibge_populacao, ibge_regiao
                FROM v_vereadores_em_exercicio
                WHERE {where_sql}
                ORDER BY votos DESC
                LIMIT %s
            """,
            tuple(params),
        )
        return _rows_to_list(cur.fetchall())


def get_resumo_vereadores() -> dict:
    """Retorna KPIs agregados dos vereadores eleitos."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    COUNT(*) AS total_eleitos,
                    COUNT(DISTINCT municipio_id) AS total_municipios,
                    COUNT(DISTINCT partido) AS total_partidos,
                    COUNT(DISTINCT uf) AS total_ufs,
                    SUM(votos) AS total_votos,
                    ROUND(AVG(votos), 0) AS media_votos
                FROM v_vereadores_em_exercicio
            """
        )
        row = cur.fetchone()
        return _row_to_dict(row) or {}


def get_vereadores_por_partido(uf: str | None = None) -> list[dict]:
    """Retorna contagem de vereadores eleitos por partido, opcionalmente filtrado por UF."""
    with _get_connection() as conn, conn.cursor() as cur:
        if uf:
            cur.execute(
                """
                    SELECT partido, COUNT(*) AS total_eleitos, SUM(votos) AS total_votos
                    FROM v_vereadores_em_exercicio
                    WHERE uf = %s
                    GROUP BY partido
                    ORDER BY total_eleitos DESC
                """,
                (uf.upper(),),
            )
        else:
            cur.execute(
                """
                    SELECT partido, COUNT(*) AS total_eleitos, SUM(votos) AS total_votos
                    FROM v_vereadores_em_exercicio
                    GROUP BY partido
                    ORDER BY total_eleitos DESC
                """
            )
        return _rows_to_list(cur.fetchall())


def get_vereadores_por_municipio(municipio_id: int) -> list[dict]:
    """Retorna todos os vereadores eleitos de um município específico."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT sq_candidato, municipio_nome, uf, nome_completo,
                       nome_urna, partido, numero_candidato, ano_eleicao,
                       votos, percentual_votos, situacao_candidatura,
                       coligacao, ibge_populacao, ibge_regiao, ibge_idhm
                FROM v_vereadores_em_exercicio
                WHERE municipio_id = %s
                ORDER BY votos DESC
            """,
            (municipio_id,),
        )
        return _rows_to_list(cur.fetchall())


def get_vereadores_por_uf(uf: str) -> list[dict]:
    """Retorna todos os vereadores eleitos de uma UF."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT sq_candidato, municipio_nome, uf, nome_completo,
                       nome_urna, partido, numero_candidato, ano_eleicao,
                       votos, percentual_votos, situacao_candidatura,
                       coligacao, ibge_populacao, ibge_regiao
                FROM v_vereadores_em_exercicio
                WHERE uf = %s
                ORDER BY municipio_nome, votos DESC
            """,
            (uf.upper(),),
        )
        return _rows_to_list(cur.fetchall())


# ---------------------------------------------------------------------------
# Licitações Públicas & Fornecedores Vencedores da Prefeitura
# ---------------------------------------------------------------------------


def get_licitacoes_prefeitura(municipio_id: int, limit: int = 50) -> list[dict]:
    """Retorna as licitações e contratos públicos registrados para o município."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT id, fonte, tipo_documento, numero, descricao,
                       valor_estimado, valor_homologado, data_publicacao,
                       data_vigencia, modalidade, cnpj_orgao, nome_orgao,
                       cnpj_fornecedor, nome_fornecedor, status, uf
                FROM compras_municipios
                WHERE municipio_id = %s
                ORDER BY data_publicacao DESC NULLS LAST, id DESC
                LIMIT %s
            """,
            (municipio_id, limit),
        )
        return _rows_to_list(cur.fetchall())


def get_ganhadores_licitacoes_prefeitura(municipio_id: int, limit: int = 15) -> list[dict]:
    """Retorna o ranking de empresas e fornecedores vencedores de licitações no município."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT
                    cnpj_fornecedor,
                    nome_fornecedor AS razao_social,
                    COUNT(*) AS total_licitacoes_ganhas,
                    SUM(COALESCE(valor_homologado, valor_estimado, 0)) AS total_valor_ganho_brl
                FROM compras_municipios
                WHERE municipio_id = %s AND nome_fornecedor IS NOT NULL AND nome_fornecedor <> ''
                GROUP BY cnpj_fornecedor, nome_fornecedor
                ORDER BY total_valor_ganho_brl DESC, total_licitacoes_ganhas DESC
                LIMIT %s
            """,
            (municipio_id, limit),
        )
        return _rows_to_list(cur.fetchall())


# ---------------------------------------------------------------------------
# FNDE — Verbas Educacionais (FUNDEB, PNAE, PNLD, PNATE)
# ---------------------------------------------------------------------------


def get_fnde_resumo_estado(uf: str | None = None) -> list[dict]:
    """Retorna resumo FNDE por estado, opcionalmente filtrado por UF."""
    with _get_connection() as conn, conn.cursor() as cur:
        if uf:
            cur.execute(
                """
                    SELECT * FROM v_fnde_resumo_estado
                    WHERE uf = %s
                """,
                (uf.upper(),),
            )
        else:
            cur.execute("SELECT * FROM v_fnde_resumo_estado")
        return _rows_to_list(cur.fetchall())


def get_fnde_resumo_municipio(
    municipio_id: int | None = None,
    uf: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Retorna resumo FNDE por município, com filtros opcionais."""
    with _get_connection() as conn, conn.cursor() as cur:
        where_parts: list[str] = ["1=1"]
        params: list = []

        if municipio_id:
            where_parts.append("municipio_id = %s")
            params.append(municipio_id)
        if uf:
            where_parts.append("uf = %s")
            params.append(uf.upper())

        where_sql = " AND ".join(where_parts)
        params.append(limit)

        cur.execute(
            f"""
                SELECT * FROM v_fnde_resumo_municipio
                WHERE {where_sql}
                ORDER BY total_beneficiados DESC
                LIMIT %s
            """,
            tuple(params),
        )
        return _rows_to_list(cur.fetchall())


def get_fnde_programas_municipio(
    municipio_id: int,
    programa: str | None = None,
) -> list[dict]:
    """Retorna programas FNDE para um município específico."""
    with _get_connection() as conn, conn.cursor() as cur:
        if programa:
            cur.execute(
                """
                    SELECT * FROM v_fnde_programas_municipio
                    WHERE municipio_id = %s AND programa = %s
                    ORDER BY ano DESC
                """,
                (municipio_id, programa.upper()),
            )
        else:
            cur.execute(
                """
                    SELECT * FROM v_fnde_programas_municipio
                    WHERE municipio_id = %s
                    ORDER BY programa, ano DESC
                """,
                (municipio_id,),
            )
        return _rows_to_list(cur.fetchall())


def get_fnde_programas_disponiveis() -> list[dict]:
    """Retorna lista de programas FNDE disponíveis no banco."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT programa, COUNT(*) as total_registros,
                       MIN(ano) as ano_minimo, MAX(ano) as ano_maximo,
                       SUM(COALESCE(quantidade_matriculas, 0)) as total_matriculas,
                       SUM(COALESCE(quantidade_alunos, 0)) as total_alunos
                FROM fnde_repasses
                GROUP BY programa
                ORDER BY programa
            """
        )
        return _rows_to_list(cur.fetchall())


def search_fnde_municipios(query: str, limit: int = 20) -> list[dict]:
    """Busca municípios com dados FNDE por nome ou UF."""
    with _get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
                SELECT DISTINCT m.municipio_id, m.nome, m.uf, m.populacao
                FROM municipios_ibge m
                JOIN fnde_repasses f ON m.municipio_id = f.municipio_id
                WHERE m.nome ILIKE %s OR m.uf ILIKE %s
                ORDER BY m.nome
                LIMIT %s
            """,
            (f"%{query}%", f"%{query}%", limit),
        )
        return _rows_to_list(cur.fetchall())
