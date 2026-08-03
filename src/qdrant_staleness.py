#!/usr/bin/env python3
"""qdrant-staleness: Summary de Staleness do Qdrant.

Compara os checkpoints armazenados (qdrant_index_checkpoint) com os dados
atuais no PostgreSQL para identificar:

  - deputados NUNCA indexados
  - chunk types DESATUALIZADOS (hash mudou)
  - chunk types AUSENTES (existem dados, mas nunca foram para o Qdrant)

Uso:
    python3 src/qdrant_staleness.py
    ./run.sh qdrant-staleness

Flags:
    --json              Saída em JSON (para consumo programático)
    --stale             Apenas deputados com dados desatualizados
    --missing           Apenas deputados nunca indexados
    --top N             Mostrar apenas os N mais problemáticos
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from typing import Any

from src.db_utils import get_connection

log = logging.getLogger(__name__)


# Chunk types do indexador — copiado do rag_qdrant_indexer para não
# forçar import de dependências pesadas (qdrant_client, localai, etc.)
CHUNK_TYPES: list[tuple[str, str, list[str]]] = [
    ("perfil", "Perfil do deputado", []),
    ("proposicao", "Proposições legislativas", []),
    ("emenda", "Emendas PIX", []),
    ("voto", "Votações nominais", []),
    ("diario_oficial", "Diário Oficial", []),
    ("conexao_politica", "Conexão política (dep.×prefeito)", []),
    ("emenda_discricionaria", "Emendas discricionárias", []),
    ("compras_municipio", "Compras municipais", []),
    ("indicadores_sociais", "Indicadores sociais (saúde+educação)", []),
    ("risco_judicial", "Risco judicial (DataJud)", []),
    ("demografia_municipio", "Demografia (pop/PIB/IDHM)", []),
    ("municipio_financeiro", "Finanças municipais (SICONFI)", []),
    ("parlamentar_resumo", "Resumo consolidado", []),
    ("beneficiario", "Perfil CNPJ beneficiário", []),
    ("prefeito", "Prefeitos eleitos", []),
    ("senador", "Senadores do estado", []),
    ("fnde_repasses", "Repasses FNDE", []),
    ("indicadores_municipal", "Indicadores municipais", []),
    ("vereadores_resumo", "Rede de vereadores", []),
    ("discurso_plenario", "Discursos em plenário", []),
]

# Mapa que registra quais tabelas fonte alimentam cada chunk type
# (usado para diagnóstico de "dados existem mas não foram indexados")
CHUNK_SOURCE_TABLES: dict[str, str] = {
    "perfil": "parlamentares_dados",
    "proposicao": "parlamentar_proposicoes",
    "emenda": "planos_acao",
    "voto": "votos_camara",
    "diario_oficial": "parlamentar_alertas",
    "conexao_politica": "prefeitos_dados",
    "emenda_discricionaria": "emendas_discricionarias",
    "compras_municipio": "compras_municipios",
    "indicadores_sociais": "saude_municipios",
    "risco_judicial": "beneficiario_processos",
    "demografia_municipio": "municipios_ibge",
    "municipio_financeiro": "municipios_financeiro",
    "parlamentar_resumo": "planos_acao",
    "beneficiario": "beneficiarios",
    "prefeito": "prefeitos_dados",
    "senador": "senadores_dados",
    "fnde_repasses": "fnde_repasses",
    "indicadores_municipal": "saude_municipios",
    "vereadores_resumo": "vereadores_dados",
    "discurso_plenario": "parlamentar_discursos",
}


def carregar_deputados(cur: Any) -> list[dict[str, Any]]:
    """Carrega todos os deputados com dados no banco."""
    cur.execute(
        """
        SELECT d.deputado_id, d.nome, d.sigla_partido, d.uf,
               COALESCE(d.ultimo_check_diario::text, 'N/A') as ultima_atualizacao
        FROM parlamentares_dados d
        ORDER BY d.nome
        """
    )
    cols = [desc[0] for desc in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def carregar_checkpoints(cur: Any) -> dict[tuple[str, int], dict[str, Any]]:
    """Carrega todos os checkpoints existentes.

    Returns:
        Dict {(chunk_type, deputado_id) -> {data_hash, indexed_at}}
    """
    cur.execute(
        """
        SELECT chunk_type, deputado_id, data_hash, indexed_at::text
        FROM qdrant_index_checkpoint
        """
    )
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for row in cur.fetchall():
        key = (row[0], row[1])
        result[key] = {"data_hash": row[2], "indexed_at": row[3]}
    return result


def contar_registros_tabela(cur: Any, tabela: str, deputado_id: int) -> int:
    """Conta quantos registros existem para um deputado em uma tabela fonte."""
    # Tabelas que têm coluna deputado_id direta
    tabelas_deputado_id = [
        "parlamentares_dados",
        "parlamentar_proposicoes",
        "votos_camara",
        "beneficiario_processos",
        "parlamentar_discursos",
        "votacoes_camara",
    ]
    # Tabelas vinculadas via parlamentar_nome
    tabelas_nome = [
        "planos_acao",
        "parlamentar_alertas",
        "emendas_discricionarias",
    ]
    # Tabelas vinculadas via municipio/UF
    tabelas_municipio = [
        "municipios_ibge",
        "municipios_financeiro",
        "compras_municipios",
        "saude_municipios",
        "prefeitos_dados",
        "vereadores_dados",
        "senadores_dados",
        "fnde_repasses",
    ]
    # Tabelas vinculadas via beneficiario_id
    tabelas_beneficiario = [
        "beneficiarios",
    ]

    try:
        if tabela in tabelas_deputado_id:
            cur.execute(
                f"SELECT COUNT(*) FROM {tabela} WHERE deputado_id = %s",
                (deputado_id,),
            )
            return cur.fetchone()[0]
        elif tabela in tabelas_nome:
            if tabela == "planos_acao":
                # Usa parlamentar_id para planos_acao (mais preciso que normalização de nome)
                cur.execute(
                    """
                    SELECT COUNT(*) FROM planos_acao pa
                    JOIN parlamentares p ON pa.parlamentar_id = p.parlamentar_id
                    JOIN parlamentares_dados pd ON (
                        p.nome = pd.nome OR p.nome_urna = pd.nome_urna
                        OR pd.nome = p.nome OR pd.nome_urna = p.nome_urna
                    )
                    WHERE pd.deputado_id = %s
                    """,
                    (deputado_id,),
                )
                return cur.fetchone()[0]
            else:
                # TODO: usar parlamentar_id quando coluna for adicionada
                #        nestas tabelas
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {tabela} t
                    JOIN parlamentares_dados pd ON (
                        REPLACE(REPLACE(LOWER(t.parlamentar_nome), ' ', ''), '.', '')
                        IN (REPLACE(REPLACE(LOWER(pd.nome_urna), ' ', ''), '.', ''),
                            REPLACE(REPLACE(LOWER(pd.nome), ' ', ''), '.', ''))
                    )
                    WHERE pd.deputado_id = %s
                    """,
                    (deputado_id,),
                )
                return cur.fetchone()[0]
        elif tabela in tabelas_municipio:
            # Pega UF do deputado e conta registros da UF
            cur.execute(
                "SELECT uf FROM parlamentares_dados WHERE deputado_id = %s",
                (deputado_id,),
            )
            row = cur.fetchone()
            if not row:
                return 0
            uf = row[0]
            if tabela in ("senadores_dados",):
                cur.execute(f"SELECT COUNT(*) FROM {tabela} WHERE uf = %s", (uf,))
            elif tabela in ("prefeitos_dados", "vereadores_dados"):
                # Conta via municipios do deputado (usando parlamentar_id)
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {tabela} t
                    JOIN beneficiario_ibge_map bm ON t.municipio_id = bm.municipio_id
                    JOIN planos_acao pa ON pa.beneficiario_id = bm.beneficiario_id
                    JOIN parlamentares p ON pa.parlamentar_id = p.parlamentar_id
                    JOIN parlamentares_dados pd ON (
                        p.nome = pd.nome OR p.nome_urna = pd.nome_urna
                    )
                    WHERE pd.deputado_id = %s
                    LIMIT 1
                    """,
                    (deputado_id,),
                )
                return min(cur.fetchone()[0], 1)  # 0 ou 1 para sim/não
            else:
                cur.execute(
                    f"""
                    SELECT COUNT(*) FROM {tabela} t
                    JOIN municipios_ibge mi ON t.municipio_id = mi.municipio_id
                    JOIN beneficiario_ibge_map bm ON mi.municipio_id = bm.municipio_id
                    JOIN planos_acao pa ON pa.beneficiario_id = bm.beneficiario_id
                    JOIN parlamentares p ON pa.parlamentar_id = p.parlamentar_id
                    JOIN parlamentares_dados pd ON (
                        p.nome = pd.nome OR p.nome_urna = pd.nome_urna
                    )
                    WHERE pd.deputado_id = %s
                    """,
                    (deputado_id,),
                )
                return cur.fetchone()[0]
        elif tabela in tabelas_beneficiario:
            cur.execute(
                f"""
                SELECT COUNT(*) FROM {tabela} b
                JOIN planos_acao pa ON pa.beneficiario_id = b.beneficiario_id
                JOIN parlamentares p ON pa.parlamentar_id = p.parlamentar_id
                JOIN parlamentares_dados pd ON (
                    p.nome = pd.nome OR p.nome_urna = pd.nome_urna
                )
                WHERE pd.deputado_id = %s
                """,
                (deputado_id,),
            )
            return cur.fetchone()[0]
    except Exception as e:
        log.debug(f"  Erro contando {tabela} para deputado {deputado_id}: {e}")
        return -1  # erro

    return 0


def analisar_staleness(
    deputados: list[dict[str, Any]],
    checkpoints: dict[tuple[str, int], dict[str, Any]],
    cur: Any,
) -> dict[str, Any]:
    """Analisa staleness comparando checkpoints com dados existentes.

    Returns:
        Dict com análise completa.
    """
    total_chunk_types = len(CHUNK_TYPES)

    # Estatísticas por deputado
    por_deputado: list[dict[str, Any]] = []
    # Totais por chunk type
    chunk_stats: dict[str, dict[str, int]] = {
        ct: {"indexado": 0, "ausente": 0, "nunca_visto": 0} for ct, _, _ in CHUNK_TYPES
    }

    for dep in deputados:
        did = dep["deputado_id"]
        indexados = 0
        ausentes = 0
        chunk_detalhes: list[dict[str, Any]] = []

        for chunk_type, chunk_label, _ in CHUNK_TYPES:
            key = (chunk_type, did)
            ckpt = checkpoints.get(key)
            fonte = CHUNK_SOURCE_TABLES.get(chunk_type, "")
            tem_dados = contar_registros_tabela(cur, fonte, did) > 0 if fonte else False

            if ckpt:
                indexados += 1
                chunk_stats[chunk_type]["indexado"] += 1
                chunk_detalhes.append(
                    {
                        "tipo": chunk_type,
                        "rotulo": chunk_label,
                        "status": "indexado",
                        "indexado_em": ckpt["indexed_at"],
                        "tem_dados_fonte": tem_dados,
                    }
                )
            elif tem_dados:
                ausentes += 1
                chunk_stats[chunk_type]["ausente"] += 1
                chunk_detalhes.append(
                    {
                        "tipo": chunk_type,
                        "rotulo": chunk_label,
                        "status": "ausente",
                        "indexado_em": None,
                        "tem_dados_fonte": True,
                    }
                )
            else:
                chunk_stats[chunk_type]["nunca_visto"] += 1
                chunk_detalhes.append(
                    {
                        "tipo": chunk_type,
                        "rotulo": chunk_label,
                        "status": "sem_dados_fonte",
                        "indexado_em": None,
                        "tem_dados_fonte": False,
                    }
                )

        total = total_chunk_types
        por_deputado.append(
            {
                "deputado_id": did,
                "nome": dep["nome"],
                "partido": dep["sigla_partido"],
                "uf": dep["uf"],
                "ultima_atualizacao": dep["ultima_atualizacao"],
                "indexados": indexados,
                "ausentes": ausentes,
                "total": total,
                "pct": round(indexados / total * 100, 1) if total else 0,
                "chunks": chunk_detalhes,
            }
        )

    # Classificar
    atualizados = [d for d in por_deputado if d["indexados"] == total_chunk_types]
    parciais = [d for d in por_deputado if 0 < d["indexados"] < total_chunk_types]
    nunca = [d for d in por_deputado if d["indexados"] == 0]

    # Chunk types que NUNCA foram indexados para ninguém
    chunk_nunca = [
        (ct, label, chunk_stats[ct]["nunca_visto"])
        for ct, label, _ in CHUNK_TYPES
        if chunk_stats[ct]["nunca_visto"] == len(deputados)
    ]

    # Chunk types com maior deficit
    chunk_deficit = sorted(
        [(ct, label, chunk_stats[ct]["ausente"]) for ct, label, _ in CHUNK_TYPES],
        key=lambda x: -x[2],
    )

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_deputados": len(deputados),
        "total_chunk_types": total_chunk_types,
        "atualizados": len(atualizados),
        "parciais": len(parciais),
        "nunca_indexados": len(nunca),
        "deputados_atualizados": [d["nome"] for d in atualizados],
        "deputados_parciais": [
            {
                "nome": d["nome"],
                "partido": d["partido"],
                "indexados": d["indexados"],
                "ausentes": d["ausentes"],
                "pct": d["pct"],
            }
            for d in parciais
        ],
        "deputados_nunca": [
            {"nome": d["nome"], "partido": d["partido"], "uf": d["uf"]} for d in nunca
        ],
        "chunk_types_nunca_indexados": [
            {"tipo": ct, "rotulo": label} for ct, label, _ in chunk_nunca
        ],
        "chunk_types_maior_deficit": [
            {"tipo": ct, "rotulo": label, "ausentes": n} for ct, label, n in chunk_deficit if n > 0
        ],
        "por_deputado": por_deputado,
    }


def formatar_tabela(
    analise: dict[str, Any],
    filtro: str | None = None,
    top: int | None = None,
) -> str:
    """Formata a análise como tabela legível."""
    linhas: list[str] = []

    # Timestamp
    linhas.append(f"🏛️  Staleness do Qdrant — {analise['timestamp']}")
    linhas.append("═" * 60)
    linhas.append("")

    # Resumo
    linhas.append("Resumo:")
    linhas.append(
        f"  ✅ {analise['atualizados']} deputados — totalmente atualizados "
        f"({analise['total_chunk_types']}/{analise['total_chunk_types']} chunk types)"
    )
    linhas.append(f"  ⚠️  {analise['parciais']} deputados — parcialmente indexados")
    linhas.append(f"  ❌ {analise['nunca_indexados']} deputados — nunca indexados")

    chunk_nunca = analise["chunk_types_nunca_indexados"]
    if chunk_nunca:
        linhas.append(
            f"  🔴 {len(chunk_nunca)} chunk types nunca processados "
            f"(de {analise['total_chunk_types']})"
        )

    # Deputados atualizados
    if analise["atualizados"] > 0 and filtro != "stale" and filtro != "missing":
        linhas.append("")
        linhas.append("✅ Totalmente atualizados:")
        for nome in analise["deputados_atualizados"][:10]:
            linhas.append(f"    {nome}")
        if len(analise["deputados_atualizados"]) > 10:
            linhas.append(f"    ... e mais {len(analise['deputados_atualizados']) - 10}")

    # Deputados parciais
    parciais = analise["deputados_parciais"]
    if parciais and filtro != "missing":
        linhas.append("")
        linhas.append(f"⚠️  Parcialmente indexados ({len(parciais)}):")
        linhas.append(f"  {'Nome':35s} {'Partido':10s} {'Indexados':>10s} {'Faltam':>8s}")
        linhas.append(f"  {'-'*35} {'-'*10} {'-'*10} {'-'*8}")
        for d in parciais[: top or len(parciais)]:
            faltam = analise["total_chunk_types"] - d["indexados"]
            linhas.append(
                f"  {d['nome']:35s} {d['partido'] or 'N/A':10s}"
                f" {d['indexados']:>3d}/{analise['total_chunk_types']:>2d}"
                f" {faltam:>3d}"
            )
        if top and len(parciais) > top:
            linhas.append(f"  ... e mais {len(parciais) - top}")

    # Deputados nunca indexados
    nunca = analise["deputados_nunca"]
    if nunca and filtro != "stale":
        linhas.append("")
        linhas.append(f"❌ Nunca indexados ({len(nunca)}):")
        for d in nunca[: top or len(nunca)]:
            linhas.append(f"    {d['nome']:35s} ({d['partido'] or 'N/A'} - {d['uf']})")
        if top and len(nunca) > top:
            linhas.append(f"    ... e mais {len(nunca) - top}")

    # Chunk types com maior deficit
    deficit = analise["chunk_types_maior_deficit"]
    if deficit:
        linhas.append("")
        linhas.append("Chunk types com maior deficit:")
        linhas.append(f"  {'Tipo':30s} {'Ausentes':>10s}")
        linhas.append(f"  {'-'*30} {'-'*10}")
        for item in deficit[:10]:
            linhas.append(f"  {item['tipo']:30s} {item['ausentes']:>3d} deputados")

    # Recomendações
    linhas.append("")
    linhas.append("Recomendações:")
    if analise["nunca_indexados"] > 0 or analise["parciais"] > 0:
        linhas.append("  • ./run.sh cron-qdrant --diff " "(indexação incremental com checkpoint)")
        linhas.append("  • ./run.sh cron-qdrant --rebuild " "(reindexar completo do zero)")
    if chunk_nunca:
        tipos_str = ", ".join(c["tipo"] for c in chunk_nunca[:5])
        linhas.append(f"  • chunk types sem dados fonte: {tipos_str}")
        linhas.append("    → Verificar se os pipelines de enriquecimento rodaram")
    linhas.append("  • ./run.sh cron-dossie --lote 50 (gerar dossiês)")
    linhas.append("")

    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summary de Staleness do Qdrant")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Saída em JSON (para consumo programático)",
    )
    parser.add_argument(
        "--stale",
        action="store_true",
        help="Apenas deputados parcialmente indexados",
    )
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Apenas deputados nunca indexados",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Mostrar apenas os N mais problemáticos",
    )
    args = parser.parse_args()

    # Determinar filtro
    filtro = None
    if args.stale:
        filtro = "stale"
    elif args.missing:
        filtro = "missing"

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            deputados = carregar_deputados(cur)

            # Verificar se tabela de checkpoint existe
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'qdrant_index_checkpoint'
                )
                """
            )
            tem_checkpoint = cur.fetchone()[0]

            checkpoints: dict[tuple[str, int], dict[str, Any]] = {}
            if tem_checkpoint:
                checkpoints = carregar_checkpoints(cur)
            else:
                log.warning(
                    "Tabela qdrant_index_checkpoint não existe. "
                    "Rode './run.sh cron-qdrant --checkpoint' primeiro."
                )

            analise = analisar_staleness(deputados, checkpoints, cur)

        if args.json:
            json.dump(analise, sys.stdout, indent=2, ensure_ascii=False, default=str)
            sys.stdout.write("\n")
        else:
            print(formatar_tabela(analise, filtro=filtro, top=args.top))

    finally:
        conn.close()


if __name__ == "__main__":
    main()
