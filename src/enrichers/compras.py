"""
Enriquecimento de licitações/contratos públicos via PNCP e Dados Abertos Compras.gov.br.

Uso: python3 -m src.enrichers.compras [--dry-run] [--limit N] [--ano YYYY]
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime
from typing import Any

import psycopg2
import requests

from config.settings import (
    ENRICH_RATE_LIMIT,
)
from src.db_utils import get_connection

PNCP_BASE = "https://pncp.gov.br/api/consulta/v1"
COMPRAS_ABERTOS_BASE = "https://dadosabertos.compras.gov.br"


def cnpj_to_municipio_id(cnpj: str | None) -> int | None:
    """Extrai os primeiros 7 dígitos do CNPJ como código IBGE do município."""
    if not cnpj:
        return None
    digits = "".join(c for c in cnpj if c.isdigit())
    if len(digits) < 7:
        return None
    return int(digits[:7])


def request_with_retry(
    url: str, params: dict[str, Any] | None = None, retries: int = 4
) -> dict[str, Any] | None:
    """GET com retry exponencial para lidar com 429/500/timeout."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()  # type: ignore[no-any-return]
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = 3 * (2**attempt)  # 3s, 6s, 12s, 24s
                print(f"    HTTP {resp.status_code} — retry {attempt + 1}/{retries} em {wait}s")
                time.sleep(wait)
                continue
            print(f"    HTTP {resp.status_code} para {url}")
            return None
        except requests.exceptions.Timeout:
            wait = 3 * (2**attempt)
            print(f"    Timeout — retry {attempt + 1}/{retries} em {wait}s")
            time.sleep(wait)
        except requests.exceptions.ConnectionError:
            wait = 3 * (2**attempt)
            print(f"    ConnectionError — retry {attempt + 1}/{retries} em {wait}s")
            time.sleep(wait)
    return None


def buscar_pncp(
    data_inicio: str,
    data_fim: str,
    pagina: int,
    modalidade: int = 8,
) -> list[dict[str, Any]]:
    """Busca contratações no PNCP por período e modalidade."""
    url = f"{PNCP_BASE}/contratacoes/publicacao"
    params = {
        "dataInicial": data_inicio,
        "dataFinal": data_fim,
        "pagina": pagina,
        "codigoModalidadeContratacao": modalidade,
    }
    data = request_with_retry(url, params=params)
    if data:
        return data.get("lista", [])  # type: ignore[no-any-return]
    return []


def buscar_dados_abertos(data_inicio: str, data_fim: str, pagina: int) -> list[dict[str, Any]]:
    """Busca contratos no Dados Abertos Compras.gov.br."""
    url = f"{COMPRAS_ABERTOS_BASE}/dadosabertos/contrato/lista"
    params = {
        "dataVigenciaInicialMin": data_inicio,
        "dataVigenciaInicialMax": data_fim,
        "pagina": pagina,
    }
    data = request_with_retry(url, params=params)
    if data:
        contratos = data.get("ListaDeContratos", {})
        return contratos.get("Contrato", [])  # type: ignore[no-any-return]
    return []


def parse_data(valor: str | None) -> date | None:
    """Converte string de data (YYYY-MM-DD ou DD/MM/YYYY) para date."""
    if not valor:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(valor, fmt).date()
        except ValueError:
            continue
    return None


def upsert_contrato(
    cur: psycopg2.extensions.cursor, row: dict[str, Any], fonte: str, dry_run: bool
) -> None:
    """Insere ou atualiza um registro em compras_municipios."""
    municipio_id = cnpj_to_municipio_id(row.get("cnpj_orgao"))

    if dry_run:
        desc = (row.get("descricao") or "")[:60]
        print(f"    [{fonte}] {row.get('numero', '?')} — {desc}")
        return

    cur.execute(
        """
        INSERT INTO compras_municipios
            (municipio_id, fonte, tipo_documento, numero, descricao,
             valor_estimado, valor_homologado, data_publicacao, data_vigencia,
             modalidade, cnpj_orgao, nome_orgao, cnpj_fornecedor,
             nome_fornecedor, status, uf)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (fonte, numero) DO UPDATE SET
            descricao = EXCLUDED.descricao,
            valor_estimado = EXCLUDED.valor_estimado,
            valor_homologado = EXCLUDED.valor_homologado,
            status = EXCLUDED.status,
            nome_orgao = EXCLUDED.nome_orgao,
            nome_fornecedor = EXCLUDED.nome_fornecedor
    """,
        (
            municipio_id,
            fonte,
            row.get("tipo_documento"),
            row.get("numero"),
            row.get("descricao"),
            row.get("valor_estimado"),
            row.get("valor_homologado"),
            parse_data(row.get("data_publicacao")),
            parse_data(row.get("data_vigencia")),
            row.get("modalidade"),
            row.get("cnpj_orgao"),
            row.get("nome_orgao"),
            row.get("cnpj_fornecedor"),
            row.get("nome_fornecedor"),
            row.get("status"),
            row.get("uf"),
        ),
    )


PNCP_MODALIDADES = [6, 8, 12, 1, 2, 3, 4, 5, 7, 9, 10, 13]


