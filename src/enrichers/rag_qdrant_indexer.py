"""
Indexer para base do Qdrant — v5+ com 20 chunk types otimizados.

Fontes de dados indexadas (20 tipos):
  1. perfil                 — Perfil enriquecido (escolaridade, naturalidade, situacao)
  2. proposicao             — PLs com resumo_ia e LIMIT 30
  3. emenda                 — Emendas Pix completas + situacao + contexto demografico inline + SICONFI
  4. voto                   — Padrao de voto com tema classificado (votacoes_temas.py)
  5. diario_oficial         — Atos DOU com nivel_relevancia e LIMIT 20
  6. conexao_politica       — Triangulo politico (deputado x prefeito x vereadores)
  7. emenda_discricionaria  — Emendas discricionarias completas com CNPJ + convenio + tipo_emenda
  8. compras_municipio      — Compras publicas nos municipios receptores
  9. indicadores_sociais    — Saude + educacao + IDHM + populacao (fundido)
  10. risco_judicial        — Processos judiciais via DataJud
  11. demografia_municipio  — Populacao, PIB, IDHM dos municipios
  12. municipio_financeiro  — SICONFI (receita, despesa, FPM, ICMS, ISS) com UF corrigida
  13. parlamentar_resumo    — Resumo consolidado emendas/beneficiarios
  14. beneficiario          — Perfil CNPJ com razao social e situacao
  15. prefeito              — Perfil prefeito com partido e coligacao
  16. senador               — Senadores em exercicio no estado
  17. fnde_repasses         — Repasses FNDE (FUNDEB, PNAE, PNLD)
  18. vereadores_resumo     — Rede politica local (aliados, partido dominante)
  19. parlamentar_alertas   — Alertas de relevancia no DOU vinculados ao deputado
  20. persona_existente     — Dossies/personas analiticas ja geradas (re-aproveitamento RAG)

Model: embeddinggemma-300m (768d) | Metric: Cosine

Melhorias FASE 5 implementadas:
  - JOINs migrados de nome fuzzy (f_unaccent + REPLACE) para parlamentar_id (indexado, 0 NULLs)
  - tipo_emenda incluido nos chunks de emenda_discricionaria
  - Novos chunk types: parlamentar_alertas (Fase 7), persona_existente (Fase 8)
  - _SQL_NORM removido -- todas as queries usam parlamentar_id agora

Uso:
    ./run.sh cron-qdrant --limit 10
    ./run.sh cron-qdrant --nome "Afonso Florence"
    python3 -m src.enrichers.rag_qdrant_indexer --rebuild  # limpa e reindexa tudo
"""

import argparse
import hashlib
import json
import logging
import re
import uuid
from collections import Counter
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

# NOTA: JOINs antes usavam _SQL_NORM (f_unaccent + REPLACE) para fuzzy match.
# Migrados para parlamentar_id (indexado, 0 NULLs) -- Fase 5.
# f_unaccent() continua disponivel no banco via migration 021.

CHUNK_TYPE_DESCRIPTIONS: dict[str, str] = {
    "perfil": "Perfil enriquecido do deputado (nome, partido, UF, escolaridade, naturalidade, situacao)",
    "proposicao": "Proposicoes legislativas (PLs, PLPs, PECs) com resumo_ia e LIMIT 30",
    "emenda": "Emendas Pix com contexto demografico inline (pop, IDHM) + financeiro SICONFI",
    "voto": "Padrao de voto em votacoes nominais com tema classificado",
    "diario_oficial": "Atos DOU com nivel de relevancia (1-5) e LIMIT 20",
    "conexao_politica": "Triangulo politico: deputado x prefeito x vereadores eleitos",
    "emenda_discricionaria": "Convenios com beneficiario CNPJ + tipo_emenda para rastreabilidade",
    "compras_municipio": "Compras publicas nos municipios receptores de emendas",
    "indicadores_sociais": "Indicadores sociais + demograficos (saude, IDEB, IDHM, populacao)",
    "risco_judicial": "Processos judiciais vinculados a beneficiarios (DataJud)",
    "demografia_municipio": "Dados demograficos dos municipios (IBGE: pop, PIB, IDHM)",
    "municipio_financeiro": "Dados financeiros municipais (SICONFI: receita, despesa, FPM, ICMS)",
    "parlamentar_resumo": "Resumo consolidado: total emendas, beneficiarios, municipios",
    "beneficiario": "Perfil de beneficiarios diretos (CNPJ, razao social, municipio)",
    "prefeito": "Perfil do prefeito municipal receptor de emendas",
    "senador": "Senadores em exercício no estado do deputado",
    "fnde_repasses": "Repasses educacionais FNDE nos municipios receptores",
    "vereadores_resumo": "Rede politica local: total vereadores, partido dominante, aliados",
    "parlamentar_alertas": "Alertas de relevancia no DOU com potencial vinculacao ao deputado",
    "persona_existente": "Dossies/personas analiticas ja geradas (re-aproveitamento entre ciclos RAG)",
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
            log.info(
                f"Criando coleção {QDRANT_COLLECTION} ({EMBEDDING_DIM}d, cosine + BM25 sparse)..."
            )
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config={
                    "dense": qdrant_models.VectorParams(
                        size=EMBEDDING_DIM,
                        distance=qdrant_models.Distance.COSINE,
                    ),
                },
                sparse_vectors_config={
                    "bm25": qdrant_models.SparseVectorParams(
                        index=qdrant_models.SparseIndexParams(on_disk=False),
                        modifier=qdrant_models.Modifier.IDF,
                    ),
                },
                hnsw_config=qdrant_models.HnswConfigDiff(
                    m=32,
                    ef_construct=200,
                    full_scan_threshold=10000,
                ),
            )
            log.info("Coleção criada com sucesso.")

        # Garantir payload indexes para busca filtrada ultra-rápida (deputado_id, type, uf, relevancia)
        log.info("Garantindo payload indexes no Qdrant...")
        for field, ftype in [
            ("deputado_id", qdrant_models.PayloadSchemaType.INTEGER),
            ("type", qdrant_models.PayloadSchemaType.KEYWORD),
            ("uf", qdrant_models.PayloadSchemaType.KEYWORD),
            ("municipio_ibge_id", qdrant_models.PayloadSchemaType.KEYWORD),
            ("nivel_relevancia", qdrant_models.PayloadSchemaType.INTEGER),
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
    """Gera embeddings em batch via LocalAIClient.

    Resiliencia: trunca textos longos (contexto real do modelo e 2048 tokens,
    nao 8192) e divide em sub-batches. Se um sub-batch falhar, tenta texto a
    texto pulando apenas os que falharem — um chunk problemático nao derruba o
    deputado inteiro (evita checkpoint 'envenenado' sem vetores).
    """
    if not texts:
        return []
    # Safeguard: 3000 chars PT-BR ≈ < 1300 tokens, bem abaixo do limite de 2048
    MAX_CHARS = 3000
    SUB_BATCH = 64
    texts = [t[:MAX_CHARS] if len(t) > MAX_CHARS else t for t in texts]
    client = _get_embed_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), SUB_BATCH):
        sub = texts[i : i + SUB_BATCH]
        try:
            emb = client.embed(sub)
            if not emb or len(emb) != len(sub):
                raise RuntimeError("resposta de tamanho inesperado")
            out.extend(emb)
        except Exception as e:
            log.error(
                f"Erro no batch embedding ({len(sub)} textos): {e}; "
                "tentando texto a texto (pulando os que falharem)..."
            )
            for t in sub:
                try:
                    one = client.embed([t])
                    if one:
                        out.append(one[0])
                except Exception:
                    log.warning(f"  embed individual falhou (pulando): {t[:80]!r}")
    return out


