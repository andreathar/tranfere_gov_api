#!/usr/bin/env python3
"""
Extrator de Emendas (Discricionárias e Especiais) via Portal da Transparência.

Usa a API oficial do Portal da Transparência (chave: TRANSPARENCIA_API_KEY no .env)
para buscar emendas parlamentares por autor e ano.

A API retorna TODOS os tipos de emenda. Este script classifica:
  - "Transferências Especiais" = Emendas PIX (já resolvidas pelo transferegov_extract.py)
  - Demais tipos = Discricionárias / Finalidade Definida (foco principal deste script)

Uso (da raiz do projeto):
  # Listar emendas de um deputado por nome
  python3 src/extrator_transparencia.py --nome-autor "ADAIL FILHO" --ano 2024

  # Por nome + salvar
  python3 src/extrator_transparencia.py --nome-autor "ADAIL FILHO" --ano 2024 --csv --json

  # Por nome + importar no banco
  python3 src/extrator_transparencia.py --nome-autor "ADAIL FILHO" --ano 2024 --db

  # Por código do parlamentar (busca nome no banco local)
  python3 src/extrator_transparencia.py --parlamentar 4291 --ano 2024 --db

  # Apenas emendas não-PIX (discricionárias)
  python3 src/extrator_transparencia.py --nome-autor "ADAIL FILHO" --ano 2024 --apenas-discricionarias

  # Todas as emendas de todos os parlamentares (modo bulk - cuidado com rate limit)
  python3 src/extrator_transparencia.py --bulk --ano 2024

  # Relatório
  python3 src/extrator_transparencia.py --nome-autor "ADAIL FILHO" --ano 2024 --relatorio

Dependências:
    pip install httpx
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

# Adiciona raiz do projeto ao path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from config.settings import OUTPUT_CSV, OUTPUT_JSON, OUTPUT_LOGS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(OUTPUT_LOGS / "extrator_transparencia.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
TRANSPARENCIA_API_BASE = "https://api.portaldatransparencia.gov.br/api-de-dados"
EMENDAS_URL = f"{TRANSPARENCIA_API_BASE}/emendas"
AUTH_HEADER = "chave-api-dados"
ENV_API_KEY = "TRANSPARENCIA_API_KEY"
PAGE_SIZE = 15  # default da API
SLEEP_BETWEEN_PAGES = 1.5  # segundos — rate limit cortesia

# Tipos de emenda que são PIX (Transferências Especiais)
TIPOS_PIX = {"Emenda Individual - Transferências Especiais"}

# Campos relevantes do raw response da API
CAMPOS_API = [
    "codigoEmenda",
    "ano",
    "tipoEmenda",
    "autor",
    "nomeAutor",
    "numeroEmenda",
    "localidadeDoGasto",
    "funcao",
    "subfuncao",
    "valorEmpenhado",
    "valorLiquidado",
    "valorPago",
    "valorRestoInscrito",
    "valorRestoCancelado",
    "valorRestoPago",
]


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------
def parse_brl(valor: str | None) -> float | None:
    """Converte string BRL '1.234,56' para float."""
    if not valor:
        return None
    try:
        return float(valor.replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def get_all_deputados() -> list[str]:
    """Retorna lista de nomes de todos os deputados no banco local."""
    try:
        from src.db_utils import get_connection

        with get_connection() as conn, conn.cursor() as cur:
            # Tenta da tabela mais completa primeiro
            cur.execute("SELECT nome FROM parlamentares_dados ORDER BY nome")
            rows = cur.fetchall()
            if rows:
                return [r[0] for r in rows if r[0]]

            # Fallback: planos_acao (para quem tem PIX)
            cur.execute(
                "SELECT DISTINCT parlamentar_nome FROM planos_acao "
                "WHERE parlamentar_nome IS NOT NULL ORDER BY 1"
            )
            rows = cur.fetchall()
            return [r[0] for r in rows if r[0]]
    except Exception as e:
        logger.error(f"Erro ao buscar lista de deputados: {e}")
        return []


def get_api_key() -> str:
    """Obtém a chave da API do ambiente."""
    key = os.getenv(ENV_API_KEY)
    if not key:
        logger.error(
            "TRANSPARENCIA_API_KEY não definida. "
            "Obtenha uma em: https://portaldatransparencia.gov.br/api-de-dados"
        )
        sys.exit(1)
    return key


def lookup_parlamentar_nome(codigo: str) -> str | None:
    """Busca nome do parlamentar no banco local pelo código."""
    try:
        from src.db_utils import get_connection

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT nome FROM parlamentares WHERE id = %s OR codigo = %s LIMIT 1",
                (codigo, codigo),
            )
            row = cur.fetchone()
            if row:
                return row[0]
        logger.warning(f"Parlamentar código {codigo} não encontrado no banco local.")
        return None
    except Exception as e:
        logger.warning(f"Não foi possível buscar nome do parlamentar {codigo}: {e}")
        return None


def lookup_parlamentar_id(codigo: str) -> int | None:
    """Busca parlamentar_id no banco local pelo código do parlamentar.

    O parlamentar_id é extraído da posição 5-8 do código de emenda
    (formato YYYYDDDDNNN), conforme a função parse_emenda() do PostgreSQL.
    """
    try:
        pid = int(codigo)
    except (ValueError, TypeError):
        logger.warning(f"parlamentar_id inválido: {codigo}")
        return None

    try:
        from src.db_utils import get_connection

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM planos_acao WHERE parlamentar_id = %s "
                "UNION SELECT 1 FROM parlamentares WHERE parlamentar_id = %s "
                "LIMIT 1",
                (pid, pid),
            )
            if cur.fetchone():
                return pid

        logger.warning(f"parlamentar_id {codigo} não encontrado no banco local.")
        return None
    except Exception as e:
        logger.warning(f"Erro ao buscar parlamentar_id para {codigo}: {e}")
        return None


# ---------------------------------------------------------------------------
# API Calls
# ---------------------------------------------------------------------------
def fetch_emendas(
    api_key: str, ano: int | None = None, nome_autor: str | None = None, pagina: int = 1
) -> tuple[list[dict[str, Any]], bool]:
    """Busca emendas no Portal da Transparência.

    Returns:
        Tupla (lista_registros, tem_proxima_pagina).
    """
    headers = {AUTH_HEADER: api_key, "Accept": "application/json"}
    params: dict[str, Any] = {"pagina": pagina}
    if ano:
        params["ano"] = ano
    if nome_autor:
        params["nomeAutor"] = nome_autor.upper()

    logger.debug(f"GET {EMENDAS_URL} params={params}")
    try:
        response = httpx.get(EMENDAS_URL, headers=headers, params=params, timeout=30.0)
    except httpx.TimeoutException:
        logger.warning(f"Timeout na página {pagina}")
        return [], False
    except httpx.RequestError as e:
        logger.error(f"Erro de requisição na página {pagina}: {e}")
        return [], False

    if response.status_code == 401:
        logger.error("Erro 401: chave API inválida ou sem autorização.")
        return [], False
    if response.status_code == 429:
        logger.warning("Rate limit atingido (429). Aguardando 10s...")
        time.sleep(10)
        return fetch_emendas(api_key, ano, nome_autor, pagina)
    if response.status_code == 400:
        logger.warning(f"Bad request na página {pagina}: {response.text[:200]}")
        return [], False

    response.raise_for_status()
    data: list[dict[str, Any]] = response.json()

    # Se API retornou menos que PAGE_SIZE, não há próxima página
    tem_proxima = len(data) >= PAGE_SIZE
    return data, tem_proxima


# ---------------------------------------------------------------------------
# Processamento
# ---------------------------------------------------------------------------
def processar_emendas(raw_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normaliza e classifica as emendas."""
    resultados = []
    for raw in raw_list:
        tipo = raw.get("tipoEmenda", "")
        e = {
            "codigo_emenda": raw.get("codigoEmenda"),
            "ano": raw.get("ano"),
            "tipo_emenda": tipo,
            "autor": raw.get("autor"),
            "nome_autor": raw.get("nomeAutor"),
            "numero_emenda": raw.get("numeroEmenda"),
            "localidade_gasto": raw.get("localidadeDoGasto"),
            "funcao": raw.get("funcao"),
            "subfuncao": raw.get("subfuncao"),
            "valor_empenhado": parse_brl(raw.get("valorEmpenhado")),
            "valor_liquidado": parse_brl(raw.get("valorLiquidado")),
            "valor_pago": parse_brl(raw.get("valorPago")),
            "valor_resto_inscrito": parse_brl(raw.get("valorRestoInscrito")),
            "valor_resto_cancelado": parse_brl(raw.get("valorRestoCancelado")),
            "valor_resto_pago": parse_brl(raw.get("valorRestoPago")),
            "eh_pix": tipo in TIPOS_PIX,
        }
        resultados.append(e)
    return resultados


