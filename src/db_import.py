#!/usr/bin/env python3
"""
Importa JSONs de planos de ação para o PostgreSQL (transferegov_db).

Uso:
    python3 src/db_import.py                          # importa todos os JSONs
    python3 src/db_import.py output/json/arquivo.json # importa arquivo específico
"""

import glob
import json
import logging
import os
import sys

from config.settings import PROJECT_ROOT, SITUACOES_NEGADAS
from src.db_utils import get_connection

log = logging.getLogger(__name__)

UPSERT_SQL = """
SELECT upsert_plano_acao(
    %(plano_acao_id)s,
    %(plano_acao_codigo)s,
    %(objeto_id)s,
    %(objeto_descricao)s,
    %(programa_id)s,
    %(programa_codigo)s,
    %(beneficiario_id)s,
    %(beneficiario_nome)s,
    %(beneficiario_cnpj)s,
    %(uf)s,
    %(ente_id)s,
    %(plano_acao_situacao)s,
    %(plano_trabalho_situacao)s,
    %(codigo_emenda_formatado)s,
    %(valor_custeio)s,
    %(valor_investimento)s,
    %(valor_total)s,
    %(politicas_publicas)s,
    %(motivo_impedimento)s,
    %(numero_parceria)s,
    %(data_atualizacao_plano_acao)s,
    %(data_atualizacao_plano_trabalho)s
);
"""

LOG_SQL = """
INSERT INTO extract_log (objeto_id, ano, total_registros, total_negados, source, notes)
VALUES (%s, %s, %s, %s, %s, %s);
"""


def parse_record(rec):
    """Converte um registro JSON para dict de parâmetros SQL."""
    plano_id = rec.get("planoAcaoId")
    if not plano_id:
        return None

    codigo = rec.get("planoAcaoCodigo", "")
    return {
        "plano_acao_id": plano_id,
        "plano_acao_codigo": codigo,
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
        "plano_trabalho_situacao": rec.get("planoTrabalhoSituacao", ""),
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


def import_file(conn, filepath):
    """Importa um arquivo JSON para o banco."""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        print(f"  SKIP: {filepath} — não é lista")
        return 0

    cur = conn.cursor()
    imported = 0
    negados = 0
    errors = []

    for rec in data:
        params = parse_record(rec)
        if not params:
            continue
        try:
            cur.execute(UPSERT_SQL, params)
            imported += 1
            sit = params["plano_acao_situacao"]
            if sit in SITUACOES_NEGADAS:
                negados += 1
        except Exception as e:
            errors.append(f"  ERRO plano {params['plano_acao_id']}: {e}")

    conn.commit()

    # Parsear emendas
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
            print(f"  Emendas parseadas: {parsed}")
    except Exception as e:
        print(f"  Aviso parse emendas: {e}")

    conn.commit()

    # Log
    ano = None
    for rec in data[:1]:
        codigo = rec.get("planoAcaoCodigo", "")
        if len(codigo) >= 4:
            try:
                ano = int(codigo[:4])
            except ValueError:
                pass

    cur.execute(
        LOG_SQL,
        (
            data[0].get("objetoId") if data else None,
            ano,
            imported,
            negados,
            "api_publica",
            f"imported from {os.path.basename(filepath)}",
        ),
    )
    conn.commit()
    cur.close()

    for err in errors:
        print(err)

    return imported


def main():
    conn = get_connection()
    print("Conectado ao banco")

    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        json_dir = str(PROJECT_ROOT / "output" / "json")
        files = glob.glob(os.path.join(json_dir, "*.json"))
        files = [f for f in files if "objetos_disponiveis" not in f]

    if not files:
        print("Nenhum arquivo JSON encontrado.")
        return 1

    total = 0
    for filepath in sorted(files):
        print(f"Importando: {os.path.basename(filepath)}")
        n = import_file(conn, filepath)
        print(f"  → {n} registros importados")
        total += n

    # Resumo
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM planos_acao")
    total_db = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM beneficiarios")
    total_ben = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM objetos")
    total_obj = cur.fetchone()[0]
    cur.close()
    conn.close()

    print(f"\n{'=' * 50}")
    print("IMPORTAÇÃO CONCLUÍDA")
    print(f"{'=' * 50}")
    print(f"Arquivos processados: {len(files)}")
    print(f"Registros importados: {total}")
    print(f"Banco: {total_db} planos | {total_ben} municípios | {total_obj} objetos")
    print(f"{'=' * 50}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