def embed_text(text: str) -> list[float] | None:
    """Embedding de um único texto (wrapper para compatibilidade)."""
    results = embed_text_batch([text])
    return results[0] if results else None


# ---------------------------------------------------------------------------
# Sparse vectors (BM25-style) para hybrid search
# ---------------------------------------------------------------------------


def _tokenize_text(text: str) -> list[str]:
    """Tokeniza texto para geração de sparse vector BM25.

    Preserva palavras acentuadas (português), siglas e números.
    Ex: 'SICONFI' → ['siconfi'], 'FPM' → ['fpm'], 'R$ 1.500,00' → ['r', '1', '500', '00']
    """
    text = text.lower()
    return re.findall(r"[a-zà-ÿ0-9]+", text)


def _token_to_index(token: str) -> int:
    """Hash determinístico de token → índice uint32 para sparse vector."""
    return int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16)


def text_to_sparse_vector(text: str) -> qdrant_models.SparseVector:
    """Converte texto em sparse vector TF (raw term frequency).

    Usa top-200 tokens mais frequentes para manter o vetor esparso eficiente.
    O IDF é aplicado pelo Qdrant em tempo de busca (modifier=IDF no SparseVectorParams).
    """
    tokens = _tokenize_text(text)
    if not tokens:
        return qdrant_models.SparseVector(indices=[0], values=[0.0])

    tf = Counter(tokens)
    indices: list[int] = []
    values: list[float] = []
    for token, count in tf.most_common(200):
        indices.append(_token_to_index(token))
        values.append(float(count))

    return qdrant_models.SparseVector(indices=indices, values=values)


def texts_to_sparse_vectors(texts: list[str]) -> list[qdrant_models.SparseVector]:
    """Batch convert textos para sparse vectors."""
    return [text_to_sparse_vector(t) for t in texts]


# ---------------------------------------------------------------------------
# Extração de dados do banco — cada fonte retorna lista de chunks
# ---------------------------------------------------------------------------