def salvar_json(emendas: list[dict[str, Any]], prefixo: str = "emendas") -> str:
    """Salva em JSON."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_JSON / f"{prefixo}_{ts}.json"
    path.write_text(json.dumps(emendas, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"JSON salvo: {path}")
    return str(path)


def salvar_csv(emendas: list[dict[str, Any]], prefixo: str = "emendas") -> str:
    """Salva em CSV."""
    import csv

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_CSV / f"{prefixo}_{ts}.csv"
    if not emendas:
        logger.warning("Nenhum dado para salvar em CSV.")
        return ""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=emendas[0].keys())
        writer.writeheader()
        writer.writerows(emendas)
    logger.info(f"CSV salvo: {path}")
    return str(path)


def _derivar_status(e: dict[str, Any]) -> str:
    """Deriva status_execucao a partir dos valores financeiros."""
    emp = e.get("valor_empenhado") or 0
    pago = e.get("valor_pago") or 0
    liq = e.get("valor_liquidado") or 0
    resto_pago = e.get("valor_resto_pago") or 0

    if emp == 0:
        return "CADASTRADO"
    if pago >= emp or resto_pago >= emp:
        return "CONCLUIDO"
    if pago > 0:
        return "EM_EXECUCAO"
    if liq > 0:
        return "LIQUIDADO"
    if emp > 0:
        return "EMPENHADO"
    return "CADASTRADO"


def upsert_no_banco(emendas: list[dict[str, Any]], parlamentar_id: int | None = None) -> int:
    """Importa emendas para o banco PostgreSQL (tabela emendas_discricionarias).

    Colunas preenchidas:
      - codigo_emenda, ano, parlamentar_nome, valor_total, objeto
      - beneficiario_nome  ← localidadeDoGasto (ex: "COARI - AM")
      - status_execucao    ← derivado dos valores financeiros
      - tipo_emenda        ← raw da API (ex: "Emenda Individual - Transferências com Finalidade Definida")
      - parlamentar_id     ← quando fornecido (necessita coluna no schema)

    Colunas NÃO preenchidas (dados não disponíveis nesta API):
      - numero_convenio, beneficiario_cnpj, data_assinatura

    Coluna gerada automaticamente:
      - parlamentar_nome_normalizado (GENERATED ALWAYS AS)
    """
    from src.db_utils import get_connection

    count = 0
    if parlamentar_id is not None:
        base = """
            INSERT INTO emendas_discricionarias (
                codigo_emenda, ano, parlamentar_nome,
                beneficiario_nome, valor_total, status_execucao,
                objeto, tipo_emenda, parlamentar_id, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (codigo_emenda) DO UPDATE SET
                ano = EXCLUDED.ano,
                parlamentar_nome = EXCLUDED.parlamentar_nome,
                beneficiario_nome = EXCLUDED.beneficiario_nome,
                valor_total = EXCLUDED.valor_total,
                status_execucao = EXCLUDED.status_execucao,
                objeto = EXCLUDED.objeto,
                tipo_emenda = EXCLUDED.tipo_emenda,
                parlamentar_id = EXCLUDED.parlamentar_id,
                updated_at = NOW()
        """
    else:
        base = """
            INSERT INTO emendas_discricionarias (
                codigo_emenda, ano, parlamentar_nome,
                beneficiario_nome, valor_total, status_execucao,
                objeto, tipo_emenda, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, NOW()
            )
            ON CONFLICT (codigo_emenda) DO UPDATE SET
                ano = EXCLUDED.ano,
                parlamentar_nome = EXCLUDED.parlamentar_nome,
                beneficiario_nome = EXCLUDED.beneficiario_nome,
                valor_total = EXCLUDED.valor_total,
                status_execucao = EXCLUDED.status_execucao,
                objeto = EXCLUDED.objeto,
                tipo_emenda = EXCLUDED.tipo_emenda,
                updated_at = NOW()
        """
    with get_connection() as conn:
        with conn.cursor() as cur:
            for e in emendas:
                codigo = e.get("codigo_emenda")
                if not codigo:
                    continue

                objeto = e.get("funcao", "")
                if e.get("subfuncao"):
                    objeto += f" - {e['subfuncao']}"

                loc = e.get("localidade_gasto")
                beneficiario_nome = loc if loc and loc not in ("Nacional", "MÚLTIPLO") else None

                status = _derivar_status(e)

                tipo = e.get("tipo_emenda")

                if parlamentar_id is not None:
                    cur.execute(
                        base,
                        (
                            codigo,
                            e.get("ano"),
                            e.get("nome_autor"),
                            beneficiario_nome,
                            e.get("valor_empenhado"),
                            status,
                            objeto,
                            tipo,
                            parlamentar_id,
                        ),
                    )
                else:
                    cur.execute(
                        base,
                        (
                            codigo,
                            e.get("ano"),
                            e.get("nome_autor"),
                            beneficiario_nome,
                            e.get("valor_empenhado"),
                            status,
                            objeto,
                            tipo,
                        ),
                    )
                count += 1
        conn.commit()
    logger.info(f"{count} registros inseridos/atualizados no banco.")
    return count


def gerar_relatorio(emendas: list[dict[str, Any]]) -> None:
    """Exibe relatório consolidado no terminal."""
    if not emendas:
        print("\n  Nenhuma emenda encontrada.\n")
        return

    pix = [e for e in emendas if e["eh_pix"]]
    disc = [e for e in emendas if not e["eh_pix"]]

    total_emp = sum(e["valor_empenhado"] or 0 for e in emendas)
    total_pago = sum(e["valor_pago"] or 0 for e in emendas)

    def fmt_brl(v):
        if v is None:
            return "R$ 0,00"
        return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    print(f"\n{'=' * 60}")
    print("  RELATÓRIO - EMENDAS PARLAMENTARES")
    print(f"{'=' * 60}")
    print(f"  Autor(a):       {emendas[0]['nome_autor'] or emendas[0]['autor']}")
    print(f"  Ano:            {emendas[0]['ano']}")
    print(f"  Total emendas:  {len(emendas)}")
    print(f"  ├─ PIX (Especiais):     {len(pix)}")
    print(f"  └─ Discricionárias:     {len(disc)}")
    print(f"  Valor empenhado: {fmt_brl(total_emp)}")
    print(f"  Valor pago:      {fmt_brl(total_pago)}")
    print(f"{'=' * 60}")

    if disc:
        print(f"\n{'=' * 60}")
        print("  DISCRICIONÁRIAS (não-PIX)")
        print(f"{'=' * 60}")
        for e in sorted(disc, key=lambda x: x["valor_empenhado"] or 0, reverse=True):
            print(f"  {e['codigo_emenda']}")
            print(f"    Tipo:     {e['tipo_emenda']}")
            print(f"    Função:   {e['funcao']} / {e['subfuncao']}")
            print(f"    Local:    {e['localidade_gasto']}")
            print(f"    Empenhado: {fmt_brl(e['valor_empenhado'])}")
            print(f"    Pago:     {fmt_brl(e['valor_pago'])}")
            print()

    if pix:
        print(
            f"\n  📌 {len(pix)} emenda(s) PIX (Transferências Especiais) - já resolvidas via transferegov_extract.py"
        )
        for e in pix:
            print(f"      {e['codigo_emenda']} - {fmt_brl(e['valor_empenhado'])}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extrator de Emendas via Portal da Transparência",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s --nome-autor "ADAIL FILHO" --ano 2024
  %(prog)s --nome-autor "ADAIL FILHO" --ano 2024 --csv --json --db
  %(prog)s --parlamentar 4291 --ano 2024 --relatorio
  %(prog)s --parlamentar 4291 --ano 2024 --apenas-discricionarias --db
  %(prog)s --bulk --ano 2024 --csv
        """,
    )

    # Filtros
    filtros = parser.add_argument_group("Filtros")
    filtros.add_argument(
        "--nome-autor",
        type=str,
        default=None,
        help="Nome do parlamentar autor (ex: 'ADAIL FILHO')",
    )
    filtros.add_argument(
        "--parlamentar",
        type=str,
        default=None,
        help="Código do parlamentar (busca nome no banco local)",
    )
    filtros.add_argument("--ano", type=int, default=None, help="Ano das emendas (ex: 2024)")
    filtros.add_argument(
        "--apenas-discricionarias",
        action="store_true",
        help="Filtrar apenas emendas NÃO-PIX (discricionárias)",
    )

    # Ações
    acoes = parser.add_argument_group("Ações de saída")
    acoes.add_argument("--json", action="store_true", help="Salvar resultados em JSON")
    acoes.add_argument("--csv", action="store_true", help="Salvar resultados em CSV")
    acoes.add_argument("--db", action="store_true", help="Importar para o banco PostgreSQL")
    acoes.add_argument("--relatorio", action="store_true", help="Exibir relatório consolidado")

    # Bulk
    bulk = parser.add_argument_group("Modo bulk")
    bulk.add_argument(
        "--bulk",
        action="store_true",
        help="Buscar emendas de TODOS os parlamentares no banco (experimental)",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Log verbose (DEBUG)")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    api_key = get_api_key()

    # Resolve nome do autor e parlamentar_id
    nome_autor = args.nome_autor
    parlamentar_id: int | None = None
    if args.parlamentar:
        if not nome_autor:
            nome_autor = lookup_parlamentar_nome(args.parlamentar)
            if nome_autor:
                logger.info(f"Parlamentar código {args.parlamentar} → nome: {nome_autor}")
        parlamentar_id = lookup_parlamentar_id(args.parlamentar)
        if parlamentar_id:
            logger.info(
                f"Parlamentar código {args.parlamentar} → parlamentar_id: {parlamentar_id}"
            )

    if not nome_autor and not args.bulk:
        logger.error("Informe --nome-autor, --parlamentar ou --bulk")
        sys.exit(1)

    if args.bulk:
        logger.info("=== MODO BULK: Buscando emendas de TODOS os deputados ===")
        if not args.ano:
            logger.error("Modo bulk requer --ano (ex: 2026)")
            sys.exit(1)

        # Default: só discricionárias no bulk (PIX já resolvido)
        apenas_disc = args.apenas_discricionarias
        if not apenas_disc:
            logger.info("Modo bulk: filtrando apenas discricionárias (PIX já resolvido)")
            apenas_disc = True

        deputados = get_all_deputados()
        logger.info(f"Encontrados {len(deputados)} deputados no banco local")

        total_geral = 0
        ok = 0
        erros = 0

        for i, nome in enumerate(deputados, 1):
            logger.info(f"[{i}/{len(deputados)}] {nome}...")
            try:
                pagina = 1
                todas: list[dict[str, Any]] = []
                while True:
                    raw_list, tem_proxima = fetch_emendas(api_key, args.ano, nome, pagina)
                    if not raw_list:
                        break
                    emendas = processar_emendas(raw_list)
                    todas.extend(emendas)
                    if not tem_proxima:
                        break
                    pagina += 1
                    time.sleep(SLEEP_BETWEEN_PAGES)

                if apenas_disc:
                    todas = [e for e in todas if not e["eh_pix"]]

                if todas:
                    upsert_no_banco(todas, parlamentar_id=None)
                    total_geral += len(todas)
                    logger.info(
                        f"  ✓ {len(todas)} discricionárias salvas (acumulado: {total_geral})"
                    )
                else:
                    logger.debug(f"  - sem emendas em {args.ano}")

                ok += 1
            except Exception as e:
                logger.error(f"  ✗ Erro com {nome}: {e}")
                erros += 1

            # Pequena pausa entre deputados para não sobrecarregar a API
            if i < len(deputados):
                time.sleep(0.3)

        logger.info(
            f"\n=== BULK CONCLUÍDO ===\n"
            f"  Deputados OK: {ok}\n"
            f"  Erros: {erros}\n"
            f"  Total emendas discricionárias salvas: {total_geral}"
        )
        return

    # -----------------------------------------------------------------------
    # Paginação
    # -----------------------------------------------------------------------
    pagina = 1
    todas_emendas: list[dict[str, Any]] = []

    logger.info(f"Buscando emendas — autor: {nome_autor}, ano: {args.ano or 'todos'}")

    while True:
        raw_list, tem_proxima = fetch_emendas(api_key, args.ano, nome_autor, pagina)
        if not raw_list:
            break

        emendas = processar_emendas(raw_list)
        todas_emendas.extend(emendas)
        logger.info(f"Página {pagina}: +{len(emendas)} emendas (total: {len(todas_emendas)})")

        if not tem_proxima:
            break
        pagina += 1
        time.sleep(SLEEP_BETWEEN_PAGES)

    # -----------------------------------------------------------------------
    # Filtros pós-extração
    # -----------------------------------------------------------------------
    if args.apenas_discricionarias:
        antes = len(todas_emendas)
        todas_emendas = [e for e in todas_emendas if not e["eh_pix"]]
        logger.info(f"Filtro discricionárias: {antes} → {len(todas_emendas)} emendas")

    if not todas_emendas:
        logger.info("Nenhuma emenda encontrada.")
        return

    # -----------------------------------------------------------------------
    # Ações de saída
    # -----------------------------------------------------------------------
    prefixo = (
        f"emendas_{nome_autor.replace(' ', '_')}_{args.ano or 'todos'}"
        if nome_autor
        else "emendas"
    )

    if args.json:
        salvar_json(todas_emendas, prefixo)

    if args.csv:
        salvar_csv(todas_emendas, prefixo)

    if args.db:
        upsert_no_banco(todas_emendas, parlamentar_id=parlamentar_id)

    if args.relatorio or not any([args.json, args.csv, args.db]):
        gerar_relatorio(todas_emendas)

    logger.info("Concluído!")


if __name__ == "__main__":
    main()
