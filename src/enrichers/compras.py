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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=30)
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
    municipio_id = row.get("municipio_id") or cnpj_to_municipio_id(row.get("cnpj_orgao"))

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
        ON CONFLICT DO NOTHING
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


PNCP_MODALIDADES = [8, 6, 12, 1, 2, 3, 4, 5]


def processar_pncp(cur: psycopg2.extensions.cursor, ano: int, limit: int, dry_run: bool) -> int:
    """Processa contratações do PNCP iterando por modalidade. Retorna quantidade inserida."""
    hoje = datetime.now()
    hoje_str = hoje.strftime("%Y%m%d")
    # Janela eficiente de 30 dias para evitar timeouts na API publica do PNCP
    data_inicio = f"{ano}0701" if ano >= hoje.year else f"{ano}0101"
    data_fim = hoje_str if ano >= hoje.year else f"{ano}1231"
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
                unidade = c.get("unidadeOrgao", {}) or {}

                cnpj_orgao = orgao.get("cnpj", "")
                nome_orgao = orgao.get("razaoSocial", "") or unidade.get("nomeUnidade", "")
                uf_sigla = unidade.get("ufSigla", "")

                # Resolução direta pelo Código IBGE retornado no PNCP
                ibge_str = str(unidade.get("codigoIbge") or "")
                municipio_id = (
                    int(ibge_str)
                    if ibge_str.isdigit() and len(ibge_str) == 7
                    else cnpj_to_municipio_id(cnpj_orgao)
                )

                fornecedor_list = c.get("fornecedores", [])
                cnpj_forn = ""
                nome_forn = ""
                if fornecedor_list:
                    cnpj_forn = fornecedor_list[0].get("cnpj", "")
                    nome_forn = fornecedor_list[0].get("razaoSocial", "")
                elif c.get("usuarioNome"):
                    nome_forn = str(c.get("usuarioNome") or "")

                row = {
                    "municipio_id": municipio_id,
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
                    "status": c.get("situacaoCompraNome", c.get("situacaoCompra")),
                    "tipo_documento": "LICITACAO",
                    "uf": uf_sigla,
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


def processar_pncp_municipios(
    cur: psycopg2.extensions.cursor, limit: int = 100, dry_run: bool = False
) -> int:
    """Busca licitações no PNCP por CNPJ municipal para as prefeituras com maiores repasses de emendas."""
    import asyncio
    import re

    from mcp_brasil.data.compras.pncp.client import buscar_contratacoes

    cur.execute(
        """
        SELECT DISTINCT bim.municipio_id, b.nome, b.cnpj, m.uf, COALESCE(p.valor_total_emendas, 0) as v_emendas
        FROM beneficiario_ibge_map bim
        JOIN beneficiarios b ON bim.beneficiario_id = b.beneficiario_id
        JOIN municipios_ibge m ON bim.municipio_id = m.municipio_id
        LEFT JOIN v_prefeitos_completo p ON bim.municipio_id = p.municipio_id
        WHERE b.cnpj IS NOT NULL AND b.nome ILIKE 'MUNICIPIO DE%%'
        ORDER BY v_emendas DESC
        LIMIT %s;
    """,
        (limit or 100,),
    )
    targets = cur.fetchall()

    print(f"\n=== Sincronizando PNCP por CNPJ Municipal ({len(targets)} municípios) ===")
    total_inseridos = 0

    for m_id, m_nome, cnpj_raw, uf, _v_emendas in targets:
        cnpj = re.sub(r"\D", "", str(cnpj_raw))
        if not cnpj:
            continue
        print(f"  📍 {m_nome} ({uf}) — CNPJ: {cnpj}")
        for mod in [8, 6, 9, 1]:
            try:
                res_obj = asyncio.run(
                    buscar_contratacoes(
                        "20260101", "20260727", mod, cnpj_orgao=cnpj, pagina=1, tamanho=15
                    )
                )
                data = res_obj.model_dump() if hasattr(res_obj, "model_dump") else res_obj
                contrats = data.get("contratacoes", [])
                if contrats:
                    print(f"     -> Modalidade {mod}: {len(contrats)} contratações encontradas")
                    for c in contrats:
                        numero = c.get("numero_controle_pncp") or c.get("numero", "")
                        row = {
                            "municipio_id": m_id,
                            "cnpj_orgao": cnpj,
                            "nome_orgao": m_nome,
                            "numero": numero,
                            "descricao": c.get("objeto") or c.get("descricao"),
                            "valor_estimado": c.get("valor_estimado"),
                            "valor_homologado": c.get("valor_homologado"),
                            "data_publicacao": (c.get("data_publicacao") or "")[:10],
                            "data_vigencia": None,
                            "modalidade": c.get("modalidade_nome") or f"Modalidade {mod}",
                            "cnpj_fornecedor": None,
                            "nome_fornecedor": "Verificado no PNCP",
                            "status": c.get("situacao_nome", "Divulgada no PNCP"),
                            "tipo_documento": "LICITACAO",
                            "uf": uf,
                        }
                        upsert_contrato(cur, row, "PNCP", dry_run)
                        total_inseridos += 1
                time.sleep(3.0)  # Pausa preventiva para respeitar rate-limit do PNCP
            except Exception as e:
                print(f"     ⚠️ Modalidade {mod} no PNCP: {e}")
                time.sleep(7.0)  # Pausa de recuperação caso ocorra 429

        cur.connection.commit()
        time.sleep(2.0)  # Pausa entre municípios

    return total_inseridos


def main():
    parser = argparse.ArgumentParser(
        description="Enriquecer licitações/contratos públicos via PNCP e Dados Abertos",
    )
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostrar, sem salvar")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N registros (0=todos)")
    parser.add_argument("--ano", type=int, default=date.today().year, help="Ano de referência")
    parser.add_argument(
        "--fonte",
        choices=["pncp", "pncp_municipios", "dados_abertos", "all"],
        default="pncp_municipios",
        help="Fonte de dados (default: pncp_municipios)",
    )
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    total_geral = 0

    if args.fonte == "pncp_municipios":
        total_geral += processar_pncp_municipios(cur, limit=args.limit or 50, dry_run=args.dry_run)
    elif args.fonte in ("pncp", "all"):
        total_geral += processar_pncp(cur, args.ano, args.limit, args.dry_run)
        if args.fonte == "all":
            total_geral += processar_pncp_municipios(
                cur, limit=args.limit or 50, dry_run=args.dry_run
            )

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
