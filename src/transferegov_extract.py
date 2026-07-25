
#!/usr/bin/env python3
"""
Transferegov Genérico — Extração de Planos de Ação por Objeto.

Uso (da raiz do projeto):
  python3 src/transferegov_extract.py --discover --ano 2026
  python3 src/transferegov_extract.py --objeto 301 --ano 2026
  python3 src/transferegov_extract.py --objeto 301 --ano 2026 --db
  python3 src/transferegov_extract.py --objeto 301 --ano 2026 --negados
  python3 src/transferegov_extract.py --objeto all --ano 2026 --csv --db
  python3 src/transferegov_extract.py --objeto 662 --ano 2026 --situacao REPROVADO CANCELADO

Dependências:
    pip install -r requirements.txt
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime

import pandas as pd
import requests

from config.settings import (
    API_URL_LISTAGEM as API_URL,
)
from config.settings import (
    DEFAULT_PAGE_SIZE,
    HEADERS,
    MAX_RETRIES,
    OUTPUT_CSV,
    OUTPUT_JSON,
    OUTPUT_LOGS,
    OUTPUT_XLSX,
    RETRY_BACKOFF,
    SITUACOES_NEGADAS,
)
from config.settings import (
    DEFAULT_TIMEOUT as TIMEOUT,
)
from config.settings import (
    SLEEP_BETWEEN_PAGES as SLEEP,
)
from src.formatters import format_brl
from src.http_cache import cache_get, cache_set
from src.schemas import validate_records

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("transferegov")


# ---------------------------------------------------------------------------
# Formatação brasileira
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Request com retry
# ---------------------------------------------------------------------------
def make_request(session, params, use_cache=True):
    # Cache hit
    if use_cache:
        cached = cache_get(API_URL, params, ttl=int(SLEEP * 30))  # cache por ~30 páginas
        if cached is not None:
            logger.debug("Cache hit página %s", params["pageNumber"])
            return cached  # retorna dict em vez de Response

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = session.get(API_URL, params=params, headers=HEADERS, timeout=TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if use_cache:
                cache_set(API_URL, params, data)
            return data
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response else "?"
            logger.warning(
                "HTTP %s página %s (tent %d/%d)",
                status, params["pageNumber"], attempt, MAX_RETRIES,
            )
            if exc.response and exc.response.status_code in (401, 403, 404):
                return None
        except requests.exceptions.ConnectionError as exc:
            logger.warning(
                "Conn error página %s (tent %d/%d): %s",
                params["pageNumber"], attempt, MAX_RETRIES, exc,
            )
        except requests.exceptions.Timeout:
            logger.warning(
                "Timeout página %s (tent %d/%d)",
                params["pageNumber"], attempt, MAX_RETRIES,
            )
        except requests.exceptions.RequestException as exc:
            logger.error("Erro requisição: %s", exc)
            return None
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF ** attempt)
    return None


# ---------------------------------------------------------------------------
# Parse response
# ---------------------------------------------------------------------------
def parse_page(body):
    """Parseia o body JSON da resposta da API."""
    if body is None:
        return [], 0
    if isinstance(body, list):
        return body, len(body)
    if isinstance(body, dict):
        total = body.get("total", 0)
        for key in ("listaPlanosAcao", "data", "content", "items", "results"):
            if key in body and isinstance(body[key], list):
                return body[key], total
    return [], 0


# ---------------------------------------------------------------------------
# Paginação genérica
# ---------------------------------------------------------------------------
def extract_all(objeto, ano, politicas_publicas="", uf=None, programa_id=None, situacao_api=None):
    """Extrai todos os planos de ação com paginação e filtros de API."""
    session = requests.Session()
    all_records = []
    page = 1

    obj_param = "" if objeto == "all" else str(objeto)

    while True:
        params = {
            "objetoExecucao": obj_param,
            "objetoExecucaoAno": str(ano),
            "politicasPublicas": politicas_publicas,
            "pageSize": str(DEFAULT_PAGE_SIZE),
            "pageNumber": str(page),
        }

        # Filtros opcionais de API (descobertos via URL real)
        if uf:
            params["uf"] = uf
        if programa_id:
            params["programaId"] = str(programa_id)
        if situacao_api:
            params["planoAcaoSituacao"] = situacao_api

        logger.info("--- Página %d ---", page)

        resp = make_request(session, params)
        if resp is None:
            logger.error("Falha página %d. Extração interrompida.", page)
            break

        records, total = parse_page(resp)

        if page == 1:
            logger.info("Total informado pela API: %s", total)
            if records:
                logger.info("Amostra primeiro registro: %s", json.dumps(records[0], ensure_ascii=False)[:500])

        if not records:
            logger.info("Página %d vazia — fim.", page)
            break

        all_records.extend(records)
        logger.info(
            "Página %d: +%d | Acumulado: %d / %s",
            page, len(records), len(all_records), total,
        )

        if len(records) < DEFAULT_PAGE_SIZE:
            break

        page += 1
        time.sleep(SLEEP)

    return all_records


# ---------------------------------------------------------------------------
# Descobrir objetos
# ---------------------------------------------------------------------------
def discover_objects(ano):
    """Varre a API para listar todos os objetos disponíveis num ano."""
    session = requests.Session()
    objetos = {}
    page = 1

    logger.info("Descobrindo objetos para ano %s...", ano)

    while True:
        params = {
            "objetoExecucao": "",
            "objetoExecucaoAno": str(ano),
            "politicasPublicas": "",
            "pageSize": str(DEFAULT_PAGE_SIZE),
            "pageNumber": str(page),
        }

        resp = make_request(session, params)
        if resp is None:
            break

        records, total = parse_page(resp)
        if not records:
            break

        for r in records:
            oid = r.get("objetoId")
            desc = r.get("objetoDescricao", "")
            if oid and oid not in objetos:
                objetos[oid] = desc

        logger.info(
            "Página %d: +%d registros | objetos únicos: %d",
            page, len(records), len(objetos),
        )

        if len(records) < DEFAULT_PAGE_SIZE:
            break

        page += 1
        time.sleep(0.5)

    return objetos


# ---------------------------------------------------------------------------
# Deduplicação
# ---------------------------------------------------------------------------
def deduplicate(records: list[dict]) -> list[dict]:
    """Remove duplicatas por planoAcaoId, mantendo o último registro."""
    seen = {}
    for rec in records:
        pid = rec.get("planoAcaoId")
        if pid is not None:
            seen[pid] = rec
    return list(seen.values())


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
def export_excel(df, filepath):
    """Exporta DataFrame para Excel com auto-width."""
    with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Planos de Acao")
        ws = writer.sheets["Planos de Acao"]
        for idx, col in enumerate(df.columns):
            max_len = max(
                df[col].fillna("").astype(str).str.len().max() if len(df) else 0,
                len(str(col)),
            ) + 2
            col_letter = (
                chr(65 + idx) if idx < 26
                else chr(64 + idx // 26) + chr(65 + idx % 26)
            )
            ws.column_dimensions[col_letter].width = min(max_len, 60)
    logger.info("Excel: %s", filepath)


def export_csv(df, filepath):
    """Exporta DataFrame para CSV."""
    df.to_csv(filepath, index=False, sep=";", encoding="utf-8-sig")
    logger.info("CSV: %s", filepath)


# ---------------------------------------------------------------------------
# Database import (Fase 2)
# ---------------------------------------------------------------------------
def import_to_db(records: list[dict]) -> tuple[int, int]:
    """Importa registros validados para o PostgreSQL. Retorna (importados, erros)."""
    import psycopg2

    from config.settings import PG_DB, PG_HOST, PG_PASS, PG_PORT, PG_USER

    conn = psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASS,
    )

    cur = conn.cursor()
    imported = 0
    errors = 0

    UPSERT_SQL = """
    SELECT upsert_plano_acao(
        %(plano_acao_id)s, %(plano_acao_codigo)s,
        %(objeto_id)s, %(objeto_descricao)s,
        %(programa_id)s, %(programa_codigo)s,
        %(beneficiario_id)s, %(beneficiario_nome)s, %(beneficiario_cnpj)s,
        %(uf)s, %(ente_id)s,
        %(plano_acao_situacao)s, %(plano_trabalho_situacao)s,
        %(codigo_emenda_formatado)s,
        %(valor_custeio)s, %(valor_investimento)s, %(valor_total)s,
        %(politicas_publicas)s, %(motivo_impedimento)s, %(numero_parceria)s,
        %(data_atualizacao_plano_acao)s, %(data_atualizacao_plano_trabalho)s
    );
    """

    for rec in records:
        params = {
            "plano_acao_id": rec.get("planoAcaoId"),
            "plano_acao_codigo": rec.get("planoAcaoCodigo", ""),
            "objeto_id": rec.get("objetoId"),
            "objeto_descricao": rec.get("objetoDescricao", ""),
            "programa_id": rec.get("programaId"),
            "programa_codigo": rec.get("programaCodigo", ""),
            "beneficiario_id": rec.get("beneficiarioId"),
            "beneficiario_nome": rec.get("beneficiarioNome", ""),
            "beneficiario_cnpj": rec.get("beneficiarioCnpj", ""),
            "uf": rec.get("uf", ""),
            "ente_id": rec.get("enteId"),
            "plano_acao_situacao": rec.get("planoAcaoSituacao", ""),
            "plano_trabalho_situacao": rec.get("planoTrabalhoSituacao"),
            "codigo_emenda_formatado": rec.get("codigoEmendaFormatado", ""),
            "valor_custeio": rec.get("valorCusteio", 0),
            "valor_investimento": rec.get("valorInvestimento", 0),
            "valor_total": rec.get("valorTotal", 0),
            "politicas_publicas": rec.get("politicasPublicas", ""),
            "motivo_impedimento": rec.get("motivoImpedimento"),
            "numero_parceria": rec.get("numeroParceria"),
            "data_atualizacao_plano_acao": rec.get("dataAtualizacaoPlanoAcao"),
            "data_atualizacao_plano_trabalho": rec.get("dataAtualizacaoPlanoTrabalho"),
        }
        try:
            cur.execute(UPSERT_SQL, params)
            imported += 1
        except Exception as e:
            logger.warning("Erro DB plano %s: %s", params["plano_acao_id"], e)
            errors += 1
            conn.rollback()
            continue

    # Parsear codigo_emenda_formatado → emenda_codigo + parlamentar_nome
    try:
        cur.execute("""
            UPDATE planos_acao SET
                emenda_codigo = split_part(codigo_emenda_formatado, '-', 1),
                parlamentar_nome = TRIM(split_part(codigo_emenda_formatado, '-', 2)),
                emenda_ano = CASE
                    WHEN length(split_part(codigo_emenda_formatado, '-', 1)) >= 4
                    THEN SUBSTRING(split_part(codigo_emenda_formatado, '-', 1) FROM 1 FOR 4)::INTEGER
                    ELSE NULL
                END
            WHERE codigo_emenda_formatado IS NOT NULL AND codigo_emenda_formatado != ''
              AND (emenda_codigo IS NULL OR emenda_codigo = '')
        """)
        parsed = cur.rowcount
        if parsed:
            logger.info("Emendas parseadas: %d registros", parsed)
    except Exception as e:
        logger.warning("Erro parseando emendas: %s", e)

    # Log de extração
    try:
        ano = None
        if records:
            codigo = records[0].get("planoAcaoCodigo", "")
            if len(codigo) >= 4:
                try:
                    ano = int(codigo[:4])
                except ValueError:
                    pass
        cur.execute(
            "INSERT INTO extract_log (objeto_id, ano, total_registros, source, notes) "
            "VALUES (%s, %s, %s, %s, %s)",
            (records[0].get("objetoId") if records else None,
             ano, imported, "cli_extract", "via transferegov_extract.py"),
        )
    except Exception:
        pass

    conn.commit()
    cur.close()
    conn.close()

    return imported, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Extrai Planos de Ação do Transferegov.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s --discover --ano 2026
  %(prog)s --objeto 301 --ano 2026
  %(prog)s --objeto 301 --ano 2026 --db
  %(prog)s --objeto 301 --ano 2026 --negados
  %(prog)s --objeto all --ano 2026 --csv --db
  %(prog)s --objeto 662 --ano 2026 --situacao REPROVADO CANCELADO
        """,
    )

    parser.add_argument("--discover", action="store_true",
                        help="Descobrir todos os objetos disponíveis")
    parser.add_argument("--objeto", type=str, default="301",
                        help="Código do objeto (default: 301). Use 'all' para todos.")
    parser.add_argument("--ano", type=str, default="2026",
                        help="Ano exercício (default: 2026)")
    parser.add_argument("--uf", type=str, default=None,
                        help="Filtrar por UF (ex: SP, AL, PI)")
    parser.add_argument("--programa", type=str, default=None,
                        help="Filtrar por programaId (25 = Transferências Especiais)")
    parser.add_argument("--situacao-api", type=str, default=None,
                        help="Filtrar por situação na API (underscores). Ex: IMPEDIDO_RESTRICAO_TECNICA")
    parser.add_argument("--situacao", nargs="+", default=None,
                        help="Filtrar por situação(ões) local. Ex: REPROVADO IMPEDIDO")
    parser.add_argument("--negados", action="store_true",
                        help="Atalho: filtra REPROVADO IMPEDIDO CANCELADO NAO_CUMPROU")
    parser.add_argument("--db", action="store_true",
                        help="Importar direto para o PostgreSQL (transferegov_db)")
    parser.add_argument("--csv", action="store_true",
                        help="Também exportar CSV")
    parser.add_argument("--output", type=str, default=None,
                        help="Nome base do arquivo de saída (sem extensão)")
    parser.add_argument("--no-dedup", action="store_true",
                        help="Não deduplicar registros")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Logging verboso")

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.INFO
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    log_file = OUTPUT_LOGS / f"transferegov_{ts}.log"
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    logger.info("=" * 70)
    logger.info("TRANSFEREGOV — Extração de Planos de Ação")
    logger.info("Endpoint: %s", API_URL)
    logger.info("=" * 70)

    # ---- Modo discover ----
    if args.discover:
        objetos = discover_objects(args.ano)
        print(f"\n{'COD':>5}  DESCRIÇÃO")
        print("-" * 70)
        for oid in sorted(objetos.keys()):
            print(f"{oid:>5}  {objetos[oid]}")
        print(f"\nTotal: {len(objetos)} objetos disponíveis para {args.ano}")

        # Salvar como JSON
        disc_path = OUTPUT_JSON / f"objetos_disponiveis_{args.ano}_{ts}.json"
        with open(disc_path, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in objetos.items()}, f, ensure_ascii=False, indent=2)
        logger.info("Lista salva: %s", disc_path)
        return 0

    # ---- Modo extração ----
    objeto = args.objeto
    ano = args.ano

    # Resolver situação
    situacao_filter = None
    if args.negados:
        situacao_filter = SITUACOES_NEGADAS
    elif args.situacao:
        situacao_filter = set(s.upper() for s in args.situacao)

    logger.info("Objeto: %s | Ano: %s | Filtro situação: %s", objeto, ano, situacao_filter)

    records = extract_all(
        objeto, ano,
        uf=args.uf,
        programa_id=args.programa,
        situacao_api=args.situacao_api,
    )

    if not records:
        logger.warning("Nenhum registro encontrado.")
        return 1

    # Deduplicação (Fase 3)
    before_dedup = len(records)
    if not args.no_dedup:
        records = deduplicate(records)
        if before_dedup != len(records):
            logger.info("Deduplicação: %d → %d registros únicos", before_dedup, len(records))

    # Validação Pydantic (Fase 1)
    validos, erros = validate_records(records, strict=False)
    if erros:
        logger.warning("Validação: %d registros com warnings:", len(erros))
        for e in erros[:5]:
            logger.warning("  %s", e)
        if len(erros) > 5:
            logger.warning("  ... e mais %d erros", len(erros) - 5)
    logger.info("Validação: %d registros válidos", len(validos))

    # Converter para dicts para DataFrame
    records_for_df = [p.model_dump() for p in validos]

    df = pd.DataFrame(records_for_df)

    # Converter valores monetários
    for col in df.columns:
        if "valor" in col.lower():
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Logar situações
    if "planoAcaoSituacao" in df.columns:
        logger.info("Situações encontradas:")
        for sit, count in df["planoAcaoSituacao"].value_counts().items():
            logger.info("  %-25s %d", sit, count)

    # Filtrar por situação
    if situacao_filter:
        before = len(df)
        df = df[df["planoAcaoSituacao"].isin(list(situacao_filter))].copy()
        logger.info("Filtro situacao: %d → %d registros", before, len(df))
        if df.empty:
            logger.info("Nenhum registro com situação %s para objeto %s/%s.",
                        situacao_filter, objeto, ano)

    # ---- Flag --db (Fase 2) ----
    db_imported = 0
    db_errors = 0
    if args.db:
        logger.info("Importando %d registros para PostgreSQL...", len(df))
        db_imported, db_errors = import_to_db(records_for_df)
        logger.info("DB: %d importados, %d erros", db_imported, db_errors)

    # Nome de saída
    if args.output:
        base = args.output
    else:
        obj_tag = "all" if objeto == "all" else objeto
        sit_tag = "_negados" if args.negados else (
            "_".join(sorted(situacao_filter)) if situacao_filter else ""
        )
        base = f"transferegov_{obj_tag}_{ano}{sit_tag}"

    # Exportar
    xlsx_path = OUTPUT_XLSX / f"{base}.xlsx"
    export_excel(df, xlsx_path)

    if args.csv:
        export_csv(df, OUTPUT_CSV / f"{base}.csv")

    # JSON backup
    json_path = OUTPUT_JSON / f"{base}_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(df.to_dict("records"), f, ensure_ascii=False, indent=2)
    logger.info("JSON: %s", json_path)

    # Resumo (Fase 3: formatação BRL)
    print("\n" + "=" * 70)
    print("RESUMO")
    print("=" * 70)
    print(f"Objeto:           {objeto}")
    print(f"Ano:              {ano}")
    print(f"Registros:        {len(df)}")
    print(f"Colunas:          {len(df.columns)}")
    print(f"Arquivo:          {xlsx_path}")
    if "valorTotal" in df.columns:
        total_valor = df["valorTotal"].sum()
        print(f"Valor total:      {format_brl(total_valor)}")
    if "planoAcaoSituacao" in df.columns:
        situacao_series = df['planoAcaoSituacao']
        if not isinstance(situacao_series, pd.Series):
            situacao_series = pd.Series(situacao_series)
        print(f"Situações:        {situacao_series.value_counts().to_dict()}")
    if args.db:
        print(f"DB importados:    {db_imported}")
        if db_errors:
            print(f"DB erros:         {db_errors}")
    print("=" * 70 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
