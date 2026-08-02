import asyncio
import json
import logging

from src.api.services.db_service import _get_connection
from src.api.services.mcp_service import _mcp_client
from src.datajud_utils import parse_datajud_response

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("enrichers.datajud")


async def process_batch(cnpjs: list[str], limit: int | None = None):
    """Fetches DataJud processes for a list of CNPJs and saves to DB."""
    await _mcp_client.connect()

    conn = _get_connection()
    cur = conn.cursor()

    count = 0

    for cnpj in cnpjs:
        if limit and count >= limit:
            break

        log.info("Fetching DataJud for CNPJ: %s", cnpj)

        # Rate limit explicitly (1 req every 3 seconds to be safe)
        await asyncio.sleep(3.0)

        try:
            # We use a small tamanho to avoid CNJ timeout
            res = await _mcp_client.call_tool(
                "datajud_buscar_processos", {"query": cnpj, "tamanho": 3}
            )

            if res and "Rate limited" in res:
                log.warning("Rate limit hit! Sleeping for 15s...")
                await asyncio.sleep(15.0)
                # Try one more time
                res = await _mcp_client.call_tool(
                    "datajud_buscar_processos", {"query": cnpj, "tamanho": 3}
                )
                if res and "Rate limited" in res:
                    log.error("Failed to fetch DataJud for %s due to rate limits.", cnpj)
                    continue

            if res and "Unknown tool" in res:
                # MCP server sem a tool registrada — nao gravar falso sucesso
                log.error("Tool datajud_buscar_processos indisponivel para %s: %s", cnpj, res)
                cur.execute(
                    """
                    INSERT INTO beneficiario_processos (cnpj, erro, checked_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (cnpj) DO UPDATE SET
                        erro = EXCLUDED.erro,
                        checked_at = NOW();
                    """,
                    (cnpj, res),
                )
                conn.commit()
                continue

            # A tool retorna STRING (markdown/mensagem), nao JSON — o parser
            # converte para (total_processos, dados_estruturados). Sem isso,
            # total caia para 0 silenciosamente e o chunk `risco_judicial`
            # ficava vazio no Qdrant.
            total, dados = parse_datajud_response(res)

            # Upsert into beneficiario_processos
            cur.execute(
                """
                INSERT INTO beneficiario_processos (cnpj, total_processos, processos_detalhes, checked_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (cnpj) DO UPDATE SET
                    total_processos = EXCLUDED.total_processos,
                    processos_detalhes = EXCLUDED.processos_detalhes,
                    erro = NULL,
                    checked_at = NOW();
            """,
                (cnpj, total, json.dumps(dados, ensure_ascii=False)),
            )
            conn.commit()

            log.info("Saved %d processes for CNPJ %s", total, cnpj)
            count += 1

        except Exception as e:
            log.error("Error processing DataJud for %s: %s", cnpj, e)
            cur.execute(
                """
                INSERT INTO beneficiario_processos (cnpj, erro, checked_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (cnpj) DO UPDATE SET
                    erro = EXCLUDED.erro,
                    checked_at = NOW();
            """,
                (cnpj, str(e)),
            )
            conn.commit()

    cur.close()
    conn.close()
    await _mcp_client.close()


def get_pending_cnpjs(reprocess: bool = False) -> list[str]:
    """Gets CNPJs that haven't been checked in DataJud yet.

    Args:
        reprocess: Se True, inclui CNPJs que a versao antiga do enricher gravou
            com `total_processos = 0` mas resposta crua nao-parseada (markdown
            com tabela em `processos_detalhes` ou erro) — para refazer a consulta
            e corrigir o falso-zero.
    """
    conn = _get_connection()
    cur = conn.cursor()

    # Get all distinct CNPJs from beneficiarios that are not in beneficiario_processos
    # or were checked more than 30 days ago
    if reprocess:
        # Marca: total 0 gravado pela versao antiga que NAO e "Nenhum processo"
        # legitimo — ex.: "Unknown tool", markdown crua ou erro. Todos sao
        # falsos-zeros causados pelo parser antigo (json.loads falhando).
        cur.execute("""
            SELECT DISTINCT b.cnpj
            FROM beneficiarios b
            LEFT JOIN beneficiario_processos p ON b.cnpj = p.cnpj
            WHERE p.cnpj IS NULL
               OR p.checked_at < NOW() - INTERVAL '30 days'
               OR (p.total_processos = 0 AND p.erro IS NOT NULL)
               OR (p.total_processos = 0
                   AND p.processos_detalhes::text NOT LIKE '%Nenhum%')
            LIMIT 200;
        """)
    else:
        cur.execute("""
            SELECT DISTINCT b.cnpj
            FROM beneficiarios b
            LEFT JOIN beneficiario_processos p ON b.cnpj = p.cnpj
            WHERE p.cnpj IS NULL OR p.checked_at < NOW() - INTERVAL '30 days'
            LIMIT 100;
        """)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [r["cnpj"] for r in rows if r["cnpj"]]


async def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Max CNPJs to process")
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Refaz CNPJs com dados nao-parseados pela versao antiga (falso-zero)",
    )
    args = parser.parse_args()

    cnpjs = get_pending_cnpjs(reprocess=args.reprocess)
    log.info("Found %d pending CNPJs for DataJud enrichment.", len(cnpjs))

    if cnpjs:
        await process_batch(cnpjs, args.limit)


if __name__ == "__main__":
    asyncio.run(main())
