import argparse
import logging
import time
from datetime import UTC, datetime

import requests

from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

ITENS_POR_PAGINA = 100
RATE_LIMIT_SLEEP = 0.3  # segundos entre deputados
BASE_URL = "https://dadosabertos.camara.leg.br/api/v2/deputados/{}/discursos"


def extract_discursos(ano: int = 2026, limit: int | None = None):
    """
    Busca TODOS os discursos do ano informado para cada deputado,
    paginando a API da Câmara, e insere no banco (upsert).

    Args:
        ano: Ano dos discursos (ex: 2026). Default 2026.
        limit: Limita número de deputados processados (para teste).
    """
    conn = get_connection()
    cur = conn.cursor()

    # Busca deputados cadastrados (inclui parlamentar_id para consistência)
    query_deps = "SELECT deputado_id, nome_urna, parlamentar_id FROM parlamentares_dados"
    if limit:
        query_deps += f" LIMIT {limit}"
    cur.execute(query_deps)
    deputados = cur.fetchall()

    log.info(f"Iniciando extração de discursos de {ano} para {len(deputados)} deputados...")

    data_inicio = f"{ano}-01-01"
    data_fim = f"{ano}-12-31"
    total_inseridos = 0
    total_deputados_com_erro = 0

    for idx, row in enumerate(deputados, 1):
        deputado_id, nome, parlamentar_id = row[0], row[1], row[2] if len(row) > 2 else None
        pagina = 1
        inseridos_dep = 0
        erros_dep = 0

        while True:
            params: dict[str, str | int] = {
                "dataInicio": data_inicio,
                "dataFim": data_fim,
                "itens": ITENS_POR_PAGINA,
                "pagina": pagina,
                "ordenarPor": "dataHoraInicio",
                "ordem": "ASC",
            }

            try:
                resp = requests.get(BASE_URL.format(deputado_id), params=params, timeout=15)
                resp.raise_for_status()
                dados = resp.json().get("dados", [])

                if not dados:
                    break  # sem mais páginas

                for item in dados:
                    fase_evento = item.get("faseEvento", {})
                    fase_evento_titulo = (
                        fase_evento.get("titulo", "")
                        if isinstance(fase_evento, dict)
                        else str(fase_evento)
                    )

                    cur.execute(
                        """
                        INSERT INTO parlamentar_discursos
                        (deputado_id, data_hora_inicio, fase_evento, tipo_discurso,
                         keywords, sumario, transcricao, url_texto, parlamentar_id)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (deputado_id, data_hora_inicio) DO NOTHING
                        RETURNING id;
                        """,
                        (
                            deputado_id,
                            item.get("dataHoraInicio"),
                            fase_evento_titulo,
                            item.get("tipoDiscurso"),
                            item.get("keywords"),
                            item.get("sumario"),
                            item.get("transcricao"),
                            item.get("urlTexto"),
                            parlamentar_id,
                        ),
                    )
                    if cur.fetchone():
                        inseridos_dep += 1

                conn.commit()
                pagina += 1

                # Pequena pausa entre páginas do mesmo deputado
                time.sleep(0.15)

            except Exception as e:
                erros_dep += 1
                log.error(f"Erro página {pagina} de {nome} (ID {deputado_id}): {e}")
                conn.rollback()
                if erros_dep >= 3:
                    log.warning(f"Desistindo de {nome} após {erros_dep} erros consecutivos")
                    break
                time.sleep(2)  # espera extra antes de retentar
                continue

        total_inseridos += inseridos_dep
        if erros_dep > 0:
            total_deputados_com_erro += 1

        if inseridos_dep > 0 or erros_dep > 0:
            log.info(
                f"[{idx}/{len(deputados)}] {nome}: {inseridos_dep} discursos salvos"
                + (f" ({erros_dep} páginas com erro)" if erros_dep else "")
            )

        # Rate limit entre deputados
        time.sleep(RATE_LIMIT_SLEEP)

    log.info(
        f"Extração de {ano} concluída. "
        f"Total de discursos novos inseridos: {total_inseridos} "
        f"em {len(deputados)} deputados"
        + (
            f" ({total_deputados_com_erro} com falhas parciais)."
            if total_deputados_com_erro
            else "."
        )
    )

    # Registra no extract_log
    try:
        cur.execute(
            """
            INSERT INTO extract_log
                (objeto_id, ano, total_registros, extracted_at, source, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                -1,  # código interno: discursos
                ano,
                total_inseridos,
                datetime.now(UTC),
                "camara_discursos",
                f"Discursos Câmara {ano}: {total_inseridos} novos, {len(deputados)} deputados processados"
                + (
                    f" ({total_deputados_com_erro} com falhas)" if total_deputados_com_erro else ""
                ),
            ),
        )
        conn.commit()
        log.info("Registrado no extract_log.")
    except Exception as e:
        log.warning(f"Erro ao registrar no extract_log: {e}")
        conn.rollback()

    cur.close()
    conn.close()


def resumo_ano(ano: int = 2026):
    """Exibe quantos discursos já existem no banco para o ano."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT deputado_id)
            FROM parlamentar_discursos
            WHERE EXTRACT(YEAR FROM data_hora_inicio) = %s
            """,
            (ano,),
        )
        total, deputados = cur.fetchone()
        cur.close()
        conn.close()
        log.info(f"Discursos de {ano} no banco: {total} discursos de {deputados} deputados.")
        return total, deputados
    except Exception as e:
        log.warning(f"Não foi possível consultar banco: {e}")
        log.info("A tabela parlamentar_discursos pode não existir ainda.")
        return 0, 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extrai discursos da Câmara dos Deputados via API Dados Abertos"
    )
    parser.add_argument("--ano", type=int, default=2026, help="Ano dos discursos (ex: 2026)")
    parser.add_argument("--limit", type=int, help="Limita número de deputados (para teste)")
    parser.add_argument(
        "--resumo",
        action="store_true",
        help="Apenas consulta quantos discursos já existem no banco",
    )
    args = parser.parse_args()

    if args.resumo:
        resumo_ano(args.ano)
    else:
        extract_discursos(ano=args.ano, limit=args.limit)
