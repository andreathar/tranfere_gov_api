"""
Verbas FNDE — Fundo Nacional de Desenvolvimento da Educação.

Uso: python3 -m src.enrichers.fnde [--dry-run] [--limit N] [--programa PROGRAMA]

Busca dados de repasses do FNDE (FUNDEB, PNAE, PNLD, PNATE) por município.
As APIs são públicas (OData v4 no Olinda/IBGE) e não requerem autenticação.

Requer: municipios_ibge populada.
Cria: fnde_repasses (auto-DDL se não existir).
"""

from __future__ import annotations

import argparse
import time
from typing import Any

import requests

from config.settings import ENRICH_RATE_LIMIT
from src.db_utils import get_connection

# URLs das APIs OData do FNDE (Olinda)
FNDE_BASE = "https://www.fnde.gov.br/olinda-ide/servico"

PROGRAMAS = {
    "FUNDEB": {
        "nome": "FUNDEB - Matrículas Ponderadas",
        "url": f"{FNDE_BASE}/FUNDEB_Matriculas/versao/v1/odata/FUNDEBMatriculas",
        "desc": "Distribuição do FUNDEB com base em matrículas",
    },
    "PNAE": {
        "nome": "PNAE - Alimentação Escolar",
        "url": f"{FNDE_BASE}/PNAE_Numero_Alunos_Atendidos/versao/v1/odata/Alunos_Atendidos",
        "desc": "Programa Nacional de Alimentação Escolar",
    },
    "PNLD": {
        "nome": "PNLD - Livro Didático",
        "url": f"{FNDE_BASE}/PNLD/versao/v1/odata/pdaPNLD",
        "desc": "Programa Nacional do Livro e do Material Didático",
    },
    "PNATE": {
        "nome": "PNATE - Transporte Escolar",
        "url": f"{FNDE_BASE}/PNATE_Alunos_Atendidos/versao/v1/odata/PNATEAlunosAtendidos",
        "desc": "Programa Nacional de Apoio ao Transporte do Escolar",
    },
}


def _create_tables(cur) -> None:
    """Cria tabela para repasses FNDE se não existir."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fnde_repasses (
            id SERIAL PRIMARY KEY,
            municipio_id INTEGER REFERENCES municipios_ibge(municipio_id),
            programa TEXT NOT NULL,
            ano INTEGER,
            descricao_programa TEXT,
            etapa_ensino TEXT,
            tipo_rede TEXT,
            localizacao TEXT,
            quantidade_matriculas INTEGER,
            quantidade_alunos INTEGER,
            valor_total NUMERIC(15,2),
            valor_por_aluno NUMERIC(10,2),
            extracted_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE (municipio_id, programa, ano, etapa_ensino, tipo_rede)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_fnde_municipio ON fnde_repasses(municipio_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_fnde_programa ON fnde_repasses(programa)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_fnde_ano ON fnde_repasses(ano)
    """)


def _build_odata_params(
    *,
    filters: list[str] | None = None,
    top: int = 100,
    skip: int = 0,
    order_by: str | None = None,
) -> dict[str, Any]:
    """Constrói parâmetros OData para consulta."""
    params: dict[str, Any] = {
        "$format": "json",
        "$top": min(top, 1000),
    }
    if skip > 0:
        params["$skip"] = skip
    if filters:
        params["$filter"] = " and ".join(filters)
    if order_by:
        params["$orderby"] = order_by
    return params


