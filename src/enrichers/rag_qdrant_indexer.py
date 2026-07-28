"""
Indexer para base do Qdrant — v3 com novos chunk types e qualidade.

Fontes de dados indexadas:
  1. perfil                 — Nome, partido, UF do deputado
  2. proposicao             — PLs e proposicoes legislativas
  3. emenda                 — Emendas Pix (planos_acao) com dados financeiros do municipio
  4. voto                   — Padrao de voto com tema classificado (votacoes_temas.py)
  5. diario_oficial         — Atos do Diario Oficial
  6. conexao_politica       — Triangulo politico (deputado x prefeito x vereadores)
  7. emenda_discricionaria  — Convenios/transferencias discricionarias (NOVO)
  8. compras_municipio      — Compras publicas nos municipios receptores (NOVO)
  9. indicadores_sociais    — Saude + educacao municipal (NOVO)
  10. risco_judicial        — Processos judiciais via DataJud (NOVO)
  11. demografia_municipio  — Populacao, PIB, IDHM dos municipios (NOVO)

Model: nomic-embed-text-v1.5 (768d) | Metric: Cosine

Uso:
    ./run.sh cron-qdrant --limit 10
    ./run.sh cron-qdrant --nome "Afonso Florence"
    python3 -m src.enrichers.rag_qdrant_indexer --rebuild  # limpa e reindexa tudo
"""

import argparse
import json
import logging
import uuid
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from config.settings import (
    EMBEDDER_MODEL,
    EMBEDDING_DIM,
    QDRANT_COLLECTION,
    QDRANT_URL,
)
from src.db_utils import get_connection
from src.localai_client import LocalAIClient
from src.localai_manager import manager as localai_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Normalizacao de nomes para JOINs robustos (remove espacos, pontos, acentos via LOWER)
# Para unaccent completo, requer: CREATE EXTENSION IF NOT EXISTS unaccent;
# Usamos REPLACE + LOWER como alternativa sem dependencia de extensao.
_SQL_NORM: str = "REPLACE(REPLACE(LOWER({col}), ' ', ''), '.', '')"

CHUNK_TYPE_DESCRIPTIONS: dict[str, str] = {
    "perfil": "Perfil basico do deputado (nome, partido, UF)",
    "proposicao": "Proposicoes legislativas (PLs, PLPs, PECs)",
    "emenda": "Emendas Pix com dados financeiros do municipio receptor",
    "voto": "Padrao de voto em votacoes nominais com tema classificado",
    "diario_oficial": "Atos publicados no Diario Oficial da Uniao",
    "conexao_politica": "Triangulo politico: deputado x prefeito x vereadores eleitos",
    "emenda_discricionaria": "Convenios e transferencias discricionarias (Portal Transparencia)",
    "compras_municipio": "Compras publicas nos municipios receptores de emendas",
    "indicadores_sociais": "Indicadores de saude e educacao municipal (CNES/IDEB)",
    "risco_judicial": "Processos judiciais vinculados a beneficiarios (DataJud)",
    "demografia_municipio": "Dados demograficos dos municipios (IBGE: pop, PIB, IDHM)",
    "municipio_financeiro": "Dados financeiros municipais (SICONFI: receita, despesa, FPM, ICMS)",
    "parlamentar_resumo": "Resumo consolidado: total emendas, beneficiarios, municipios",
    "beneficiario": "Perfil de beneficiarios diretos (CNPJ, razao social, municipio)",
    "prefeito": "Perfil do prefeito municipal receptor de emendas",
    "senador": "Senadores em exercício no estado do deputado",
    "fnde_repasses": "Repasses educacionais FNDE nos municipios receptores",
    "indicadores_municipal": "Painel municipal: IDEB, saude, IDHM, leitos, matriculas",
    "vereadores_resumo": "Rede politica local: total vereadores, partido dominante, aliados",
}

# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------


def ensure_collection(client: QdrantClient, recreate: bool = False) -> None:
    """Cria ou recria a coleção Qdrant com configurações otimizadas e payload indexes."""
    try:
        collections = [c.name for c in client.get_collections().collections]
        if recreate and QDRANT_COLLECTION in collections:
            log.info(f"Recriando coleção {QDRANT_COLLECTION} (--rebuild)...")
            client.delete_collection(QDRANT_COLLECTION)

        if QDRANT_COLLECTION not in collections or recreate:
            log.info(f"Criando coleção {QDRANT_COLLECTION} ({EMBEDDING_DIM}d, cosine)...")
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=qdrant_models.VectorParams(
                    size=EMBEDDING_DIM,
                    distance=qdrant_models.Distance.COSINE,
                ),
                hnsw_config=qdrant_models.HnswConfigDiff(
                    m=32,
                    ef_construct=200,
                    full_scan_threshold=10000,
                ),
            )
            log.info("Coleção criada com sucesso.")

        # Garantir payload indexes para busca filtrada ultra-rápida (deputado_id, type, uf)
        log.info("Garantindo payload indexes no Qdrant...")
        for field, ftype in [
            ("deputado_id", qdrant_models.PayloadSchemaType.INTEGER),
            ("type", qdrant_models.PayloadSchemaType.KEYWORD),
            ("uf", qdrant_models.PayloadSchemaType.KEYWORD),
            ("municipio_ibge_id", qdrant_models.PayloadSchemaType.KEYWORD),
        ]:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field,
                field_schema=ftype,
            )
    except Exception as e:
        log.error(f"Erro ao verificar/criar coleção Qdrant: {e}")
        raise