def processar_pncp(cur: psycopg2.extensions.cursor, ano: int, limit: int, dry_run: bool) -> int:
    """Processa contratações do PNCP iterando por modalidade. Retorna quantidade inserida."""
    data_inicio = f"{ano}0101"
    data_fim = f"{ano}1231"
    total = 0

    print(f"\n=== PNCP (publicações {ano}) ===")
    for mod in PNCP_MODALIDADES:
        if limit and total >= limit:
            break

        pagina = 1
        print(f"  Modalidade {mod}...")
        while True:
            contratacoes = buscar_pncp(data_inicio, data_fim, pagina, modalidade=mod)
            if not contratacoes:
                break

            print(f"    Página {pagina}: {len(contratacoes)} contratações")
            for c in contratacoes:
                numero = c.get("numeroControlePNCP", c.get("numero", ""))
                orgao = c.get("orgaoEntidade", {})
                cnpj_orgao = orgao.get("cnpj", "")
                nome_orgao = orgao.get("nomeRazaoSocial", "")

                fornecedor_list = c.get("fornecedores", [])
                cnpj_forn = ""
                nome_forn = ""
                if fornecedor_list:
                    cnpj_forn = fornecedor_list[0].get("cnpj", "")
                    nome_forn = fornecedor_list[0].get("razaoSocial", "")

                row = {
                    "cnpj_orgao": cnpj_orgao,
                    "nome_orgao": nome_orgao,
                    "numero": numero,
                    "descricao": c.get("objetoCompra"),
                    "valor_estimado": c.get("valorTotalEstimado"),
                    "valor_homologado": c.get("valorTotalHomologado"),
                    "data_publicacao": c.get("dataPublicacaoPncp"),
                    "data_vigencia": c.get("dataVigenciaFinal"),
                    "modalidade": c.get("modalidadeNome"),
                    "cnpj_fornecedor": cnpj_forn,
                    "nome_fornecedor": nome_forn,
                    "status": c.get("situacaoCompra"),
                    "tipo_documento": "LICITACAO",
                    "uf": "",
                }

                upsert_contrato(cur, row, "PNCP", dry_run)
                total += 1

                if limit and total >= limit:
                    return total

            cur.connection.commit()
            pagina += 1
            time.sleep(ENRICH_RATE_LIMIT)

    return total


def processar_dados_abertos(
    cur: psycopg2.extensions.cursor, ano: int, limit: int, dry_run: bool
) -> int:
    """Processa contratos do Dados Abertos Compras.gov.br. Retorna quantidade inserida."""
    data_inicio = f"{ano}-01-01"
    data_fim = f"{ano}-12-31"
    total = 0
    pagina = 1

    print(f"\n=== Dados Abertos Compras.gov.br (vigência {ano}) ===")
    while True:
        contratos = buscar_dados_abertos(data_inicio, data_fim, pagina)
        if not contratos:
            break

        print(f"  Página {pagina}: {len(contratos)} contratos")
        for c in contratos:
            numero = c.get("NumeroContrato", "")
            orgao_cnpj = c.get("CNPJOrgaoContratante", "")
            forn_cnpj = c.get("CNPJFornecedor", "")
            forn_nome = c.get("NomeRazaoSocialFornecedor", "")

            row = {
                "cnpj_orgao": orgao_cnpj,
                "nome_orgao": c.get("NomeOrgaoContratante", ""),
                "numero": str(numero) if numero else "",
                "descricao": c.get("ObjetoContrato"),
                "valor_estimado": None,
                "valor_homologado": c.get("ValorTotalContrato"),
                "data_publicacao": None,
                "data_vigencia": c.get("DataVigenciaInicio"),
                "modalidade": c.get("TipoContratacao"),
                "cnpj_fornecedor": forn_cnpj,
                "nome_fornecedor": forn_nome,
                "status": c.get("SituacaoContrato"),
                "tipo_documento": "CONTRATO",
                "uf": "",
            }

            upsert_contrato(cur, row, "DADOS_ABERTOS", dry_run)
            total += 1

            if limit and total >= limit:
                return total

        conn = cur.connection
        conn.commit()
        pagina += 1
        time.sleep(ENRICH_RATE_LIMIT)

    return total


def main():
    parser = argparse.ArgumentParser(
        description="Enriquecer licitações/contratos públicos via PNCP e Dados Abertos",
    )
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostrar, sem salvar")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N registros (0=todos)")
    parser.add_argument("--ano", type=int, default=date.today().year, help="Ano de referência")
    parser.add_argument(
        "--fonte",
        choices=["pncp", "dados_abertos", "all"],
        default="all",
        help="Fonte de dados (default: all)",
    )
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    total_geral = 0

    if args.fonte in ("pncp", "all"):
        total_geral += processar_pncp(cur, args.ano, args.limit, args.dry_run)

    if args.fonte in ("dados_abertos", "all"):
        remaining = (args.limit - total_geral) if args.limit else 0
        if args.limit and remaining <= 0:
            print(f"\nLimite de {args.limit} registros atingido")
        else:
            total_geral += processar_dados_abertos(cur, args.ano, remaining, args.dry_run)

    conn.commit()
    conn.close()

    acao = "buscados" if args.dry_run else "inseridos/atualizados"
    print(f"\nTotal: {total_geral} registros {acao} em compras_municipios")


if __name__ == "__main__":
    main()