def _extract_perfil(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk 1: Perfil enriquecido do deputado (11 campos disponíveis)."""
    cur.execute(
        "SELECT nome, sigla_partido, uf, escolaridade, "
        "municipio_nascimento, uf_nascimento, situacao "
        "FROM parlamentares_dados WHERE deputado_id = %s",
        (deputado_id,),
    )
    row = cur.fetchone()
    if not row:
        return []
    nome_full, partido, uf, escolaridade, mun_nasc, uf_nasc, situacao = row
    txt = (
        f"Deputado Federal {nome_full} ({partido}/{uf}). "
        f"Situacao: {situacao or 'ativo'}. "
        f"Escolaridade: {escolaridade or 'N/I'}. "
        f"Natural de {mun_nasc or 'N/I'}/{uf_nasc or 'N/I'}. "
        f"Atuacao legislativa na Camara dos Deputados."
    )
    return [
        {
            "text": txt,
            "type": "perfil",
            "deputado_id": deputado_id,
        }
    ]


def _extract_proposicoes(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Proposições legislativas (PLs, PLPs, PECs) com resumo_ia e LIMIT 30."""
    cur.execute(
        "SELECT sigla_tipo, numero, ano, COALESCE(resumo_ia, ementa) "
        "FROM parlamentar_proposicoes "
        "WHERE deputado_id = %s "
        "ORDER BY data_apresentacao DESC NULLS LAST "
        "LIMIT 30",
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for sigla, num, ano, texto in cur.fetchall():
        if not texto:
            continue
        docs.append(
            {
                "text": (f"Proposicao legislativa de {nome}: {sigla} {num}/{ano}. {texto}"),
                "type": "proposicao",
                "deputado_id": deputado_id,
                "ref": f"{sigla} {num}/{ano}",
            }
        )
    return docs


def _extract_emendas(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Emendas Pix com dados financeiros + contexto demográfico inline.

    Sem LIMIT artificial — todas as emendas do deputado são indexadas.
    A seleção dos chunks mais relevantes é feita pelo Qdrant via HNSW em tempo de busca.
    O prompt final é limitado por RAG_MAX_CHUNKS (rag_persona.py).
    """
    cur.execute(
        """
        SELECT b.nome, b.uf, o.descricao, pa.valor_total,
               pa.plano_acao_situacao,
               mf.receitas_orcamentarias, mf.despesas_totais, mf.divida_passiva,
               mib.populacao, mib.idhm
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN objetos o ON pa.objeto_id = o.objeto_id
        LEFT JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        LEFT JOIN municipios_financeiro mf
            ON bm.municipio_id = mf.municipio_id
            AND mf.exercicio = EXTRACT(YEAR FROM COALESCE(pa.data_atualizacao_plano_acao, NOW()))
        LEFT JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
        ORDER BY pa.valor_total DESC NULLS LAST
    """,
        (deputado_id,),
    )
    rows = cur.fetchall()
    docs: list[dict[str, Any]] = []

    # Resumo por município: TOTAL EXATO das emendas, para o LLM citar o valor
    # literalmente em vez de somar os itens (causa de alucinacao de soma
    # detectada pelo taxa_invencao_rs). Prependido para prioridade de retrieval.
    por_municipio: dict[tuple[str, str], list[float]] = {}
    for row in rows:
        municipio, emp_uf, _obj, valor = row[0], row[1], row[2], row[3]
        if valor is not None:
            por_municipio.setdefault((municipio, emp_uf), []).append(float(valor))
    for (municipio, emp_uf), valores in sorted(por_municipio.items()):
        total = sum(valores)
        docs.append(
            {
                "text": (
                    f"Resumo das emendas PIX de {nome} para {municipio}-{emp_uf}: "
                    f"{len(valores)} emenda(s), TOTAL exato R$ {total:,.2f}."
                    # (sem lista de valores individuais — reduz o risco de o
                    # LLM fabricar series descendentes de valores falsos)
                ),
                "type": "emenda",
                "deputado_id": deputado_id,
                "ref": f"Resumo emendas para {municipio}",
            }
        )

    # Resumo por OBJETO (área temática): TOTAL EXATO de cada área, para o
    # analista de temáticas ranquear áreas citando valores literais em vez de
    # estimar/somar (mesmo approach do resumo por município que consertou o
    # analista "anomalias").
    por_objeto: dict[str, list[tuple[str, float]]] = {}
    for row in rows:
        municipio, _emp_uf, obj, valor = row[0], row[1], row[2], row[3]
        if valor is not None:
            por_objeto.setdefault(obj, []).append((municipio, float(valor)))
    if por_objeto:
        partes: list[str] = []
        for obj, pares in sorted(por_objeto.items(), key=lambda kv: -sum(v for _, v in kv[1])):
            # Top municípios por valor (limita o tamanho do chunk: listar todos
            # pode estourar o contexto de 2048 tokens do embedding -> 500).
            # O detalhe completo fica nos resumos por município.
            por_muni: dict[str, float] = {}
            for m, v in pares:
                por_muni[m] = por_muni.get(m, 0.0) + v
            top_munis = ", ".join(
                m for m, _ in sorted(por_muni.items(), key=lambda kv: -kv[1])[:5]
            )
            total_obj = sum(v for _, v in pares)
            partes.append(
                f"{obj}: R$ {total_obj:,.2f} ({len(pares)} emenda(s), "
                f"top municípios: {top_munis})"
            )
        total_geral = sum(sum(v for _, v in pares) for pares in por_objeto.values())
        docs.append(
            {
                "text": (
                    f"Distribuição por área das emendas PIX de {nome}: "
                    + "; ".join(partes)
                    + f". TOTAL GERAL exato R$ {total_geral:,.2f}."
                ),
                "type": "emenda",
                "deputado_id": deputado_id,
                "ref": "Resumo por área (objeto)",
            }
        )

    for row in rows:
        municipio, emp_uf, obj, valor, situacao, receita, despesa, divida, pop, idhm = row
        txt = f"Emenda PIX de {nome} para {municipio}-{emp_uf}: R$ {valor:,.2f} — {obj}."
        if situacao:
            txt += f" Situacao: {situacao}."
        # Contexto demográfico inline (elimina fragmentação com demografia_municipio)
        if pop:
            txt += f" Municipio: {pop:,} hab"
            if idhm:
                txt += f", IDHM {idhm}"
            txt += "."
        # Dados financeiros do município (se disponíveis)
        if receita and despesa:
            txt += f" Receita orcamentaria R$ {receita:,.2f}, despesas totais R$ {despesa:,.2f}."
            if divida:
                txt += f" Divida passiva R$ {divida:,.2f}."
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
        dissenso: bool = (aprovacao is True and tipo_voto in ("Não", "Obstrução")) or (
            aprovacao is False and tipo_voto == "Sim"
        )

        prefixo: str = "[DISSENSO] " if dissenso else ""
        desc_trunc: str = descricao[:200] + ("..." if len(descricao) > 200 else "")
        tema_part: str = f" [{tema}]" if tema else ""
        txt = f"{prefixo}Voto{tema_part} em {desc_trunc} — resultado: {'Aprovado' if aprovacao else 'Reprovado'}, voto: {tipo_voto}"
        docs.append({"text": txt, "type": "voto", "deputado_id": deputado_id})

    return docs


def _extract_diario_oficial(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Atos do Diário Oficial (via alertas) com nível de relevância e LIMIT 20."""
    cur.execute(
        """
        SELECT da.orgao, da.tipo_ato, da.resumo_ia, da.valor_financeiro,
               da.entidades_citadas, pa.nivel_relevancia
        FROM parlamentar_alertas pa
        JOIN diario_oficial_atos da ON pa.ato_id = da.ato_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
        ORDER BY pa.nivel_relevancia DESC, da.data_publicacao DESC
        LIMIT 20
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for orgao, tipo_ato, resumo, valor, entidades, nivel in cur.fetchall():
        txt = f"[Relevancia {nivel or 0}/5] Ato Oficial ({tipo_ato}) em {orgao}. Resumo: {resumo}."
        if entidades and entidades != "[]":
            txt += f" Entidades: {entidades}."
        if valor:
            txt += f" Valor: R$ {valor:,.2f}."
        docs.append(
            {
                "text": txt,
                "type": "diario_oficial",
                "deputado_id": deputado_id,
                "ref": f"Ato: {tipo_ato}",
                "nivel_relevancia": nivel or 0,
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


def _extract_emendas_discricionarias(
    cur: Any, deputado_id: int, nome: str
) -> list[dict[str, Any]]:
    """Chunks: Emendas discricionarias com beneficiario CNPJ + tipo_emenda.

    Sem LIMIT artificial — todas as emendas do deputado são indexadas.
    Usa parlamentar_id (indexado, 0 NULLs) para JOIN direto.
    """
    cur.execute(
        """
        SELECT ed.ano, ed.valor_total, ed.objeto, ed.status_execucao,
               ed.beneficiario_nome, ed.beneficiario_cnpj, ed.numero_convenio,
               ed.tipo_emenda
        FROM emendas_discricionarias ed
        WHERE ed.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
          AND ed.valor_total IS NOT NULL
        ORDER BY ed.valor_total DESC
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for row in cur.fetchall():
        ano, valor, objeto, status, ben_nome, ben_cnpj, num_convenio, tipo_emenda = row
        if not valor:
            continue
        desc_part: str = f" — {objeto}" if objeto else ""
        status_part: str = f" Status: {status}." if status else ""
        ben_part: str = f" Ben: {ben_nome} (CNPJ: {ben_cnpj})." if ben_nome else ""
        conv_part: str = f" Convenio: {num_convenio}." if num_convenio else ""
        tipo_part: str = f" Tipo: {tipo_emenda}." if tipo_emenda else ""
        txt = (
            f"Emenda Discricionaria {ano or '?'} do deputado {nome}: "
            f"R$ {valor:,.2f}{desc_part}.{status_part}{ben_part}{conv_part}{tipo_part}"
        )
        docs.append({"text": txt, "type": "emenda_discricionaria", "deputado_id": deputado_id})
    return docs


def _extract_discursos(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Discursos no plenário e comissões do deputado."""
    cur.execute(
        """
        SELECT data_hora_inicio, fase_evento, tipo_discurso, keywords, sumario, transcricao
        FROM parlamentar_discursos
        WHERE deputado_id = %s
        ORDER BY data_hora_inicio DESC
        LIMIT 50
        """,
        (deputado_id,),
    )

    docs = []
    for row in cur.fetchall():
        data, fase, tipo, kw, sumario, trans = row
        data_str = data.strftime("%d/%m/%Y %H:%M") if data else "Data desconhecida"

        texto = f"[DISCURSO_PLENARIO] Deputado(a) {nome}\nFase: {fase or 'N/I'} | Tipo: {tipo or 'N/I'}\nData: {data_str}\n"
        if sumario:
            texto += f"Resumo: {sumario}\n"
        if kw:
            texto += f"Tags: {kw}\n"
        # embeddinggemma-300m: max 8192 tokens (~24000 chars PT-BR)
        # mantendo 5500 como safe-guard para consistencia com todos os chunk types
        if trans and len(trans) > 5500:
            trans = (
                trans[:5500]
                + "\n[...truncado para caber no contexto do embedding (2048 tokens)...]"
            )
        texto += f"Transcrição Literal:\n{trans or 'N/I'}"

        docs.append(
            {
                "type": "discurso_plenario",
                "deputado_id": deputado_id,
                "text": texto,
                "data": data_str,
            }
        )
    return docs


def _extract_compras_municipio(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Compras publicas nos municipios receptores de emendas do deputado."""
    cur.execute(
        """
        SELECT mib.nome, COUNT(DISTINCT cm.id) as n_compras,
               SUM(COALESCE(cm.valor_homologado, cm.valor_estimado, 0)) as valor_total,
               STRING_AGG(DISTINCT cm.nome_orgao, ', ' ORDER BY cm.nome_orgao)
                   FILTER (WHERE cm.nome_orgao IS NOT NULL) as orgaos
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN compras_municipios cm ON bm.municipio_id = cm.municipio_id
        JOIN municipios_ibge mib ON cm.municipio_id = mib.municipio_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
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
    """Chunks: Indicadores de saude, educacao + populacao/IDHM (fundido com antigo indicadores_municipal)."""
    cur.execute(
        """
        SELECT mib.nome, mib.populacao, mib.idhm,
               sm.total_estabelecimentos, sm.total_leitos, sm.leitos_sus,
               sm.hospitais, sm.ubs, sm.total_profissionais,
               em.ideb_initial_years, em.ideb_final_years,
               em.taxa_aprovacao, em.matriculas_totais, em.escolas_totais
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        LEFT JOIN saude_municipios sm ON bm.municipio_id = sm.municipio_id
        LEFT JOIN educacao_municipios em ON bm.municipio_id = em.municipio_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
          AND (sm.municipio_id IS NOT NULL OR em.municipio_id IS NOT NULL
               OR mib.populacao IS NOT NULL)
        GROUP BY mib.nome, mib.populacao, mib.idhm,
                 sm.total_estabelecimentos, sm.total_leitos, sm.leitos_sus,
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
            pop,
            idhm,
            estab,
            leitos,
            leitos_sus,
            hosp,
            ubs,
            prof,
            ideb_i,
            ideb_f,
            aprov,
            matric,
            escolas,
        ) = row  # noqa: E501
        partes: list[str] = []
        # Demografia (fundido do antigo indicadores_municipal)
        demograf: list[str] = []
        if pop:
            demograf.append(f"{pop:,} hab")
        if idhm:
            demograf.append(f"IDHM {idhm}")
        if demograf:
            partes.append(f"Demografia: {', '.join(demograf)}")
        # Saude
        if estab or leitos:
            saude_parts: list[str] = []
            if estab:
                saude_parts.append(f"{estab} estabelecimentos ({hosp or 0} hosp, {ubs or 0} UBS)")
            if leitos:
                saude_parts.append(f"{leitos} leitos ({leitos_sus or 0} SUS)")
            if prof:
                saude_parts.append(f"{prof} profissionais")
            partes.append(f"Saude: {', '.join(saude_parts)}")
        # Educacao
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
    cur.execute(
        """
        SELECT mib.nome, bp.total_processos, bp.processos_detalhes
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        JOIN beneficiario_processos bp ON b.cnpj = bp.cnpj
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
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
    cur.execute(
        """
        SELECT DISTINCT mib.nome, mib.populacao, mib.pib_per_capita,
               mib.area_km2, mib.idhm, mib.densidade_demografica
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
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


# Mapa de prefixo IBGE (2 dígitos) → UF sigla para corrigir payload de municipio_financeiro
IBGE_UF_MAP: dict[str, str] = {
    "11": "RO",
    "12": "AC",
    "13": "AM",
    "14": "RR",
    "15": "PA",
    "16": "AP",
    "17": "TO",
    "21": "MA",
    "22": "PI",
    "23": "CE",
    "24": "RN",
    "25": "PB",
    "26": "PE",
    "27": "AL",
    "28": "SE",
    "29": "BA",
    "31": "MG",
    "32": "ES",
    "33": "RJ",
    "35": "SP",
    "41": "PR",
    "42": "SC",
    "43": "RS",
    "50": "MS",
    "51": "MT",
    "52": "GO",
    "53": "DF",
}


def _extract_municipio_financeiro(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Dados financeiros dos municipios receptores de emendas (SICONFI)."""
    cur.execute(
        """
        SELECT DISTINCT mib.nome, mib.municipio_id, mf.exercicio,
               mf.receitas_orcamentarias, mf.despesas_totais,
               mf.divida_passiva, mf.arrec_impostos_geral,
               mf.arrec_cota_fpm, mf.arrec_cota_icms, mf.arrec_iss
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        JOIN municipios_financeiro mf ON bm.municipio_id = mf.municipio_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
          -- FIX 2026-07-31: receitas_orcamentarias é 100 por cento NULL no SICONFI-RREO;
          -- o filtro antigo (IS NOT NULL) tornava o SICONFI INVISÍVEL ao RAG.
          -- Os dados úteis estão nas colunas arrec_* (arrecadação).
          AND (mf.arrec_impostos_geral IS NOT NULL
               OR mf.arrec_cota_fpm IS NOT NULL
               OR mf.arrec_cota_icms IS NOT NULL
               OR mf.arrec_iss IS NOT NULL)
        ORDER BY mf.exercicio DESC,
                 mf.arrec_impostos_geral DESC NULLS LAST
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
        # SICONFI-RREO costuma preencher só arrecadação (receitas/despesas NULL)
        if not partes and fontes:
            partes = ["arrecadação: " + "; ".join(fontes)]
            fontes = []
        if not partes:
            continue
        txt = (
            f"Dados financeiros de {mun} (IBGE {mun_id}, exercício {exerc or '?'}), "
            f"município receptor de emendas do deputado {nome}: "
            f"{', '.join(partes)}."
        )
        if fontes:
            txt += f" Fontes de receita: {', '.join(fontes)}."
        # Corrigir uf: código IBGE numérico → sigla (ex: "35" → "SP")
        uf_real = IBGE_UF_MAP.get(str(mun_id)[:2]) if mun_id else None
        docs.append(
            {
                "text": txt,
                "type": "municipio_financeiro",
                "deputado_id": deputado_id,
                "municipio_ibge_id": mun_id,
                "uf": uf_real,
            }
        )
    return docs


def _extract_estado_financeiro(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Dados financeiros do GOVERNO ESTADUAL (SICONFI esfera estadual).

    Usa a UF do deputado para puxar os dados do estado em que ele atua:
    receitas, despesas, resultado orcamentario, divida e arrecadacao propria
    (ICMS, IPVA, ITCD, IRRF) + transferencias (FPE, FUNDEB, RCL).
    Fonte: estados_financeiro (enricher estados_financeiro.py).
    """
    # UF do deputado
    cur.execute(
        "SELECT uf FROM parlamentares_dados WHERE deputado_id = %s",
        (deputado_id,),
    )
    row_uf = cur.fetchone()
    if not row_uf or not row_uf[0]:
        return []
    uf = row_uf[0]

    cur.execute(
        """
        SELECT ef.uf, ef.exercicio,
               ef.receitas_correntes, ef.receitas_capital, ef.receitas_orcamentarias,
               ef.despesas_correntes, ef.despesas_capital, ef.despesas_totais,
               ef.resultado_orcamentario, ef.resultado_primario,
               ef.divida_ativa, ef.divida_passiva, ef.patrimonio_liquido,
               ef.arrec_icms, ef.arrec_ipva, ef.arrec_itcd, ef.arrec_irrf,
               ef.arrec_cota_fpe, ef.arrec_fundeb, ef.arrec_impostos_geral,
               ef.arrec_transferencias, ef.arrec_receitas_correntes, ef.arrec_rcl
        FROM estados_financeiro ef
        WHERE ef.uf = %s
        ORDER BY ef.exercicio DESC
        LIMIT 1
        """,
        (uf,),
    )
    row = cur.fetchone()
    if not row:
        return []

    (
        _uf,
        exerc,
        rec_corr,
        rec_cap,
        rec_orc,
        desp_corr,
        desp_cap,
        desp_tot,
        res_orc,
        res_prim,
        div_ativa,
        div_pass,
        patr_liq,
        icms,
        ipva,
        itcd,
        irrf,
        fpe,
        fundeb,
        imp_geral,
        transf,
        rec_corr_rreo,
        rcl,
    ) = row

    partes: list[str] = []
    if rec_corr:
        partes.append(f"receitas correntes R$ {rec_corr:,.2f}")
    if rec_cap:
        partes.append(f"receitas de capital R$ {rec_cap:,.2f}")
    if desp_tot:
        partes.append(f"despesas totais R$ {desp_tot:,.2f}")
    if res_orc is not None:
        partes.append(
            f"resultado orçamentário {'superávit' if res_orc > 0 else 'déficit'} R$ {abs(res_orc):,.2f}"
        )
    if div_pass:
        partes.append(f"dívida passiva R$ {div_pass:,.2f}")
    if patr_liq is not None:
        partes.append(f"patrimônio líquido R$ {patr_liq:,.2f}")
    if not partes:
        return []

    txt = (
        f"Dados financeiros do governo do estado de {uf} (exercício {exerc or '?'}), "
        f"onde o deputado {nome} atua: {', '.join(partes)}."
    )

    # Arrecadação própria + transferências (RREO Anexo 03 estadual)
    fontes: list[str] = []
    if icms:
        fontes.append(f"ICMS R$ {icms:,.2f}")
    if ipva:
        fontes.append(f"IPVA R$ {ipva:,.2f}")
    if itcd:
        fontes.append(f"ITCD R$ {itcd:,.2f}")
    if irrf:
        fontes.append(f"IRRF R$ {irrf:,.2f}")
    if fpe:
        fontes.append(f"FPE R$ {fpe:,.2f}")
    if fundeb:
        fontes.append(f"FUNDEB R$ {fundeb:,.2f}")
    if rcl:
        fontes.append(f"receita corrente líquida R$ {rcl:,.2f}")
    if fontes:
        txt += f" Arrecadação e transferências: {', '.join(fontes)}."

    docs = [
        {
            "text": txt,
            "type": "estado_financeiro",
            "deputado_id": deputado_id,
            "uf": uf,
        }
    ]
    return docs


def _extract_parlamentar_resumo(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Resumo consolidado do deputado (emendas, beneficiários, valores)."""
    cur.execute(
        """
        SELECT COUNT(DISTINCT pa.plano_acao_id) as n_planos,
               COUNT(DISTINCT b.beneficiario_id) as n_benef,
               COUNT(DISTINCT bm.municipio_id) as n_municipios,
               COALESCE(SUM(pa.valor_total), 0) as valor_total,
               pd.sigla_partido, pd.uf
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd ON pa.parlamentar_id = pd.parlamentar_id
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
    return [
        {
            "text": txt,
            "type": "parlamentar_resumo",
            "deputado_id": deputado_id,
        }
    ]


def _extract_beneficiarios(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Perfil dos beneficiários diretos do deputado."""
    cur.execute(
        """
        SELECT DISTINCT b.nome, b.cnpj, b.uf,
               vc.razao_social, vc.situacao_cadastral, pa.valor_total
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        LEFT JOIN validacao_cnpj vc ON b.cnpj = vc.cnpj
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
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
        docs.append(
            {
                "text": txt,
                "type": "beneficiario",
                "deputado_id": deputado_id,
            }
        )
    return docs


def _extract_prefeitos(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Perfil dos prefeitos nos municípios receptores de emendas."""
    cur.execute(
        """
        SELECT DISTINCT pf.prefeito_nome, pf.municipio_nome, pf.sigla_partido,
               pf.ano_eleicao, pf.coligacao
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN prefeitos_dados pf ON bm.municipio_id = pf.municipio_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
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
        docs.append(
            {
                "text": txt,
                "type": "prefeito",
                "deputado_id": deputado_id,
            }
        )
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
    # FIX 2026-07-31: situacao real é 'EM EXERCÍCIO' (não 'Exercício') —
    # o match exato anterior nunca retornava senadores.
    cur.execute(
        "SELECT nome_parlamentar, sigla_partido, email, legislatura "
        "FROM senadores_dados WHERE uf = %s AND situacao ILIKE '%%EXERC%%'",
        (uf,),
    )
    docs: list[dict[str, Any]] = []
    for s_nome, partido, _email, _leg in cur.fetchall():
        txt = (
            f"Senador(a) {s_nome} ({partido}) em exercício em {uf}. "
            f"Conexão federal relevante para deputado {nome} ({uf})."
        )
        docs.append(
            {
                "text": txt,
                "type": "senador",
                "deputado_id": deputado_id,
            }
        )
    return docs


def _extract_fnde_repasses(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Repasses FNDE nos municípios receptores de emendas."""
    cur.execute(
        """
        SELECT DISTINCT mib.nome, fr.programa, fr.valor_total,
               fr.ano, fr.descricao_programa
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        JOIN fnde_repasses fr ON bm.municipio_id = fr.municipio_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
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
        docs.append(
            {
                "text": txt,
                "type": "fnde_repasses",
                "deputado_id": deputado_id,
            }
        )
    return docs


def _extract_indicadores_municipal(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Painel consolidado de indicadores municipais (saúde + educação + IBGE)."""
    cur.execute(
        """
        SELECT DISTINCT mib.nome, mib.populacao, mib.idhm,
               sm.total_leitos, sm.total_profissionais,
               em.ideb_initial_years, em.ideb_final_years,
               em.taxa_aprovacao, em.matriculas_totais
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        JOIN municipios_ibge mib ON bm.municipio_id = mib.municipio_id
        LEFT JOIN saude_municipios sm ON bm.municipio_id = sm.municipio_id
        LEFT JOIN educacao_municipios em ON bm.municipio_id = em.municipio_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
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
        docs.append(
            {
                "text": txt,
                "type": "indicadores_municipal",
                "deputado_id": deputado_id,
            }
        )
    return docs


def _extract_vereadores_resumo(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunk: Resumo de vereadores nos municípios receptores de emendas."""
    cur.execute(
        """
        SELECT mib.nome, mib.municipio_id,
               COUNT(*) as n_veread,
               MODE() WITHIN GROUP (ORDER BY vd.sigla_partido) as partido_mais,
               SUM(CASE WHEN vd.sigla_partido = pd.sigla_partido THEN 1 ELSE 0 END) as aliados
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN parlamentares_dados pd ON pa.parlamentar_id = pd.parlamentar_id
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
        docs.append(
            {
                "text": txt,
                "type": "vereadores_resumo",
                "deputado_id": deputado_id,
            }
        )
    return docs


# ---------------------------------------------------------------------------
# Fase 7: Novo chunk type — parlamentar_alertas (alertas DOU vinculados ao deputado)
# ---------------------------------------------------------------------------


def _extract_parlamentar_alertas(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Alertas de relevancia do DOU com vinculacao direta ao deputado."""
    cur.execute(
        """
        SELECT pa.nivel_relevancia, COUNT(*) as n_alertas,
               MAX(da.data_publicacao)::date as ultimo_ato
        FROM parlamentar_alertas pa
        JOIN diario_oficial_atos da ON pa.ato_id = da.ato_id
        WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
        GROUP BY pa.nivel_relevancia
        ORDER BY pa.nivel_relevancia DESC
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for nivel, n_alertas, ultimo in cur.fetchall():
        if not n_alertas or n_alertas == 0:
            continue
        nivel_str = f"Relevancia {nivel or 0}/5"
        txt = (
            f"Alertas DOU para o deputado {nome}: {n_alertas} atos "
            f"(nivel {nivel_str}), ultimo em {ultimo or 'N/I'}."
        )
        docs.append(
            {
                "text": txt,
                "type": "parlamentar_alertas",
                "deputado_id": deputado_id,
                "nivel_relevancia": nivel or 0,
            }
        )
    return docs


# ---------------------------------------------------------------------------
# Fase 8: Novo chunk type — persona_existente (dossies RAG ja gerados)
# ---------------------------------------------------------------------------


def _extract_personas_existentes(cur: Any, deputado_id: int, nome: str) -> list[dict[str, Any]]:
    """Chunks: Re-aproveitamento de dossies/personas analiticas ja geradas."""
    cur.execute(
        """
        SELECT analise_gerada, versao_prompt, score_qualidade,
               data_analise::date, modelo_usado
        FROM parlamentares_personas
        WHERE deputado_id = %s
          AND qualidade_ok = true
          AND analise_gerada IS NOT NULL
        ORDER BY data_analise DESC
        LIMIT 3
    """,
        (deputado_id,),
    )
    docs: list[dict[str, Any]] = []
    for analise, versao, score, data, modelo in cur.fetchall():
        if not analise:
            continue
        preview: str = analise[:2000] + ("..." if len(analise) > 2000 else "")
        txt = (
            f"[Persona RAG v{versao or '?'}] Dossier do deputado {nome} "
            f"(score: {score or 0:.1f}/100, modelo: {modelo or 'N/I'}, data: {data or 'N/I'}).\n"
            f"**Analise**: {preview}"
        )
        docs.append(
            {
                "text": txt,
                "type": "persona_existente",
                "deputado_id": deputado_id,
            }
        )
    return docs


# Mapa de extratores por tipo de chunk — usado pelo modo --types e --diff
CHUNK_EXTRACTORS: dict[str, str] = {
    "perfil": "_extract_perfil",
    "proposicao": "_extract_proposicoes",
    "emenda": "_extract_emendas",
    "voto": "_extract_votos",
    "diario_oficial": "_extract_diario_oficial",
    "conexao_politica": "_extract_prefeitos_aliados",
    "emenda_discricionaria": "_extract_emendas_discricionarias",
    "compras_municipio": "_extract_compras_municipio",
    "indicadores_sociais": "_extract_indicadores_sociais",
    "risco_judicial": "_extract_risco_judicial",
    "demografia_municipio": "_extract_demografia_municipio",
    "municipio_financeiro": "_extract_municipio_financeiro",
    "estado_financeiro": "_extract_estado_financeiro",
    "parlamentar_resumo": "_extract_parlamentar_resumo",
    "beneficiario": "_extract_beneficiarios",
    "prefeito": "_extract_prefeitos",
    "senador": "_extract_senadores",
    "fnde_repasses": "_extract_fnde_repasses",
    "indicadores_municipal": "_extract_indicadores_municipal",
    "vereadores_resumo": "_extract_vereadores_resumo",
    "discurso_plenario": "_extract_discursos",
    "parlamentar_alertas": "_extract_parlamentar_alertas",
    "persona_existente": "_extract_personas_existentes",
}

# ---------------------------------------------------------------------------
# Checkpoint: tabela de controle no PostgreSQL
# ---------------------------------------------------------------------------

_CHECKPOINT_SQL = """
CREATE TABLE IF NOT EXISTS qdrant_index_checkpoint (
    chunk_type TEXT NOT NULL,
    deputado_id INTEGER NOT NULL,
    data_hash TEXT NOT NULL,
    indexed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (chunk_type, deputado_id)
);
"""


def _ensure_checkpoint_table() -> None:
    """Cria tabela de checkpoint se não existir."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(_CHECKPOINT_SQL)
            conn.commit()
    finally:
        conn.close()


def _get_checkpoint_hash(chunk_type: str, deputado_id: int) -> str | None:
    """Retorna hash do último checkpoint para (chunk_type, deputado_id)."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT data_hash FROM qdrant_index_checkpoint WHERE chunk_type = %s AND deputado_id = %s",
                (chunk_type, deputado_id),
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def _save_checkpoint(chunk_type: str, deputado_id: int, data_hash: str) -> None:
    """Salva/atualiza checkpoint."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO qdrant_index_checkpoint (chunk_type, deputado_id, data_hash) "
                "VALUES (%s, %s, %s) "
                "ON CONFLICT (chunk_type, deputado_id) DO UPDATE SET data_hash = EXCLUDED.data_hash, indexed_at = NOW()",
                (chunk_type, deputado_id, data_hash),
            )
            conn.commit()
    finally:
        conn.close()


def _compute_data_hash(cur: Any, deputado_id: int, extractor_name: str) -> str:
    """Calcula hash MD5 dos dados atuais para detectar mudancas (modo --diff)."""
    # Para cada extrator, faz uma consulta resumida para gerar hash
    hasher = hashlib.md5()
    hasher.update(f"{deputado_id}_{extractor_name}".encode())

    if extractor_name == "_extract_perfil":
        cur.execute(
            "SELECT nome, sigla_partido, uf FROM parlamentares_dados WHERE deputado_id = %s",
            (deputado_id,),
        )
        row = cur.fetchone()
        if row:
            hasher.update(str(row).encode())
    elif extractor_name == "_extract_proposicoes":
        cur.execute(
            "SELECT COUNT(*), COALESCE(MAX(data_apresentacao)::text, '') FROM parlamentar_proposicoes WHERE deputado_id = %s",
            (deputado_id,),
        )
        hasher.update(str(cur.fetchone()).encode())
    elif extractor_name == "_extract_emendas":
        # Hash por CONTEÚDO dos chunks (nao so count/sum): mudancas de formato
        # (ex: resumo com total exato) sao detectadas pelo --diff. Fallback
        # para count/sum se o extrator falhar.
        try:
            cur.execute(
                "SELECT nome FROM parlamentares_dados WHERE deputado_id = %s",
                (deputado_id,),
            )
            _row_nome = cur.fetchone()
            _nome = _row_nome[0] if _row_nome else ""
            for _d in _extract_emendas(cur, deputado_id, _nome):
                hasher.update(_d["text"].encode())
        except Exception:
            cur.execute(
                "SELECT COUNT(*), COALESCE(SUM(pa.valor_total)::text, '0') FROM planos_acao pa "
                "WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)",
                (deputado_id,),
            )
            hasher.update(str(cur.fetchone()).encode())
    elif extractor_name == "_extract_votos":
        cur.execute(
            "SELECT COUNT(*), MAX(id) FROM votos_camara WHERE deputado_id = %s",
            (deputado_id,),
        )
        hasher.update(str(cur.fetchone()).encode())
    elif extractor_name == "_extract_diario_oficial":
        cur.execute(
            "SELECT COUNT(*) FROM parlamentar_alertas pa "
            "WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)",
            (deputado_id,),
        )
        hasher.update(str(cur.fetchone()).encode())
    elif extractor_name == "_extract_discursos":
        cur.execute(
            "SELECT COUNT(*), MAX(data_hora_inicio::text) FROM parlamentar_discursos WHERE deputado_id = %s",
            (deputado_id,),
        )
        hasher.update(str(cur.fetchone()).encode())
    elif extractor_name in (
        "_extract_municipio_financeiro",
        "_extract_estado_financeiro",
        "_extract_demografia_municipio",
        "_extract_indicadores_sociais",
        "_extract_compras_municipio",
        "_extract_risco_judicial",
        "_extract_indicadores_municipal",
        "_extract_vereadores_resumo",
        "_extract_prefeitos_aliados",
        "_extract_prefeitos",
        "_extract_fnde_repasses",
    ):
        # Para extratores com JOIN complexos, hash generico
        hasher.update(f"generic_{deputado_id}".encode())
    elif extractor_name == "_extract_emendas_discricionarias":
        cur.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(ed.valor_total)::text, '0')
            FROM emendas_discricionarias ed
            WHERE ed.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)
            """,
            (deputado_id,),
        )
        hasher.update(str(cur.fetchone()).encode())
    elif extractor_name == "_extract_beneficiarios":
        cur.execute(
            "SELECT COUNT(DISTINCT b.beneficiario_id) FROM planos_acao pa "
            "JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id "
            "WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)",
            (deputado_id,),
        )
        hasher.update(str(cur.fetchone()).encode())
    elif extractor_name == "_extract_senadores":
        cur.execute("SELECT uf FROM parlamentares_dados WHERE deputado_id = %s", (deputado_id,))
        row = cur.fetchone()
        if row:
            cur.execute("SELECT COUNT(*) FROM senadores_dados WHERE uf = %s", (row[0],))
            hasher.update(str(cur.fetchone()).encode())
    elif extractor_name == "_extract_parlamentar_resumo":
        hasher.update(f"resumo_{deputado_id}".encode())
    elif extractor_name == "_extract_parlamentar_alertas":
        cur.execute(
            "SELECT COUNT(*) FROM parlamentar_alertas pa "
            "WHERE pa.parlamentar_id IN (SELECT parlamentar_id FROM parlamentares_dados WHERE deputado_id = %s)",
            (deputado_id,),
        )
        hasher.update(str(cur.fetchone()).encode())
    elif extractor_name == "_extract_personas_existentes":
        cur.execute(
            "SELECT COUNT(*), COALESCE(MAX(data_analise)::text, '') "
            "FROM parlamentares_personas WHERE deputado_id = %s AND qualidade_ok = true",
            (deputado_id,),
        )
        hasher.update(str(cur.fetchone()).encode())
    return hasher.hexdigest()


# ---------------------------------------------------------------------------
# Orchestrador: extrai todos os chunks de um deputado (com resiliência)
# ---------------------------------------------------------------------------


def get_deputado_texts(
    deputado_id: int,
    *,
    chunk_types: list[str] | None = None,
    diff: bool = False,
) -> tuple[list[dict[str, Any]], list[tuple[str, str]]]:
    """Extrai chunks de fontes selecionadas para um deputado.

    Args:
        chunk_types: Lista de tipos para filtrar (None = todos).
        diff: Se True, pula chunks que nao mudaram desde o ultimo checkpoint.

    Returns:
        Tupla (docs, checkpoints):
          - docs: lista de chunks extraidos com metadados.
          - checkpoints: lista de (chunk_type, current_hash) dos tipos cujos
            dados mudaram e PRECISAM ter o checkpoint salvo. O chamador deve
            salvar SOMENTE apos o upsert ter sucesso — salvar antes (na
            extracao) deixa o checkpoint 'envenenado' (marcado como atualizado
            sem vetores) quando o embedding/upsert falha.
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT nome FROM parlamentares_dados WHERE deputado_id = %s",
            (deputado_id,),
        )
        row = cur.fetchone()
        if not row:
            return [], []
        nome = row[0]

        # Mapear tipos para funcoes extratoras
        extractors: list[tuple[str, Any]] = []
        for tipo, func_name in CHUNK_EXTRACTORS.items():
            if chunk_types and tipo not in chunk_types:
                continue
            func = globals().get(func_name)
            if func:
                extractors.append((tipo, func))

        docs: list[dict[str, Any]] = []
        checkpoints: list[tuple[str, str]] = []
        for chunk_type, extractor in extractors:
            try:
                current_hash: str | None = None
                # Modo diff: verificar se dados mudaram
                if diff:
                    current_hash = _compute_data_hash(cur, deputado_id, extractor.__name__)
                    stored_hash = _get_checkpoint_hash(chunk_type, deputado_id)
                    if current_hash is not None and stored_hash == current_hash:
                        log.debug(
                            f"  [diff] {chunk_type} para deputado {deputado_id}: inalterado, pulando"
                        )
                        continue

                chunk_docs = extractor(cur, deputado_id, nome)
                if chunk_docs:
                    docs.extend(chunk_docs)
                    log.debug(f"  {extractor.__name__}: {len(chunk_docs)} chunks")
                    # NAO salvar checkpoint aqui: o chamador (main) salva apos
                    # o upsert ter sucesso, evitando checkpoint sem vetores.
                    if diff and current_hash:
                        checkpoints.append((chunk_type, current_hash))
                else:
                    log.debug(f"  {extractor.__name__}: 0 chunks")

            except Exception as e:
                log.error(
                    f"  Erro no extrator {extractor.__name__} para deputado {deputado_id}: {e}"
                )
                # Nao aborta — continua com os proximos extratores

        return docs, checkpoints


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Popula o Qdrant com dados dos Deputados para RAG (v4+ com 18 chunk types)"
    )
    parser.add_argument("--limit", type=int, default=10, help="Número de deputados a processar")
    parser.add_argument("--nome", type=str, help="Nome do deputado (busca exata por ILIKE)")
    parser.add_argument("--rebuild", action="store_true", help="Recriar coleção do zero")
    parser.add_argument(
        "--diff", action="store_true", help="Modo incremental: pula chunks com hash inalterado"
    )
    parser.add_argument(
        "--types",
        type=str,
        help="Filtrar tipos de chunk (separados por virgula). "
        f"Disponiveis: {', '.join(CHUNK_EXTRACTORS.keys())}",
    )
    parser.add_argument(
        "--checkpoint",
        action="store_true",
        help="Forcar verificacao/criacao da tabela de checkpoint",
    )
    args = parser.parse_args()

    # Garantir tabela de checkpoint se --diff ou --checkpoint
    if args.diff or args.checkpoint:
        _ensure_checkpoint_table()

    # Filtrar tipos de chunk
    tipos_filtro: list[str] | None = None
    if args.types:
        tipos_filtro = [t.strip() for t in args.types.split(",") if t.strip() in CHUNK_EXTRACTORS]
        if not tipos_filtro:
            log.error(
                f"Nenhum tipo valido em --types. Disponiveis: {', '.join(CHUNK_EXTRACTORS.keys())}"
            )
            return
        log.info(f"Filtrando tipos: {tipos_filtro}")

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
            # Priorizar deputados com mais dados (alertas DO + votos + emendas)
            cur.execute(
                """
                SELECT pd.deputado_id, pd.nome,
                    (SELECT COUNT(*) FROM parlamentar_alertas pa
                     WHERE pa.parlamentar_id = pd.parlamentar_id) as n_alertas,
                    (SELECT COUNT(*) FROM votos_camara vc
                     WHERE vc.deputado_id = pd.deputado_id) as n_votos,
                    (SELECT COUNT(*) FROM planos_acao pa2
                     WHERE pa2.parlamentar_id = pd.parlamentar_id) as n_emendas
                FROM parlamentares_dados pd
                ORDER BY n_alertas DESC, n_votos DESC, n_emendas DESC, pd.deputado_id ASC
                LIMIT %s
            """,
                (args.limit,),
            )
        deputados = cur.fetchall()

    if not deputados:
        log.info("Nenhum deputado encontrado para indexar.")
        return

    log.info(
        f"Indexando {len(deputados)} deputados no Qdrant (diff={args.diff}, tipos={tipos_filtro or 'todos'})..."
    )
    total_points = 0

    for idx, dep_row in enumerate(deputados, 1):
        deputado_id = dep_row[0]
        nome = dep_row[1]

        # Extrair chunks (com resiliencia + diff)
        docs, checkpoints = get_deputado_texts(
            deputado_id, chunk_types=tipos_filtro, diff=args.diff
        )
        if not docs:
            log.debug(f"  [{idx}/{len(deputados)}] {nome}: sem dados novos, pulando.")
            continue

        # Batch embedding (1 request para todos os chunks)
        texts = [d["text"] for d in docs]
        vectors = embed_text_batch(texts)

        # Sparse vectors (BM25) — geração local rápida, sem modelo
        sparse_vectors = texts_to_sparse_vectors(texts)

        # Montar points com named vectors (dense + sparse)
        points: list[qdrant_models.PointStruct] = []
        for doc, vector, sparse_vec in zip(docs, vectors, sparse_vectors):
            if not vector or len(vector) != EMBEDDING_DIM:
                continue
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{deputado_id}_{doc['text']}"))
            points.append(
                qdrant_models.PointStruct(
                    id=point_id,
                    vector={
                        "dense": vector,
                        "bm25": sparse_vec,
                    },
                    payload=doc,
                )
            )

        # Upsert em lotes reduzidos para evitar timeout no Qdrant durante rebuild
        if points:
            batch_size = 20
            for i in range(0, len(points), batch_size):
                batch = points[i : i + batch_size]
                client.upsert(collection_name=QDRANT_COLLECTION, points=batch)
            total_points += len(points)
            # Checkpoint SOMENTE apos upsert bem-sucedido. Salvar antes (na
            # extracao) deixava o checkpoint 'envenenado' (hash 'atual' sem
            # vetores) quando o embedding/upsert falhava -> o --diff pulava o
            # deputado para sempre.
            if checkpoints:
                try:
                    with get_connection() as conn, conn.cursor() as cur:
                        for chunk_type, current_hash in checkpoints:
                            _save_checkpoint(chunk_type, deputado_id, current_hash)
                except Exception as e:
                    log.error(
                        f"  Erro ao salvar checkpoint de {nome} " f"(chunk {chunk_type}): {e}"
                    )

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
