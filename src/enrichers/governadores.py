"""
src.enrichers.governadores — Enriquecedor de Governadores dos 26 Estados + DF.

Sincroniza os governadores eleitos (TSE 2022) com a tabela `governadores_dados` no PostgreSQL.
Recupera votação no 1º e 2º turnos, partido e coligação.

Uso:
  python3 -m src.enrichers.governadores [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import logging
from typing import Any

from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Mapeamento consolidado dos 27 Governadores eleitos em 2022 (TSE)
GOVERNADORES_2022: list[dict[str, Any]] = [
    {
        "uf": "AC",
        "nome": "GLADSON CAMELI",
        "partido": "PP",
        "votos_t1": 242100,
        "pct_t1": 56.75,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "PP / MDB / TRIBUNA",
    },
    {
        "uf": "AL",
        "nome": "PAULO DANTAS",
        "partido": "MDB",
        "votos_t1": 708984,
        "pct_t1": 46.64,
        "votos_t2": 834278,
        "pct_t2": 52.33,
        "coligacao": "MDB / PDT / PSB",
    },
    {
        "uf": "AM",
        "nome": "WILSON LIMA",
        "partido": "UNIÃO",
        "votos_t1": 819784,
        "pct_t1": 42.82,
        "votos_t2": 1039192,
        "pct_t2": 56.65,
        "coligacao": "UNIÃO / PL / PTB",
    },
    {
        "uf": "AP",
        "nome": "CLÉCIO LUÍS",
        "partido": "SOLIDARIEDADE",
        "votos_t1": 222168,
        "pct_t1": 53.77,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "SOLIDARIEDADE / PDT / PP",
    },
    {
        "uf": "BA",
        "nome": "JERÔNIMO RODRIGUES",
        "partido": "PT",
        "votos_t1": 4019830,
        "pct_t1": 49.45,
        "votos_t2": 4480464,
        "pct_t2": 52.79,
        "coligacao": "PT / PCdoB / PV / PSD",
    },
    {
        "uf": "CE",
        "nome": "ELMANO DE FREITAS",
        "partido": "PT",
        "votos_t1": 2808300,
        "pct_t1": 54.02,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "PT / MDB / PP / PRTB",
    },
    {
        "uf": "DF",
        "nome": "IBANEIS ROCHA",
        "partido": "MDB",
        "votos_t1": 832633,
        "pct_t1": 50.31,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "MDB / PP / PL / PROS",
    },
    {
        "uf": "ES",
        "nome": "RENATO CASAGRANDE",
        "partido": "PSB",
        "votos_t1": 976652,
        "pct_t1": 46.94,
        "votos_t2": 1171288,
        "pct_t2": 53.80,
        "coligacao": "PSB / MDB / PSDB / CIDADANIA",
    },
    {
        "uf": "GO",
        "nome": "RONALDO CAIADO",
        "partido": "UNIÃO",
        "votos_t1": 1806892,
        "pct_t1": 51.81,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "UNIÃO / MDB / PP / PSC",
    },
    {
        "uf": "MA",
        "nome": "CARLOS BRANDÃO",
        "partido": "PSB",
        "votos_t1": 1769187,
        "pct_t1": 51.29,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "PSB / PT / PCdoB / PV",
    },
    {
        "uf": "MG",
        "nome": "ROMEU ZEMA",
        "partido": "NOVO",
        "votos_t1": 6094136,
        "pct_t1": 56.18,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "NOVO / PP / MDB / PSDB",
    },
    {
        "uf": "MS",
        "nome": "EDUARDO RIEDEL",
        "partido": "PSDB",
        "votos_t1": 361981,
        "pct_t1": 25.17,
        "votos_t2": 808210,
        "pct_t2": 56.90,
        "coligacao": "PSDB / CIDADANIA / PP / PL",
    },
    {
        "uf": "MT",
        "nome": "MAURO MENDES",
        "partido": "UNIÃO",
        "votos_t1": 1114549,
        "pct_t1": 68.45,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "UNIÃO / MDB / PL / PP",
    },
    {
        "uf": "PA",
        "nome": "HELDER BARBALHO",
        "partido": "MDB",
        "votos_t1": 3117276,
        "pct_t1": 70.41,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "MDB / PT / PP / PSD / PDT",
    },
    {
        "uf": "PB",
        "nome": "JOÃO AZEVÊDO",
        "partido": "PSB",
        "votos_t1": 863174,
        "pct_t1": 39.65,
        "votos_t2": 1221904,
        "pct_t2": 52.51,
        "coligacao": "PSB / Republicanos / PP / PSD",
    },
    {
        "uf": "PE",
        "nome": "RAQUEL LYRA",
        "partido": "PSDB",
        "votos_t1": 1009556,
        "pct_t1": 20.58,
        "votos_t2": 3113415,
        "pct_t2": 58.70,
        "coligacao": "PSDB / CIDADANIA / PRTB",
    },
    {
        "uf": "PI",
        "nome": "RAFAEL FONTELES",
        "partido": "PT",
        "votos_t1": 1115139,
        "pct_t1": 57.17,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "PT / PCdoB / PV / MDB / PSD",
    },
    {
        "uf": "PR",
        "nome": "RATINHO JÚNIOR",
        "partido": "PSD",
        "votos_t1": 4243292,
        "pct_t1": 69.64,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "PSD / PP / MDB / Republicanos",
    },
    {
        "uf": "RJ",
        "nome": "CLÁUDIO CASTRO",
        "partido": "PL",
        "votos_t1": 4930288,
        "pct_t1": 58.69,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "PL / MDB / PP / União / PSC",
    },
    {
        "uf": "RN",
        "nome": "FÁTIMA BEZERRA",
        "partido": "PT",
        "votos_t1": 1066496,
        "pct_t1": 58.31,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "PT / PCdoB / PV / MDB / PDT",
    },
    {
        "uf": "RO",
        "nome": "MARCOS ROCHA",
        "partido": "UNIÃO",
        "votos_t1": 330656,
        "pct_t1": 38.88,
        "votos_t2": 458370,
        "pct_t2": 52.47,
        "coligacao": "UNIÃO / Republicanos / Avante",
    },
    {
        "uf": "RR",
        "nome": "ANTONIO DENARIUM",
        "partido": "PP",
        "votos_t1": 163167,
        "pct_t1": 56.47,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "PP / União / Republicanos",
    },
    {
        "uf": "RS",
        "nome": "EDUARDO LEITE",
        "partido": "PSDB",
        "votos_t1": 1702815,
        "pct_t1": 26.81,
        "votos_t2": 3687126,
        "pct_t2": 57.12,
        "coligacao": "PSDB / CIDADANIA / MDB / PSD",
    },
    {
        "uf": "SC",
        "nome": "JORGINHO MELLO",
        "partido": "PL",
        "votos_t1": 1575912,
        "pct_t1": 38.61,
        "votos_t2": 2983949,
        "pct_t2": 70.69,
        "coligacao": "PL / PROS",
    },
    {
        "uf": "SE",
        "nome": "FÁBIO MITIDIERI",
        "partido": "PSD",
        "votos_t1": 294936,
        "pct_t1": 38.91,
        "votos_t2": 623851,
        "pct_t2": 51.70,
        "coligacao": "PSD / PDT / PP / União / MDB",
    },
    {
        "uf": "SP",
        "nome": "TARCÍSIO DE FREITAS",
        "partido": "REPUBLICANOS",
        "votos_t1": 9881995,
        "pct_t1": 42.32,
        "votos_t2": 13480643,
        "pct_t2": 55.27,
        "coligacao": "REPUBLICANOS / PL / PSD / PTB",
    },
    {
        "uf": "TO",
        "nome": "WANDERLEI BARBOSA",
        "partido": "REPUBLICANOS",
        "votos_t1": 481496,
        "pct_t1": 58.14,
        "votos_t2": 0,
        "pct_t2": 0.0,
        "coligacao": "REPUBLICANOS / União / PDT",
    },
]


def sync_governadores(dry_run: bool = False, limit: int = 0) -> None:
    """Sincroniza os 27 governadores eleitos com a tabela governadores_dados."""
    data = GOVERNADORES_2022[:limit] if limit > 0 else GOVERNADORES_2022

    log.info(f"Sincronizando {len(data)} governadores estaduais...")

    records = [
        (
            g["uf"],
            g["nome"],
            g.get("vice", ""),
            g["partido"],
            g.get("coligacao", ""),
            2022,
            g.get("votos_t1", 0),
            g.get("pct_t1", 0.0),
            g.get("votos_t2", 0),
            g.get("pct_t2", 0.0),
            "ELEITO",
        )
        for g in data
    ]

    if dry_run:
        log.info(f"DRY-RUN: {len(records)} governadores seriam inseridos:")
        for r in records[:5]:
            log.info(f"  {r[0]} — {r[1]} ({r[3]}) — T2: {r[9]}%")
        return

    with get_connection() as conn, conn.cursor() as cur:
        insert_sql = """
            INSERT INTO governadores_dados (
                uf, nome_governador, nome_vice, sigla_partido, coligacao,
                ano_eleicao, votos_t1, pct_votos_t1, votos_t2, pct_votos_t2,
                situacao, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (uf) DO UPDATE SET
                nome_governador = EXCLUDED.nome_governador,
                nome_vice = EXCLUDED.nome_vice,
                sigla_partido = EXCLUDED.sigla_partido,
                coligacao = EXCLUDED.coligacao,
                votos_t1 = EXCLUDED.votos_t1,
                pct_votos_t1 = EXCLUDED.pct_votos_t1,
                votos_t2 = EXCLUDED.votos_t2,
                pct_votos_t2 = EXCLUDED.pct_votos_t2,
                situacao = EXCLUDED.situacao,
                updated_at = NOW()
        """
        cur.executemany(insert_sql, records)
        conn.commit()
        log.info(
            f"💾 {len(records)} governadores salvos com sucesso na tabela 'governadores_dados'!"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizar governadores dos 26 estados + DF")
    parser.add_argument("--dry-run", action="store_true", help="Modo simulação")
    parser.add_argument("--limit", type=int, default=0, help="Limitar quantidade N")
    args = parser.parse_args()

    sync_governadores(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