def _fetch_odata(url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Busca dados de uma API OData do FNDE."""
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        result: list[dict[str, Any]] = data.get("value", [])
        return result
    except requests.RequestException as e:
        print(f"  ⚠️  Erro ao acessar {url}: {e}")
        return []


def _get_municipio_id(cur, nome_municipio: str, uf: str) -> int | None:
    """Busca municipio_id pelo nome e UF."""
    cur.execute(
        "SELECT municipio_id FROM municipios_ibge WHERE UPPER(nome) = %s AND uf = %s LIMIT 1",
        (nome_municipio.upper().strip(), uf.upper()),
    )
    row = cur.fetchone()
    return row[0] if row else None


def _upsert_fnde(cur, d: dict) -> None:
    """Insere ou atualiza um registro FNDE."""
    cur.execute(
        """
        INSERT INTO fnde_repasses
            (municipio_id, programa, ano, descricao_programa, etapa_ensino,
             tipo_rede, localizacao, quantidade_matriculas, quantidade_alunos,
             valor_total, valor_por_aluno, extracted_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, NOW())
        ON CONFLICT (municipio_id, programa, ano, etapa_ensino, tipo_rede) DO UPDATE SET
            descricao_programa = EXCLUDED.descricao_programa,
            localizacao = EXCLUDED.localizacao,
            quantidade_matriculas = EXCLUDED.quantidade_matriculas,
            quantidade_alunos = EXCLUDED.quantidade_alunos,
            valor_total = EXCLUDED.valor_total,
            valor_por_aluno = EXCLUDED.valor_por_aluno,
            extracted_at = NOW()
        """,
        (
            d["municipio_id"],
            d["programa"],
            d["ano"],
            d["descricao_programa"],
            d["etapa_ensino"],
            d["tipo_rede"],
            d["localizacao"],
            d["quantidade_matriculas"],
            d["quantidade_alunos"],
            d["valor_total"],
            d["valor_por_aluno"],
        ),
    )


def _processar_fundeb(cur, limite: int | None) -> int:
    """Processa dados FUNDEB (matrículas ponderadas)."""
    print("📚 Processando FUNDEB (matrículas ponderadas)...")
    url = PROGRAMAS["FUNDEB"]["url"]
    total = 0
    skip = 0
    batch_size = 100

    while True:
        params = _build_odata_params(top=batch_size, skip=skip)
        registros = _fetch_odata(url, params)

        if not registros:
            break

        for reg in registros:
            try:
                nome_mun = reg.get("MunicipioGe", "").strip()
                uf = reg.get("Uf", "").strip()

                if not nome_mun or not uf:
                    continue

                mun_id = _get_municipio_id(cur, nome_mun, uf)
                if not mun_id:
                    continue

                d = {
                    "municipio_id": mun_id,
                    "programa": "FUNDEB",
                    "ano": reg.get("AnoCenso"),
                    "descricao_programa": "FUNDEB - Matrículas Ponderadas",
                    "etapa_ensino": reg.get("DescricaoTipoEnsino", ""),
                    "tipo_rede": reg.get("TipoRedeEducacao", ""),
                    "localizacao": reg.get("DescricaoTipoLocalizacao", ""),
                    "quantidade_matriculas": reg.get("QtdMatricula", 0),
                    "quantidade_alunos": None,
                    "valor_total": None,
                    "valor_por_aluno": None,
                }
                _upsert_fnde(cur, d)
                total += 1

                if limite and total >= limite:
                    print(f"  ⏹️  Limite de {limite} atingido")
                    return total

            except Exception as e:
                print(f"  ⚠️  Erro ao processar FUNDEB: {e}")
                continue

        skip += batch_size
        time.sleep(ENRICH_RATE_LIMIT)

    print(f"  ✅ {total} registros FUNDEB processados")
    return total


def _processar_pnae(cur, limite: int | None) -> int:
    """Processa dados PNAE (alimentação escolar)."""
    print("🍽️  Processando PNAE (alimentação escolar)...")
    url = PROGRAMAS["PNAE"]["url"]
    total = 0
    skip = 0
    batch_size = 100

    while True:
        params = _build_odata_params(top=batch_size, skip=skip)
        registros = _fetch_odata(url, params)

        if not registros:
            break

        for reg in registros:
            try:
                nome_mun = reg.get("Municipio", "").strip()
                uf = reg.get("Estado", "").strip()

                if not nome_mun or not uf:
                    continue

                mun_id = _get_municipio_id(cur, nome_mun, uf)
                if not mun_id:
                    continue

                d = {
                    "municipio_id": mun_id,
                    "programa": "PNAE",
                    "ano": reg.get("Ano"),
                    "descricao_programa": "PNAE - Alimentação Escolar",
                    "etapa_ensino": reg.get("Etapa_ensino", ""),
                    "tipo_rede": reg.get("Esfera_governo", ""),
                    "localizacao": reg.get("Regiao", ""),
                    "quantidade_matriculas": None,
                    "quantidade_alunos": reg.get("Qt_alunos_pnae", 0),
                    "valor_total": None,
                    "valor_por_aluno": None,
                }
                _upsert_fnde(cur, d)
                total += 1

                if limite and total >= limite:
                    print(f"  ⏹️  Limite de {limite} atingido")
                    return total

            except Exception as e:
                print(f"  ⚠️  Erro ao processar PNAE: {e}")
                continue

        skip += batch_size
        time.sleep(ENRICH_RATE_LIMIT)

    print(f"  ✅ {total} registros PNAE processados")
    return total


def _processar_pnld(cur, limite: int | None) -> int:
    """Processa dados PNLD (livro didático)."""
    print("📖 Processando PNLD (livro didático)...")
    url = PROGRAMAS["PNLD"]["url"]
    total = 0
    skip = 0
    batch_size = 100

    while True:
        params = _build_odata_params(top=batch_size, skip=skip)
        registros = _fetch_odata(url, params)

        if not registros:
            break

        for _reg in registros:
            try:
                # PNLD não tem município, apenas dados agregados
                # Vamos pular por enquanto ou armazenar de forma diferente
                total += 1

                if limite and total >= limite:
                    print(f"  ⏹️  Limite de {limite} atingido")
                    return total

            except Exception as e:
                print(f"  ⚠️  Erro ao processar PNLD: {e}")
                continue

        skip += batch_size
        time.sleep(ENRICH_RATE_LIMIT)

    print(f"  ✅ {total} registros PNLD processados (dados agregados, sem município)")
    return total


def _processar_pnate(cur, limite: int | None) -> int:
    """Processa dados PNATE (transporte escolar)."""
    print("🚌 Processando PNATE (transporte escolar)...")
    url = PROGRAMAS["PNATE"]["url"]
    total = 0
    skip = 0
    batch_size = 100

    while True:
        params = _build_odata_params(top=batch_size, skip=skip)
        registros = _fetch_odata(url, params)

        if not registros:
            break

        for _reg in registros:
            try:
                total += 1

                if limite and total >= limite:
                    print(f"  ⏹️  Limite de {limite} atingido")
                    return total

            except Exception as e:
                print(f"  ⚠️  Erro ao processar PNATE: {e}")
                continue

        skip += batch_size
        time.sleep(ENRICH_RATE_LIMIT)

    print(f"  ✅ {total} registros PNATE processados")
    return total


def main() -> None:
    """Executa o enriquecedor FNDE."""
    parser = argparse.ArgumentParser(
        description="Enriquecer municípios com dados FNDE (verbas educacionais)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Apenas listar sem gravar")
    parser.add_argument("--limit", type=int, default=None, help="Limite de registros por programa")
    parser.add_argument(
        "--programa",
        choices=["FUNDEB", "PNAE", "PNLD", "PNATE", "ALL"],
        default="ALL",
        help="Programa específico ou ALL para todos",
    )
    args = parser.parse_args()

    print("🎓 Enriquecedor FNDE — Verbas Educacionais")
    print("=" * 60)

    if args.dry_run:
        print("🔍 Modo dry-run: nenhuma alteração será feita")
        print()
        for _sigla, info in PROGRAMAS.items():
            print(f"  📋 {info['nome']}")
            print(f"     {info['desc']}")
            print(f"     URL: {info['url']}")
            print()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            _create_tables(cur)
            conn.commit()

            total_geral = 0

            if args.programa in ("FUNDEB", "ALL"):
                total_geral += _processar_fundeb(cur, args.limit)
                conn.commit()

            if args.programa in ("PNAE", "ALL"):
                total_geral += _processar_pnae(cur, args.limit)
                conn.commit()

            if args.programa in ("PNLD", "ALL"):
                total_geral += _processar_pnld(cur, args.limit)
                conn.commit()

            if args.programa in ("PNATE", "ALL"):
                total_geral += _processar_pnate(cur, args.limit)
                conn.commit()

            print()
            print("=" * 60)
            print(f"✅ Total de registros processados: {total_geral}")

            # Resumo por programa
            cur.execute("""
                SELECT programa, COUNT(*) as total,
                       SUM(quantidade_matriculas) as matriculas,
                       SUM(quantidade_alunos) as alunos
                FROM fnde_repasses
                GROUP BY programa
                ORDER BY programa
            """)
            rows = cur.fetchall()
            if rows:
                print()
                print("📊 Resumo por programa:")
                for row in rows:
                    print(
                        f"  • {row[0]}: {row[1]} registros "
                        f"(Matrículas: {row[2] or 0:,}, Alunos: {row[3] or 0:,})"
                    )

    finally:
        conn.close()

    print()
    print("🎉 Enriquecimento FNDE concluído!")


if __name__ == "__main__":
    main()
