from __future__ import annotations

import logging
from typing import List, Dict, Any

from .db_service import _get_connection, _rows_to_list
from .camara_service import buscar_deputado, listar_despesas

log = logging.getLogger(__name__)

def get_party_efficiency() -> List[Dict[str, Any]]:
    """
    Agrupa emendas por partido e status de execução.
    Retorna a eficiência de execução de cada partido.
    """
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    pd.sigla_partido,
                    vu.status_execucao,
                    COUNT(vu.codigo_emenda) as total_emendas,
                    COALESCE(SUM(vu.valor_total), 0) as valor_total
                FROM v_emendas_unificadas vu
                JOIN parlamentares_dados pd ON vu.parlamentar_nome = pd.nome
                WHERE pd.sigla_partido IS NOT NULL
                GROUP BY pd.sigla_partido, vu.status_execucao
                ORDER BY pd.sigla_partido, vu.status_execucao
            """)
            return _rows_to_list(cur.fetchall())

def get_socioeconomic_data() -> List[Dict[str, Any]]:
    """
    Agrega o volume de emendas por município e cruza com IDHM e PIB per capita.
    """
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    mi.nome as municipio,
                    mi.uf,
                    mi.idhm,
                    mi.pib_per_capita,
                    mi.populacao,
                    COALESCE(SUM(vu.valor_total), 0) as total_emendas,
                    COUNT(vu.codigo_emenda) as qtd_emendas
                FROM v_emendas_unificadas vu
                -- Cruza com beneficiarios pelo nome
                JOIN beneficiarios b ON vu.beneficiario_nome = b.nome
                JOIN beneficiario_ibge_map bim ON b.beneficiario_id = bim.beneficiario_id
                JOIN municipios_ibge mi ON bim.municipio_id = mi.municipio_id
                WHERE mi.idhm IS NOT NULL AND vu.valor_total > 0
                GROUP BY mi.nome, mi.uf, mi.idhm, mi.pib_per_capita, mi.populacao
                ORDER BY total_emendas DESC
                LIMIT 500
            """)
            return _rows_to_list(cur.fetchall())

async def get_deputy_roi() -> List[Dict[str, Any]]:
    """
    Cruza as despesas totais do deputado na Câmara (Live API) com o valor total 
    das emendas que ele destinou. (Simula buscando top 20 parlamentares por emendas)
    """
    # 1. Fetch top 20 deputados from DB
    deputados = []
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    pd.deputado_id,
                    pd.nome_urna as nome,
                    pd.sigla_partido,
                    COALESCE(SUM(vu.valor_total), 0) as valor_emendas,
                    COUNT(vu.codigo_emenda) as qtd_emendas
                FROM v_emendas_unificadas vu
                JOIN parlamentares_dados pd ON vu.parlamentar_nome = pd.nome
                GROUP BY pd.deputado_id, pd.nome_urna, pd.sigla_partido
                ORDER BY valor_emendas DESC
                LIMIT 20
            """)
            deputados = _rows_to_list(cur.fetchall())
            
    # 2. Asynchronously fetch expenses for these 20 deputies
    for dep in deputados:
        try:
            despesas = await listar_despesas(dep["deputado_id"])
            total_despesas = sum([d.get("valorDocumento", 0) for d in despesas])
            dep["valor_despesas"] = total_despesas
        except Exception as e:
            log.error("Failed to fetch expenses for %s: %s", dep['nome'], e)
            dep["valor_despesas"] = 0
            
    return deputados

def get_top_municipios() -> List[Dict[str, Any]]:
    with _get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT b.municipio_id as ibge, m.nome, m.uf, SUM(p.valor_total) as total
                FROM planos_acao p
                JOIN beneficiario_ibge_map b ON p.beneficiario_id = b.beneficiario_id
                JOIN municipios_ibge m ON b.municipio_id = m.municipio_id
                GROUP BY b.municipio_id, m.nome, m.uf
                ORDER BY total DESC 
                LIMIT 12;
            """)
            return _rows_to_list(cur.fetchall())
