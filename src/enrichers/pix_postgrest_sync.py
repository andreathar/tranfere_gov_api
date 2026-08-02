"""
Sincroniza Emendas PIX (Transferências Especiais) históricas 2022-2024
via API oficial do TransfereGov (PostgREST) exposta pelo pacote mcp-brasil.

Contexto:
    - Nosso `planos_acao` só tem extração 2025/2026 (backend interno).
    - A API pública `api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao_especial`
      cobre 2022-2026 (ids de plano compatíveis com o nosso banco).
    - Gap medido: 2022=8.514, 2023=9.273, 2024=10.934 PIX ausentes.

Uso:
    python3 -m src.enrichers.pix_postgrest_sync [--anos 2022 2023 2024] [--dry-run] [--limit N]

Mapeamento:
    - upsert idempotente via `upsert_plano_acao()` (mesma função do import padrão).
    - beneficiario_id resolvido por CNPJ (fallback nome+UF) — sem CNPJ mapeado fica NULL.
    - objeto_id sintético 990 "Transferências Especiais (Emenda PIX)" (API não expõe objeto).
    - parlamentar_nome normalizado para maiúsculas (bate com convenção existente).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Any

from mcp_brasil._shared.http_client import http_get
from mcp_brasil.data.transferegov.client import _parse_transferencia
from mcp_brasil.data.transferegov.constants import PLANO_ACAO_URL
from mcp_brasil.data.transferegov.schemas import TransferenciaEspecial

from config.settings import SITUACOES_NEGADAS
from src.db_import import LOG_SQL, UPSERT_SQL
from src.db_utils import get_connection

log = logging.getLogger(__name__)

OBJETO_PIX_HIST = 990
OBJETO_PIX_HIST_DESC = "Transferências Especiais (Emenda PIX) — histórico"
PROGRAMA_PIX = 25  # Transferências Especiais
PAGE = 1000

DEFAULT_ANOS = (2022, 2023, 2024)


async def fetch_ano(ano: int, limit: int = 0) -> list[TransferenciaEspecial]:
    """Baixa todas as PIX de um ano da API PostgREST (paginando de 1000 em 1000)."""
    registros: list[TransferenciaEspecial] = []
    offset = 0
    while True:
        params: dict[str, str] = {
            "ano_plano_acao": f"eq.{ano}",
            "limit": str(PAGE),
            "offset": str(offset),
        }
        data = await http_get(PLANO_ACAO_URL, params=params)
        if not isinstance(data, list) or len(data) == 0:
            break
        for raw in data:
            parsed = _parse_transferencia(raw)
            if parsed.id_plano_acao:
                registros.append(parsed)
        if limit and len(registros) >= limit:
            break
        if len(data) < PAGE:
            break
        offset += PAGE
    return registros[:limit] if limit else registros


def carregar_beneficiarios(cur: Any) -> tuple[dict[str, int], dict[tuple[str, str], int]]:
    """Mapas cnpj -> beneficiario_id e (nome, uf) -> beneficiario_id."""
    cur.execute("SELECT beneficiario_id, cnpj, nome, uf FROM beneficiarios WHERE cnpj IS NOT NULL AND cnpj != ''")
    por_cnpj: dict[str, int] = {}
    por_nome_uf: dict[tuple[str, str], int] = {}
    for bid, cnpj, nome, uf in cur.fetchall():
        if cnpj:
            por_cnpj[str(cnpj).replace(".", "").replace("/", "").replace("-", "")] = bid
        if nome and uf:
            por_nome_uf[(str(nome).strip().upper(), str(uf).strip().upper())] = bid
    return por_cnpj, por_nome_uf


def resolver_beneficiario(
    e: TransferenciaEspecial,
    por_cnpj: dict[str, int],
    por_nome_uf: dict[tuple[str, str], int],
) -> int | None:
    cnpj = (e.cnpj_beneficiario or "").replace(".", "").replace("/", "").replace("-", "")
    if cnpj and cnpj in por_cnpj:
        return por_cnpj[cnpj]
    nome = (e.nome_beneficiario or "").strip().upper()
    uf = (e.uf_beneficiario or "").strip().upper()
    if nome and uf and (nome, uf) in por_nome_uf:
        return por_nome_uf[(nome, uf)]
    return None


def primeiro_area_politica(area: str | None) -> str | None:
    """Resume a string gigante de áreas para a primeira área pública."""
    if not area:
        return None
    primeiro = str(area).split(",")[0].strip()
    return primeiro if primeiro else None


def mapear_param(
    e: TransferenciaEspecial,
    por_cnpj: dict[str, int],
    por_nome_uf: dict[tuple[str, str], int],
) -> dict[str, Any] | None:
    if not e.id_plano_acao:
        return None
    custeio = float(e.valor_custeio or 0)
    invest = float(e.valor_investimento or 0)
    nome = (e.nome_parlamentar or "").strip().upper()
    num = (e.numero_emenda or "").strip()
    if not num:
        return None
    return {
        "plano_acao_id": e.id_plano_acao,
        "plano_acao_codigo": e.codigo_plano_acao or "",
        "objeto_id": OBJETO_PIX_HIST,
        "objeto_descricao": OBJETO_PIX_HIST_DESC,
        "programa_id": PROGRAMA_PIX,
        "programa_codigo": str(PROGRAMA_PIX),
        "beneficiario_id": resolver_beneficiario(e, por_cnpj, por_nome_uf),
        "beneficiario_nome": e.nome_beneficiario or "",
        "beneficiario_cnpj": e.cnpj_beneficiario or "",
        "uf": e.uf_beneficiario or "",
        "ente_id": None,
        "plano_acao_situacao": e.situacao or "",
        "plano_trabalho_situacao": None,
        "codigo_emenda_formatado": f"{num}-{nome}" if num else "",
        "valor_custeio": custeio,
        "valor_investimento": invest,
        "valor_total": custeio + invest,
        "politicas_publicas": primeiro_area_politica(e.area_politica_publica),
        "motivo_impedimento": None,
        "numero_parceria": None,
        "data_atualizacao_plano_acao": None,
        "data_atualizacao_plano_trabalho": None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizar PIX 2022-2024 via API PostgREST (mcp-brasil)")
    parser.add_argument("--anos", type=int, nargs="+", default=list(DEFAULT_ANOS), help="Anos a sincronizar")
    parser.add_argument("--dry-run", action="store_true", help="Apenas contar, sem gravar")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N registros por ano (0=todos)")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    # Garante objeto sintético 990 (apenas em modo real)
    if not args.dry_run:
        cur.execute(
            "INSERT INTO objetos (objeto_id, descricao) VALUES (%s, %s) "
            "ON CONFLICT (objeto_id) DO UPDATE SET descricao = EXCLUDED.descricao",
            (OBJETO_PIX_HIST, OBJETO_PIX_HIST_DESC),
        )
        conn.commit()

    por_cnpj, por_nome_uf = carregar_beneficiarios(cur)

    total_baixados = 0
    total_inseridos = 0
    total_atualizados = 0
    sem_beneficiario = 0
    negados = 0
    primeiro_erro: str | None = None
    t0 = time.time()

    for ano in args.anos:
        registros = asyncio.run(fetch_ano(ano, args.limit))
        log.info("Ano %s: %d registros na API", ano, len(registros))
        for e in registros:
            params = mapear_param(e, por_cnpj, por_nome_uf)
            if not params:
                continue
            total_baixados += 1
            if params["beneficiario_id"] is None:
                sem_beneficiario += 1
            if args.dry_run:
                continue
            # SAVEPOINT por registro: erro em um não envenena o lote
            cur.execute("SAVEPOINT rec")
            try:
                # Detecta insert vs update ANTES do upsert
                cur.execute(
                    "SELECT 1 FROM planos_acao WHERE plano_acao_id = %s",
                    (params["plano_acao_id"],),
                )
                existe = cur.fetchone() is not None
                cur.execute(UPSERT_SQL, params)
                cur.execute("RELEASE SAVEPOINT rec")
                if existe:
                    total_atualizados += 1
                else:
                    total_inseridos += 1
                if params["plano_acao_situacao"] in SITUACOES_NEGADAS:
                    negados += 1
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT rec")
                if primeiro_erro is None:
                    primeiro_erro = f"plano {params['plano_acao_id']}: {e}"
                log.warning("Erro plano %s: %s", params["plano_acao_id"], e)
            if total_baixados % 500 == 0:
                print(
                    f"  [{ano}] {total_baixados} baixados | {total_inseridos} ins | "
                    f"{total_atualizados} upd | sem_benef {sem_beneficiario}",
                    flush=True,
                )
        conn.commit()
        print(
            f"  ano {ano}: COMMIT ok (total {total_inseridos + total_atualizados} registros)",
            flush=True,
        )

    if not args.dry_run:
        # Marca origem dos registros históricos sincronizados
        # (função upsert não seta extract_source; default da coluna é 'api_publica')
        anos_sql = ",".join(str(a) for a in args.anos)
        cur.execute(
            f"UPDATE planos_acao SET extract_source = 'mcp-brasil-postgrest' "
            f"WHERE emenda_ano IN ({anos_sql}) "
            f"AND (extract_source IS NULL OR extract_source = 'api_publica')"
        )
        conn.commit()
        cur.execute(
            LOG_SQL,
            (
                OBJETO_PIX_HIST,
                args.anos[0],
                total_baixados,
                negados,
                "mcp-brasil-postgrest",
                f"sync PIX {args.anos}",
            ),
        )
        conn.commit()

    print(f"== PIX PostgREST {args.anos} ==")
    print(f"  baixados:        {total_baixados}")
    print(f"  inseridos:       {total_inseridos}")
    print(f"  atualizados:     {total_atualizados}")
    print(f"  sem beneficiario:{sem_beneficiario}")
    print(f"  negados:         {negados}")
    print(f"  tempo:           {time.time() - t0:.1f}s")
    if primeiro_erro:
        print(f"  primeiro erro:   {primeiro_erro}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