# ---------------------------------------------------------------------------
# Batch embedding via LocalAIClient (com retry + cache)
# ---------------------------------------------------------------------------

_embed_client: LocalAIClient | None = None


def _get_embed_client() -> LocalAIClient:
    global _embed_client
    if _embed_client is None:
        _embed_client = LocalAIClient(model=EMBEDDER_MODEL)
    return _embed_client


def embed_text_batch(texts: list[str]) -> list[list[float]]:
    """Gera embeddings em batch via LocalAIClient (1 request para N textos)."""
    if not texts:
        return []
    client = _get_embed_client()
    try:
        return client.embed(texts)
    except Exception as e:
        log.error(f"Erro no batch embedding ({len(texts)} textos): {e}")
        return []


def embed_text(text: str) -> list[float] | None:
    """Embedding de um único texto (wrapper para compatibilidade)."""
    results = embed_text_batch([text])
    return results[0] if results else None


# ---------------------------------------------------------------------------
# Extração de dados do banco — cada fonte retorna lista de chunks
# ---------------------------------------------------------------------------


def _extract_perfil(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk 1: Perfil básico do deputado."""
    cur.execute(
        "SELECT nome, sigla_partido, uf FROM parlamentares_dados WHERE deputado_id = %s",
        (deputado_id,),
    )
    row = cur.fetchone()
    if not row:
        return []
    nome_full, partido, uf = row
    return [
        {
            "text": (
                f"Deputado Federal: {nome_full}. "
                f"Partido: {partido}. Estado: {uf}. "
                f"Atuação legislativa na Câmara dos Deputados."
            ),
            "type": "perfil",
            "deputado_id": deputado_id,
        }
    ]


def _extract_proposicoes(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Proposições legislativas (PLs, PLPs, PECs)."""
    cur.execute(
        "SELECT sigla_tipo, numero, ano, ementa FROM parlamentar_proposicoes "
        "WHERE deputado_id = %s",
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for sigla, num, ano, ementa in cur.fetchall():
        if not ementa:
            continue
        docs.append(
            {
                "text": (f"Proposição do deputado {nome}: {sigla} {num}/{ano}. Ementa: {ementa}"),
                "type": "proposicao",
                "deputado_id": deputado_id,
                "ref": f"{sigla} {num}/{ano}",
            }
        )
    return docs


def _extract_emendas(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Emendas Pix com dados financeiros do município (SICONFI)."""
    norm_pa = _SQL_NORM.format(col="pa.parlamentar_nome")
    norm_pd = _SQL_NORM.format(col="pd.nome_urna")
    norm_pd2 = _SQL_NORM.format(col="pd.nome")
    cur.execute(
        f"""
        SELECT b.nome, b.uf, o.descricao, pa.valor_total,
               mf.receitas_orcamentarias, mf.despesas_totais, mf.divida_passiva
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN objetos o ON pa.objeto_id = o.objeto_id
        JOIN parlamentares_dados pd
            ON {norm_pa} = {norm_pd} OR {norm_pa} = {norm_pd2}
        LEFT JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        LEFT JOIN municipios_financeiro mf
            ON bm.municipio_id = mf.municipio_id
            AND mf.exercicio = EXTRACT(YEAR FROM COALESCE(pa.data_atualizacao_plano_acao, NOW()))
        WHERE pd.deputado_id = %s
        ORDER BY pa.valor_total DESC NULLS LAST
        LIMIT 20
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for row in cur.fetchall():
        municipio, emp_uf, obj, valor, receita, despesa, divida = row
        txt = (
            f"Emenda do deputado {nome} para {municipio}-{emp_uf}. "
            f"Objeto: {obj}. Valor: R$ {valor:,.2f}."
        )
        # Enriquecer com dados financeiros do município (se disponíveis)
        if receita and despesa:
            txt += (
                f" Dados financeiros do município: receita orçamentária R$ {receita:,.2f}, "
                f"despesas totais R$ {despesa:,.2f}."
            )
            if divida:
                txt += f" Dívida passiva R$ {divida:,.2f}."
        docs.append(
            {
                "text": txt,
                "type": "emenda",
                "deputado_id": deputado_id,
                "ref": f"Emenda para {municipio}",
            }
        )
    return docs


def _extract_votos(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Padrão de voto em votações nominais (v3 com tema e ano dinamico).

    Requer extensao unaccent para buscas acentuadas:
        CREATE EXTENSION IF NOT EXISTS unaccent;
    """
    # 1. Resumo agregado: quantos SIM/NÃO/ABSTENÇÃO com range de anos
    cur.execute(
        """
        SELECT v.tipo_voto, COUNT(*) as n
        FROM votos_camara v
        WHERE v.deputado_id = %s
        GROUP BY v.tipo_voto
        ORDER BY n DESC
    """,
        (deputado_id,),
    )
    votos_agg: list[tuple[str, int]] = cur.fetchall()
    if not votos_agg:
        return []

    # Determinar range de anos a partir das datas de votacao
    cur.execute(
        """
        SELECT EXTRACT(YEAR FROM MIN(vc.data_registro))::int,
               EXTRACT(YEAR FROM MAX(vc.data_registro))::int
        FROM votos_camara v
        JOIN votacoes_camara vc ON v.votacao_id = vc.votacao_id
        WHERE v.deputado_id = %s
    """,
        (deputado_id,),
    )
    ano_range_row = cur.fetchone()
    if ano_range_row and ano_range_row[0] and ano_range_row[1]:
        ano_min, ano_max = int(ano_range_row[0]), int(ano_range_row[1])
        ano_text: str = str(ano_min) if ano_min == ano_max else f"{ano_min}-{ano_max}"
    else:
        ano_text = "desconhecido"

    total_votos: int = sum(n for _, n in votos_agg)
    partes: list[str] = [f"'{tv}': {n} vezes ({n * 100 // total_votos}%)" for tv, n in votos_agg]
    resumo_text: str = (
        f"Padrão de voto do deputado {nome} em {total_votos} votações nominais ({ano_text}): "
        f"{', '.join(partes)}."
    )

    docs: list[dict[str, Any]] = [
        {"text": resumo_text, "type": "voto", "deputado_id": deputado_id}
    ]

    # 2. Votos em destaque: votações onde votou contra a maioria (dissenso)
    #    Inclui tema classificado por votacoes_temas.py (coluna tema em votacoes_camara)
    cur.execute(
        """
        SELECT v.tipo_voto, vc.descricao, vc.aprovacao, COALESCE(vc.tema, '')
        FROM votos_camara v
        JOIN votacoes_camara vc ON v.votacao_id = vc.votacao_id
        WHERE v.deputado_id = %s
          AND v.tipo_voto IS NOT NULL
        ORDER BY v.id DESC
        LIMIT 30
    """,
        (deputado_id,),
    )
    for tipo_voto, descricao, aprovacao, tema in cur.fetchall():
        if not descricao or not tipo_voto:
            continue
        dissenso: bool = (
            (aprovacao is True and tipo_voto in ("Não", "Obstrução"))
            or (aprovacao is False and tipo_voto == "Sim")
        )

        prefixo: str = "[DISSENSO] " if dissenso else ""
        desc_trunc: str = descricao[:200] + ("..." if len(descricao) > 200 else "")
        tema_part: str = f" [{tema}]" if tema else ""
        txt = f"{prefixo}Voto{tema_part} em {desc_trunc} — resultado: {'Aprovado' if aprovacao else 'Reprovado'}, voto: {tipo_voto}"
        docs.append({"text": txt, "type": "voto", "deputado_id": deputado_id})

    return docs


def _extract_diario_oficial(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Atos do Diário Oficial (via alertas)."""
    cur.execute(
        """
        SELECT da.orgao, da.tipo_ato, da.resumo_ia, da.valor_financeiro,
               da.entidades_citadas
        FROM parlamentar_alertas pa
        JOIN diario_oficial_atos da ON pa.ato_id = da.ato_id
        WHERE pa.parlamentar_nome = %s
           OR pa.parlamentar_nome = (
               SELECT nome_urna FROM parlamentares_dados
               WHERE deputado_id = %s LIMIT 1
           )
    """,
        (nome, deputado_id),
    )
    docs: list[dict[str, Any]] = []
    for orgao, tipo_ato, resumo, valor, entidades in cur.fetchall():
        txt = f"Ato Oficial ({tipo_ato}) em {orgao}. Resumo: {resumo}."
        if entidades and entidades != "[]":
            txt += f" Entidades citadas: {entidades}."
        if valor:
            txt += f" Valor associado: R$ {valor:,.2f}."
        docs.append(
            {
                "text": txt,
                "type": "diario_oficial",
                "deputado_id": deputado_id,
                "ref": f"Ato: {tipo_ato}",
            }
        )
    return docs


def _extract_prefeitos_aliados(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Triangulo politico — Deputado x Prefeito x Vereadores (via v_triangulo_politico)."""
    cur.execute(
        """
        SELECT municipio_nome, partido_deputado, prefeito_nome, partido_prefeito,
               relacao_partidaria_prefeito, vereadores_eleitos_partido_dep,
               total_planos_acao, total_emendas_brl
        FROM v_triangulo_politico
        WHERE deputado_id = %s
        ORDER BY total_emendas_brl DESC
        LIMIT 15
    """,
        (deputado_id,),
    )

    docs: list[dict[str, Any]] = []
    for (
        municipio,
        part_dep,
        pref_nome,
        part_pref,
        relacao,
        veread_dep,
        n_planos,
        valor,
    ) in cur.fetchall():
        txt = (
            f"Conexao politica em {municipio}: Prefeito {pref_nome} ({part_pref}). "
            f"Relacao com deputado {nome} ({part_dep}): {relacao}. "
            f"Vereadores eleitos do partido do deputado: {veread_dep}. "
            f"Planos de acao: {n_planos}, total emendas R$ {valor:,.2f}."
        )
        docs.append(
            {
                "text": txt,
                "type": "conexao_politica",
                "deputado_id": deputado_id,
                "ref": f"Prefeito de {municipio}",
            }
        )
    return docs


def _extract_emendas_discricionarias(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Emendas discricionarias (convenios/transferencias do Portal Transparencia)."""
    norm = _SQL_NORM.format(col="ed.parlamentar_nome")
    cur.execute(
        f"""
        SELECT ed.ano, ed.valor_total, ed.objeto, ed.status_execucao
        FROM emendas_discricionarias ed
        JOIN parlamentares_dados pd ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
                                  OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        WHERE pd.deputado_id = %s
          AND ed.valor_total IS NOT NULL
        ORDER BY ed.valor_total DESC
        LIMIT 15
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for ano, valor, objeto, status in cur.fetchall():
        if not valor:
            continue
        desc_part: str = f" — {objeto}" if objeto else ""
        status_part: str = f" — Situacao: {status}" if status else ""
        txt = (
            f"Emenda Discricionaria {ano or '?'} do deputado {nome}: "
            f"R$ {valor:,.2f}{desc_part}{status_part}"
        )
        docs.append({"text": txt, "type": "emenda_discricionaria", "deputado_id": deputado_id})
    return docs


def _extract_compras_municipio(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Compras publicas nos municipios receptores de emendas do deputado."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT mib.nome, COUNT(DISTINCT cm.id) as n_compras,
               SUM(COALESCE(cm.valor_homologado, cm.valor_estimado, 0)) as valor_total,
               STRING_AGG(DISTINCT cm.nome_orgao, ', ' ORDER BY cm.nome_orgao)
                   FILTER (WHERE cm.nome_orgao IS NOT NULL) as orgaos
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN compras_municipios cm ON bm.municipio_id = cm.municipio_id
        JOIN municipios_ibge mib ON cm.municipio_id = mib.municipio_id
        WHERE pd.deputado_id = %s
        GROUP BY mib.nome
        ORDER BY valor_total DESC
        LIMIT 10
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for municipio, n_compras, valor_total, orgaos in cur.fetchall():
        if not valor_total or valor_total == 0:
            continue
        orgao_part: str = f" — Orgaos: {orgaos}" if orgaos else ""
        txt = (
            f"Compras publicas no municipio {municipio} (receptor de emendas do deputado {nome}): "
            f"{n_compras} licitacoes/contratos, R$ {valor_total:,.2f}{orgao_part}"
        )
        docs.append({"text": txt, "type": "compras_municipio", "deputado_id": deputado_id})
    return docs


def _extract_indicadores_sociais(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Indicadores de saude e educacao nos municipios receptores de emendas."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT mib.nome,
               sm.total_estabelecimentos, sm.total_leitos, sm.leitos_sus,
               sm.hospitais, sm.ubs, sm.total_profissionais,
               em.ideb_initial_years, em.ideb_final_years,
               em.taxa_aprovacao, em.matriculas_totais, em.escolas_totais
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        LEFT JOIN saude_municipios sm ON bm.municipio_id = sm.municipio_id
        LEFT JOIN educacao_municipios em ON bm.municipio_id = em.municipio_id
        WHERE pd.deputado_id = %s
          AND (sm.municipio_id IS NOT NULL OR em.municipio_id IS NOT NULL)
        GROUP BY mib.nome, sm.total_estabelecimentos, sm.total_leitos, sm.leitos_sus,
                 sm.hospitais, sm.ubs, sm.total_profissionais,
                 em.ideb_initial_years, em.ideb_final_years, em.taxa_aprovacao,
                 em.matriculas_totais, em.escolas_totais
        LIMIT 10
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for row in cur.fetchall():
        (
            municipio,
            estab, leitos, leitos_sus, hosp, ubs, prof,
            ideb_i, ideb_f, aprov, matric, escolas,
        ) = row
        partes: list[str] = []
        if estab or leitos:
            saude_parts: list[str] = []
            if estab:
                saude_parts.append(f"{estab} estabelecimentos ({hosp or 0} hosp, {ubs or 0} UBS)")
            if leitos:
                saude_parts.append(f"{leitos} leitos ({leitos_sus or 0} SUS)")
            if prof:
                saude_parts.append(f"{prof} profissionais")
            partes.append(f"Saude: {', '.join(saude_parts)}")
        if ideb_i or ideb_f or aprov:
            edu_parts: list[str] = []
            if ideb_i:
                edu_parts.append(f"IDEB iniciais {ideb_i}")
            if ideb_f:
                edu_parts.append(f"IDEB finais {ideb_f}")
            if aprov:
                edu_parts.append(f"aprovacao {aprov}%")
            if matric:
                edu_parts.append(f"{matric} matriculas")
            partes.append(f"Educacao: {', '.join(edu_parts)}")
        if not partes:
            continue
        txt = (
            f"Indicadores sociais do municipio {municipio} "
            f"(receptor de emendas do deputado {nome}): {' — '.join(partes)}."
        )
        docs.append({"text": txt, "type": "indicadores_sociais", "deputado_id": deputado_id})
    return docs


def _extract_risco_judicial(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Processos judiciais vinculados a beneficiarios do deputado (DataJud)."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT mib.nome, bp.total_processos, bp.processos_detalhes
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        JOIN beneficiario_processos bp ON b.cnpj = bp.cnpj
        WHERE pd.deputado_id = %s
          AND bp.total_processos > 0
        ORDER BY bp.total_processos DESC
        LIMIT 10
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for municipio, total, detalhes in cur.fetchall():
        if not total or total == 0:
            continue
        partes: list[str] = []
        if isinstance(detalhes, str):
            try:
                detalhes = json.loads(detalhes)
            except (ValueError, TypeError):
                detalhes = {}
        if isinstance(detalhes, dict):
            processos = detalhes.get("processos", detalhes.get("data", []))
            if isinstance(processos, list):
                for proc in processos[:5]:
                    if isinstance(proc, dict):
                        classe = proc.get("classe", proc.get("classeJudicial", ""))
                        assunto = proc.get("assunto", proc.get("assuntoPrincipal", ""))
                        data_disp = proc.get(
                            "dataDistribuicao",
                            proc.get("dataistribuicao", proc.get("data", "")),
                        )
                        if classe or assunto:
                            partes.append(
                                f"{classe} — {assunto}"
                                + (f" (distribuido em {data_disp})" if data_disp else "")
                            )
        if partes:
            resumo_proc: str = "; ".join(partes[:3])
        else:
            resumo_proc = f"{total} processos judiciais"
        txt = (
            f"Risco judicial no municipio {municipio} (beneficiario do deputado {nome}): "
            f"{resumo_proc}."
        )
        docs.append({"text": txt, "type": "risco_judicial", "deputado_id": deputado_id})
    return docs


def _extract_demografia_municipio(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Dados demograficos dos municipios receptores de emendas (IBGE)."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT DISTINCT mib.nome, mib.populacao, mib.pib_per_capita,
               mib.area_km2, mib.idhm, mib.densidade_demografica
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        WHERE pd.deputado_id = %s
          AND mib.populacao IS NOT NULL
        ORDER BY mib.populacao DESC
        LIMIT 10
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for municipio, pop, pib_pc, area, idhm, densidade in cur.fetchall():
        partes: list[str] = []
        if pop:
            partes.append(f"Pop {pop:,}")
        if pib_pc:
            partes.append(f"PIB per capita R$ {pib_pc:,.2f}")
        if area:
            partes.append(f"{area:,.1f} km2")
        if idhm:
            partes.append(f"IDHM {idhm}")
        if densidade:
            partes.append(f"{densidade:,.1f} hab/km2")
        if not partes:
            continue
        txt = (
            f"Demografia de {municipio} (receptor de emendas do deputado {nome}): "
            f"{', '.join(partes)}."
        )
        docs.append({"text": txt, "type": "demografia_municipio", "deputado_id": deputado_id})
    return docs


# ---------------------------------------------------------------------------
# Fase 1: Novos chunk types — municipio_financeiro, parlamentar_resumo,
#          beneficiario, prefeito, senador, fnde_repasses,
#          indicadores_municipal, vereadores_resumo
# ---------------------------------------------------------------------------


def _extract_municipio_financeiro(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Dados financeiros dos municipios receptores de emendas (SICONFI)."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT DISTINCT mib.nome, mib.municipio_id, mf.exercicio,
               mf.receitas_orcamentarias, mf.despesas_totais,
               mf.divida_passiva, mf.arrec_impostos_geral,
               mf.arrec_cota_fpm, mf.arrec_cota_icms, mf.arrec_iss
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        JOIN municipios_financeiro mf ON bm.municipio_id = mf.municipio_id
        WHERE pd.deputado_id = %s
          AND mf.receitas_orcamentarias IS NOT NULL
        ORDER BY mf.exercicio DESC, mf.receitas_orcamentarias DESC
        LIMIT 10
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for row in cur.fetchall():
        mun, mun_id, exerc, receita, despesa, divida, rec_impostos, fpm, icms, iss = row
        partes: list[str] = []
        if receita:
            partes.append(f"receita orçamentária R$ {receita:,.2f}")
        if despesa:
            partes.append(f"despesas totais R$ {despesa:,.2f}")
        if divida:
            partes.append(f"dívida passiva R$ {divida:,.2f}")
        if rec_impostos:
            partes.append(f"arrecadação impostos R$ {rec_impostos:,.2f}")
        # Fontes de receita
        fontes: list[str] = []
        if fpm:
            fontes.append(f"FPM R$ {fpm:,.2f}")
        if icms:
            fontes.append(f"ICMS R$ {icms:,.2f}")
        if iss:
            fontes.append(f"ISS R$ {iss:,.2f}")
        if not partes:
            continue
        txt = (
            f"Dados financeiros de {mun} (IBGE {mun_id}, exercício {exerc or '?'}), "
            f"município receptor de emendas do deputado {nome}: "
            f"{', '.join(partes)}."
        )
        if fontes:
            txt += f" Fontes de receita: {', '.join(fontes)}."
        docs.append({
            "text": txt, "type": "municipio_financeiro",
            "deputado_id": deputado_id, "municipio_ibge_id": mun_id,
            "uf": mun_id[:2] if mun_id else None,
        })
    return docs


def _extract_parlamentar_resumo(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Resumo consolidado do deputado (emendas, beneficiários, valores)."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT COUNT(DISTINCT pa.plano_acao_id) as n_planos,
               COUNT(DISTINCT b.beneficiario_id) as n_benef,
               COUNT(DISTINCT bm.municipio_id) as n_municipios,
               COALESCE(SUM(pa.valor_total), 0) as valor_total,
               pd.sigla_partido, pd.uf
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        LEFT JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        WHERE pd.deputado_id = %s
        GROUP BY pd.sigla_partido, pd.uf
    """,
        (deputado_id,),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return []
    n_planos, n_benef, n_municipios, valor_total, partido, uf = row
    txt = (
        f"Resumo do deputado {nome} ({partido}/{uf}): "
        f"{n_planos} planos de ação, {n_benef} beneficiários em {n_municipios} municípios, "
        f"valor total R$ {valor_total:,.2f}."
    )
    return [{
        "text": txt, "type": "parlamentar_resumo",
        "deputado_id": deputado_id,
    }]


def _extract_beneficiarios(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Perfil dos beneficiários diretos do deputado."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT DISTINCT b.nome, b.cnpj, b.uf,
               vc.razao_social, vc.situacao_cadastral, pa.valor_total
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        LEFT JOIN validacao_cnpj vc ON b.cnpj = vc.cnpj
        WHERE pd.deputado_id = %s
        ORDER BY pa.valor_total DESC NULLS LAST
        LIMIT 15
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for b_nome, cnpj, uf, razao, sit, _valor in cur.fetchall():
        razao_part = f" ({razao})" if razao else ""
        sit_part = f" — situação: {sit}" if sit else ""
        txt = (
            f"Beneficiário{razao_part} {b_nome} em {uf} "
            f"(CNPJ {cnpj or 'N/A'}){sit_part}, receptor de emendas do deputado {nome}."
        )
        docs.append({
            "text": txt, "type": "beneficiario",
            "deputado_id": deputado_id,
        })
    return docs


def _extract_prefeitos(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Perfil dos prefeitos nos municípios receptores de emendas."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT DISTINCT pf.prefeito_nome, pf.municipio_nome, pf.sigla_partido,
               pf.ano_eleicao, pf.coligacao
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados dep
            ON {norm} = {_SQL_NORM.format(col='dep.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='dep.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN prefeitos_dados pf ON bm.municipio_id = pf.municipio_id
        WHERE dep.deputado_id = %s
        ORDER BY pf.ano_eleicao DESC
        LIMIT 10
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for pf_nome, municipio, partido, ano, colig in cur.fetchall():
        colig_part = f" Coligação: {colig}." if colig else ""
        txt = (
            f"Prefeito(a) de {municipio}: {pf_nome} ({partido}), "
            f"eleito(a) em {ano or '?'}, "
            f"município receptor de emendas do deputado {nome}.{colig_part}"
        )
        docs.append({
            "text": txt, "type": "prefeito",
            "deputado_id": deputado_id,
        })
    return docs


def _extract_senadores(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Senadores em exercício no estado do deputado."""
    cur.execute(
        "SELECT uf FROM parlamentares_dados WHERE deputado_id = %s",
        (deputado_id,),
    )
    row = cur.fetchone()
    if not row:
        return []
    uf = row[0]
    cur.execute(
        "SELECT nome_parlamentar, sigla_partido, email, legislatura "
        "FROM senadores_dados WHERE uf = %s AND situacao = 'Exercício'",
        (uf,),
    )
    docs: list[dict[str, Any]] = []
    for s_nome, partido, email, _leg in cur.fetchall():
        txt = (
            f"Senador(a) {s_nome} ({partido}) em exercício em {uf}. "
            f"Conexão federal relevante para deputado {nome} ({uf})."
        )
        docs.append({
            "text": txt, "type": "senador",
            "deputado_id": deputado_id,
        })
    return docs


def _extract_fnde_repasses(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Repasses FNDE nos municípios receptores de emendas."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT DISTINCT mib.nome, fr.programa, fr.valor_total,
               fr.ano, fr.descricao_programa
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        JOIN fnde_repasses fr ON bm.municipio_id = fr.municipio_id
        WHERE pd.deputado_id = %s
        ORDER BY fr.valor_total DESC NULLS LAST
        LIMIT 10
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for municipio, programa, valor, ano, sit in cur.fetchall():
        val_part = f" — R$ {valor:,.2f}" if valor else ""
        sit_part = f" (situação: {sit})" if sit else ""
        txt = (
            f"FNDE em {municipio}: programa {programa or 'N/A'}{val_part}, "
            f"ano {ano or '?'}{sit_part}. "
            f"Município receptor de emendas do deputado {nome}."
        )
        docs.append({
            "text": txt, "type": "fnde_repasses",
            "deputado_id": deputado_id,
        })
    return docs


def _extract_indicadores_municipal(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Painel consolidado de indicadores municipais (saúde + educação + IBGE)."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT DISTINCT mib.nome, mib.populacao, mib.idhm,
               sm.total_leitos, sm.total_profissionais,
               em.ideb_initial_years, em.ideb_final_years,
               em.taxa_aprovacao, em.matriculas_totais
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        LEFT JOIN saude_municipios sm ON bm.municipio_id = sm.municipio_id
        LEFT JOIN educacao_municipios em ON bm.municipio_id = em.municipio_id
        WHERE pd.deputado_id = %s
          AND (sm.municipio_id IS NOT NULL OR em.municipio_id IS NOT NULL)
        ORDER BY mib.populacao DESC NULLS LAST
        LIMIT 8
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for row in cur.fetchall():
        mun, pop, idhm, leitos, prof, ideb_i, ideb_f, aprov, matric = row
        partes: list[str] = []
        if pop:
            partes.append(f"pop {pop:,}")
        if idhm:
            partes.append(f"IDHM {idhm}")
        if leitos:
            partes.append(f"{leitos} leitos SUS")
        if prof:
            partes.append(f"{prof} prof. saúde")
        if ideb_i or ideb_f:
            partes.append(f"IDEB {ideb_i or '?'}-{ideb_f or '?'}")
        if aprov:
            partes.append(f"aprovação {aprov}%")
        if matric:
            partes.append(f"{matric} matrículas")
        if not partes:
            continue
        txt = (
            f"Painel municipal de {mun} (receptor de emendas do deputado {nome}): "
            f"{', '.join(partes)}."
        )
        docs.append({
            "text": txt, "type": "indicadores_municipal",
            "deputado_id": deputado_id,
        })
    return docs


def _extract_vereadores_resumo(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Resumo de vereadores nos municípios receptores de emendas."""
    norm = _SQL_NORM.format(col="pa.parlamentar_nome")
    cur.execute(
        f"""
        SELECT mib.nome, mib.municipio_id,
               COUNT(*) as n_veread,
               MODE() WITHIN GROUP (ORDER BY vd.sigla_partido) as partido_mais,
               SUM(CASE WHEN vd.sigla_partido = pd.sigla_partido THEN 1 ELSE 0 END) as aliados
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd
            ON {norm} = {_SQL_NORM.format(col='pd.nome_urna')}
           OR {norm} = {_SQL_NORM.format(col='pd.nome')}
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        JOIN vereadores_dados vd ON bm.municipio_id = vd.municipio_id
        WHERE pd.deputado_id = %s
        GROUP BY mib.nome, mib.municipio_id
        ORDER BY n_veread DESC
        LIMIT 10
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for municipio, _ibge_id, n_veread, partido_mais, aliados in cur.fetchall():
        aliados = aliados or 0
        txt = (
            f"Rede política em {municipio}: {n_veread} vereadores, "
            f"partido dominante: {partido_mais or 'N/A'}, "
            f"{aliados} aliados do deputado {nome} (mesmo partido)."
        )
        docs.append({
            "text": txt, "type": "vereadores_resumo",
            "deputado_id": deputado_id,
        })
    return docs


# ---------------------------------------------------------------------------
# Orchestrador: extrai todos os chunks de um deputado
# ---------------------------------------------------------------------------


def get_deputado_texts(deputado_id: int) -> list[dict[str, Any]]:
    """Extrai chunks de TODAS as fontes para um deputado."""
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT nome FROM parlamentares_dados WHERE deputado_id = %s",
            (deputado_id,),
        )
        row = cur.fetchone()
        if not row:
            return []
        nome = row[0]

        docs: list[dict[str, Any]] = []
        docs.extend(_extract_perfil(cur, deputado_id, nome))
        docs.extend(_extract_proposicoes(cur, deputado_id, nome))
        docs.extend(_extract_emendas(cur, deputado_id, nome))
        docs.extend(_extract_votos(cur, deputado_id, nome))
        docs.extend(_extract_diario_oficial(cur, deputado_id, nome))
        docs.extend(_extract_prefeitos_aliados(cur, deputado_id, nome))
        docs.extend(_extract_emendas_discricionarias(cur, deputado_id, nome))
        docs.extend(_extract_compras_municipio(cur, deputado_id, nome))
        docs.extend(_extract_indicadores_sociais(cur, deputado_id, nome))
        docs.extend(_extract_risco_judicial(cur, deputado_id, nome))
        docs.extend(_extract_demografia_municipio(cur, deputado_id, nome))
        # Fase 1: Novos chunk types
        docs.extend(_extract_municipio_financeiro(cur, deputado_id, nome))
        docs.extend(_extract_parlamentar_resumo(cur, deputado_id, nome))
        docs.extend(_extract_beneficiarios(cur, deputado_id, nome))
        docs.extend(_extract_prefeitos(cur, deputado_id, nome))
        docs.extend(_extract_senadores(cur, deputado_id, nome))
        docs.extend(_extract_fnde_repasses(cur, deputado_id, nome))
        docs.extend(_extract_indicadores_municipal(cur, deputado_id, nome))
        docs.extend(_extract_vereadores_resumo(cur, deputado_id, nome))
        return docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Popula o Qdrant com dados dos Deputados para RAG (v2)"
    )
    parser.add_argument("--limit", type=int, default=10, help="Número de deputados a processar")
    parser.add_argument("--nome", type=str, help="Nome do deputado (busca exata por ILIKE)")
    parser.add_argument("--rebuild", action="store_true", help="Recriar coleção do zero")
    args = parser.parse_args()

    # 1. Carregar embedder
    log.info("Carregando modelo de embeddings...")
    localai_manager.ensure_model_loaded(EMBEDDER_MODEL)

    # 2. Conectar Qdrant
    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client, recreate=args.rebuild)

    # 3. Buscar deputados para indexar
    with get_connection() as conn, conn.cursor() as cur:
        if args.nome:
            cur.execute(
                """
                SELECT deputado_id, nome
                FROM parlamentares_dados
                WHERE nome ILIKE %s OR nome_urna ILIKE %s
            """,
                (f"%{args.nome}%", f"%{args.nome}%"),
            )
        else:
            # Priorizar deputados com mais dados (alertas DO + votos)
            cur.execute(
                """
                SELECT pd.deputado_id, pd.nome,
                    (SELECT COUNT(*) FROM parlamentar_alertas pa
                     WHERE pa.parlamentar_nome IN (pd.nome, pd.nome_urna)) as n_alertas,
                    (SELECT COUNT(*) FROM votos_camara vc
                     WHERE vc.deputado_id = pd.deputado_id) as n_votos
                FROM parlamentares_dados pd
                ORDER BY n_alertas DESC, n_votos DESC, pd.deputado_id ASC
                LIMIT %s
            """,
                (args.limit,),
            )
        deputados = cur.fetchall()

    if not deputados:
        log.info("Nenhum deputado encontrado para indexar.")
        return

    log.info(f"Indexando {len(deputados)} deputados no Qdrant...")
    total_points = 0

    for idx, dep_row in enumerate(deputados, 1):
        deputado_id = dep_row[0]
        nome = dep_row[1]

        # Extrair chunks
        docs = get_deputado_texts(deputado_id)
        if not docs:
            log.warning(f"  [{idx}/{len(deputados)}] {nome}: sem dados, pulando.")
            continue

        # Batch embedding (1 request para todos os chunks)
        texts = [d["text"] for d in docs]
        vectors = embed_text_batch(texts)

        # Montar points
        points: list[qdrant_models.PointStruct] = []
        for doc, vector in zip(docs, vectors):
            if not vector or len(vector) != EMBEDDING_DIM:
                continue
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{deputado_id}_{doc['text']}"))
            points.append(
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=doc,
                )
            )

        # Upsert
        if points:
            client.upsert(collection_name=QDRANT_COLLECTION, points=points)
            total_points += len(points)

        if idx % 10 == 0 or idx == len(deputados):
            log.info(
                f"  [{idx}/{len(deputados)}] {nome}: {len(docs)} chunks, "
                f"{len(points)} vetores → total {total_points}"
            )

    log.info(
        f"Indexação concluída: {len(deputados)} deputados, "
        f"{total_points} vetores inseridos no Qdrant."
    )


if __name__ == "__main__":
    main()
