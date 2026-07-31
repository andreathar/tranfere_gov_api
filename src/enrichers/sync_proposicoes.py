"""
Script para sincronizar proposições (PLs, etc.) dos deputados federais da API da Câmara.
Popula a tabela parlamentar_proposicoes para enriquecer o contexto do RAG.

Diferença vs versão anterior: agora faz PAGINAÇÃO completa (antes limitava a 50 por deputado).

Uso: python3 -m src.enrichers.sync_proposicoes [--limit N] [--itens 200]
"""

import argparse
import logging
import time

import httpx

from config.settings import CAMARA_API_BASE, ENRICH_RATE_LIMIT
from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def sync_proposicoes_deputado(
    dep_id: int,
    nome: str,
    parlamentar_id: int | None = None,
    *,
    max_items: int = 200,
    ano_inicio: int = 2023,
    ano_fim: int = 2026,
) -> int:
    """Busca TODAS as proposições de um deputado (paginado) e salva no banco."""
    url = f"{CAMARA_API_BASE}/proposicoes"
    inseridos = 0
    page = 1

    # Filtro por data — API limita range a 3 meses, usamos só Inicio
    data_inicio = f"{ano_inicio}-01-01"

    while inseridos < max_items:
        params = {
            "idDeputadoAutor": dep_id,
            "ordem": "DESC",
            "ordenarPor": "id",
            "itens": 100,
            "pagina": page,
            "dataApresentacaoInicio": data_inicio,
        }
        try:
            resp = httpx.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                log.warning("HTTP %d para %s (pag %d)", resp.status_code, nome, page)
                break

            dados = resp.json().get("dados", [])
            if not dados:
                break

            with get_connection() as conn, conn.cursor() as cur:
                for prop in dados:
                    if inseridos >= max_items:
                        break

                    proposicao_id = prop.get("id")
                    if not proposicao_id:
                        continue

                    # Verificar duplicata
                    cur.execute(
                        "SELECT 1 FROM parlamentar_proposicoes WHERE proposicao_id = %s",
                        (proposicao_id,),
                    )
                    if cur.fetchone():
                        continue

                    data_apres = prop.get("dataApresentacao")
                    if data_apres:
                        data_apres = data_apres.split("T")[0]

                    # Nota: parlamentar_proposicoes pode precisar de migration
                    # para adicionar a coluna parlamentar_id caso ainda não exista.
                    cur.execute(
                        """
                        INSERT INTO parlamentar_proposicoes
                        (proposicao_id, deputado_id, parlamentar_nome, parlamentar_id,
                         sigla_tipo, numero, ano, ementa, data_apresentacao)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (proposicao_id) DO UPDATE SET
                            ementa = EXCLUDED.ementa,
                            data_apresentacao = EXCLUDED.data_apresentacao
                    """,
                        (
                            proposicao_id,
                            dep_id,
                            nome,
                            parlamentar_id,
                            prop.get("siglaTipo"),
                            prop.get("numero"),
                            prop.get("ano"),
                            prop.get("ementa"),
                            data_apres,
                        ),
                    )
                    inseridos += 1

                conn.commit()

            # Se retornou menos de 100, é a última página
            if len(dados) < 100:
                break

            page += 1
            time.sleep(0.3)

        except Exception as e:
            log.error("Erro ao buscar proposições para %s (pag %d): %s", nome, page, e)
            break

    return inseridos


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincronizar proposições dos deputados (paginado)."
    )
    parser.add_argument("--limit", type=int, default=0, help="Limitar N deputados (0=todos)")
    parser.add_argument(
        "--itens", type=int, default=200, help="Máximo de proposições por deputado (padrão=200)"
    )
    parser.add_argument(
        "--ano-inicio", type=int, default=2023, help="Ano início legislatura (padrão=2023)"
    )
    parser.add_argument(
        "--ano-fim", type=int, default=2026, help="Ano fim legislatura (padrão=2026)"
    )
    args = parser.parse_args()

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT pd.deputado_id, pd.nome,
                   COALESCE(
                     (SELECT parlamentar_id FROM planos_acao WHERE parlamentar_nome = pd.nome AND parlamentar_id IS NOT NULL LIMIT 1),
                     (SELECT parlamentar_id FROM parlamentares WHERE nome = pd.nome LIMIT 1)
                   ) AS parlamentar_id
            FROM parlamentares_dados pd ORDER BY pd.nome
        """
        )
        deputados = cur.fetchall()

    if args.limit > 0:
        deputados = deputados[: args.limit]

    log.info(
        "Iniciando sincronização para %d deputados (max %d proposições, %d-%d)...",
        len(deputados),
        args.itens,
        args.ano_inicio,
        args.ano_fim,
    )

    total_inseridos = 0
    for i, (dep_id, nome, parlamentar_id) in enumerate(deputados, 1):
        inseridos = sync_proposicoes_deputado(
            dep_id,
            nome,
            parlamentar_id=parlamentar_id,
            max_items=args.itens,
            ano_inicio=args.ano_inicio,
            ano_fim=args.ano_fim,
        )
        total_inseridos += inseridos

        if i % 10 == 0:
            log.info(
                "[%d/%d] %s: +%d (total: %d)", i, len(deputados), nome, inseridos, total_inseridos
            )

        time.sleep(ENRICH_RATE_LIMIT)

    log.info("Sincronização concluída! %d novas proposições inseridas no total.", total_inseridos)


if __name__ == "__main__":
    main()
