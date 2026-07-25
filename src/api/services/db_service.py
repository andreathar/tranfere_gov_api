"""
Serviço de consultas PostgreSQL para o Painel de Deputados.

Consulta o banco transferegov_db para dados de parlamentares,
planos de ação (emendas pix) e municípios beneficiários.
"""

from __future__ import annotations

import logging
from decimal import Decimal

import psycopg2
from psycopg2.extras import RealDictCursor

from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER

log = logging.getLogger(__name__)


def _get_connection():
    """Cria conexão com o PostgreSQL transferegov_db."""
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
        cursor_factory=RealDictCursor,
    )


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
    with _get_connection() as conn:
        with conn.cursor() as cur:
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
    with _get_connection() as conn:
        with conn.cursor() as cur:
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
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
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
            """, (parlamentar_nome,))
            return _rows_to_list(cur.fetchall())


def get_resumo_emendas(parlamentar_nome: str) -> dict:
    """Retorna KPIs agregados das emendas do parlamentar."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
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
            """, (parlamentar_nome,))
            row = cur.fetchone()
            if not row:
                return {}
            res = _row_to_dict(row)
            total = res.get("total_planos", 0)
            negados = res.get("negados", 0)
            res["taxa_sucesso"] = (
                round(100.0 * (total - negados) / total, 1) if total > 0 else 0
            )
            return res


def get_municipios_deputado(parlamentar_nome: str) -> list[dict]:
    """Retorna municípios beneficiários com dados IBGE."""
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
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
            """, (parlamentar_nome,))
            return _rows_to_list(cur.fetchall())
