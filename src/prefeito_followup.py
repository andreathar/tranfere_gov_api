"""
prefeito_followup — CLI Interativo de Busca e Inteligência de Prefeitos.

Consultas ao PostgreSQL (view canônica v_prefeitos_completo):
  - Perfil do Prefeito e Partido
  - População IBGE e IDHM
  - Indicadores Financeiros SICONFI
  - Emendas Pix e Convênios Recebidos
  - Valor Per Capita de Emendas

Uso:
  python3 src/prefeito_followup.py "Amapá"
  python3 src/prefeito_followup.py --buscar "DAYMO"
  python3 src/prefeito_followup.py --uf AP
  python3 src/prefeito_followup.py --partido PP
  python3 src/prefeito_followup.py --ranking
"""

from __future__ import annotations

import argparse
import sys

from src.db_utils import get_connection
from src.formatters import fmt_brl, fmt_num, fmt_pct


def buscar_prefeitos(termo: str) -> list[tuple]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT municipio_id, municipio_nome, uf, prefeito_nome, prefeito_partido, valor_total_emendas
        FROM v_prefeitos_completo
        WHERE UPPER(municipio_nome) LIKE UPPER(%s)
           OR UPPER(prefeito_nome) LIKE UPPER(%s)
        ORDER BY valor_total_emendas DESC
        LIMIT 20
    """,
        (f"%{termo}%", f"%{termo}%"),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def mostrar_perfil_prefeito(termo: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            municipio_id, municipio_nome, uf, prefeito_nome, prefeito_partido,
            ano_eleicao, situacao_candidatura, coligacao,
            ibge_regiao, ibge_populacao, ibge_idhm,
            siconfi_receitas_correntes, siconfi_despesas_correntes, siconfi_autonomia_fiscal_pct,
            total_emendas_recebidas, valor_total_emendas, valor_emendas_aprovadas,
            valor_emendas_impedidas, emendas_per_capita
        FROM v_prefeitos_completo
        WHERE UPPER(municipio_nome) LIKE UPPER(%s)
           OR UPPER(prefeito_nome) LIKE UPPER(%s)
        ORDER BY valor_total_emendas DESC
        LIMIT 1
    """,
        (f"%{termo}%", f"%{termo}%"),
    )
    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    (
        mun_id,
        mun_nome,
        uf,
        pref_nome,
        partido,
        ano,
        sit,
        coligacao,
        regiao,
        pop,
        idhm,
        rec_cor,
        desp_cor,
        auto_fiscal,
        tot_emendas,
        val_emendas,
        val_aprov,
        val_imped,
        per_capita,
    ) = row

    print("\n" + "=" * 75)
    print(f"🏛️  PAINEL DO PREFEITO: {pref_nome} ({partido}/{uf}) — {mun_nome}")
    print("=" * 75)

    print("\n📍 GESTÃO MUNICIPAL & ELEIÇÃO:")
    print(f"   - Município / UF:        {mun_nome} ({uf}) — Região {regiao or 'N/I'}")
    print(f"   - Código IBGE:          {mun_id}")
    print(f"   - Prefeito Eleito:       {pref_nome}")
    print(f"   - Partido / Ano:         {partido or 'N/I'} (Eleição {ano})")
    print(f"   - Coligação:             {coligacao or 'N/I'}")

    print("\n📊 PERFIL SOCIOECONÔMICO (IBGE):")
    print(f"   - População Estimada:   {fmt_num(pop)} habitantes")
    print(f"   - IDHM:                 {idhm or 'N/I'}")

    print("\n💰 INDICADORES FINANCEIROS (SICONFI):")
    print(f"   - Receita Corrente:      {fmt_brl(rec_cor)}")
    print(f"   - Despesa Corrente:      {fmt_brl(desp_cor)}")
    print(f"   - Autonomia Fiscal:      {fmt_pct(auto_fiscal)}")

    print("\n💸 REPASSES EM EMENDAS (TRANSFEREGOV):")
    print(f"   - Total de Emendas:      {fmt_num(tot_emendas)}")
    print(f"   - Valor Total Repassado: {fmt_brl(val_emendas)}")
    print(f"   - Valor Aprovado:        {fmt_brl(val_aprov)}")
    print(f"   - Valor Impedido:        {fmt_brl(val_imped)}")
    print(f"   - Valor Per Capita:      {fmt_brl(per_capita)} / habitante")

    # Buscar Top 5 Deputados que enviaram recursos para esta prefeitura
    cur.execute(
        """
        SELECT pa.parlamentar_nome, COUNT(pa.id) AS qtd, SUM(pa.valor_total) AS total
        FROM planos_acao pa
        JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
        JOIN beneficiario_ibge_map bm ON b.beneficiario_id = bm.beneficiario_id
        WHERE bm.municipio_id = %s AND pa.parlamentar_nome IS NOT NULL
        GROUP BY pa.parlamentar_nome
        ORDER BY total DESC
        LIMIT 5
    """,
        (mun_id,),
    )
    deputados = cur.fetchall()

    if deputados:
        print("\n👥 TOP DEPUTADOS PARCEIROS DO MUNICÍPIO:")
        print(f"   {'Parlamentar':<35} {'Emendas':<10} {'Valor Total':>18}")
        print("   " + "-" * 65)
        for dep_nome, qtd, val in deputados:
            print(f"   {dep_nome:<35} {fmt_num(qtd):<10} {fmt_brl(val):>18}")

    # Buscar Licitações e Fornecedores Vencedores da Prefeitura
    cur.execute(
        """
        SELECT numero, modalidade, descricao, valor_homologado, status, nome_fornecedor, cnpj_fornecedor
        FROM compras_municipios
        WHERE municipio_id = %s
        ORDER BY data_publicacao DESC NULLS LAST
        LIMIT 5
    """,
        (mun_id,),
    )
    licitacoes = cur.fetchall()

    if licitacoes:
        print("\n📜 LICITAÇÕES PUBLICADAS E CONTRATOS DA GESTÃO (PNCP):")
        print(
            f"   {'Nº Processo':<22} {'Modalidade':<15} {'Fornecedor Vencedor':<25} {'Valor Homologado':>15}"
        )
        print("   " + "-" * 80)
        for num, mod, _desc, val_h, _stat, forn_nome, _forn_cnpj in licitacoes:
            num_str = (num or "S/N")[:22]
            mod_str = (mod or "Licitação")[:15]
            forn_str = (forn_nome or "Em Andamento")[:25]
            val = float(val_h) if val_h else 0.0
            print(f"   {num_str:<22} {mod_str:<15} {forn_str:<25} {fmt_brl(val):>15}")

    cur.execute(
        """
        SELECT nome_fornecedor, cnpj_fornecedor, COUNT(*) as qtd_ganhas, SUM(COALESCE(valor_homologado, valor_estimado, 0)) as total_ganho
        FROM compras_municipios
        WHERE municipio_id = %s AND nome_fornecedor IS NOT NULL AND nome_fornecedor <> ''
        GROUP BY nome_fornecedor, cnpj_fornecedor
        ORDER BY total_ganho DESC
        LIMIT 5
    """,
        (mun_id,),
    )
    ganhadores = cur.fetchall()

    if ganhadores:
        print("\n🏆 PRINCIPAIS EMPRESAS / FORNECEDORES VENCEDORES:")
        print(
            f"   {'Razão Social / Fornecedor':<35} {'CNPJ':<18} {'Vencedor em':<12} {'Total Ganho (R$)':>16}"
        )
        print("   " + "-" * 85)
        for forn_nome, forn_cnpj, qtd, val in ganhadores:
            cnpj_str = forn_cnpj or "N/I"
            print(
                f"   {forn_nome[:35]:<35} {cnpj_str:<18} {fmt_num(qtd) + ' licitações':<12} {fmt_brl(val):>16}"
            )

    print("=" * 85 + "\n")
    conn.close()
    return True


def mostrar_ranking_prefeitos(limit: int = 15):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT municipio_nome, uf, prefeito_nome, prefeito_partido, ibge_populacao, valor_total_emendas, emendas_per_capita
        FROM v_prefeitos_completo
        ORDER BY valor_total_emendas DESC
        LIMIT %s
    """,
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()

    print("\n" + "=" * 85)
    print(f"🏆 RANKING TOP {limit} PREFEITURAS POR CAPTAÇÃO DE EMENDAS")
    print("=" * 85)
    print(f"{'#':<3} {'Município/UF':<22} {'Prefeito':<30} {'Partido':<8} {'Valor Total':>16}")
    print("-" * 85)

    for i, (mun, uf, pref, part, _pop, val, _per_capita) in enumerate(rows, 1):
        mun_uf = f"{mun} ({uf})"
        print(f"{i:<3} {mun_uf:<22} {pref:<30} {part or 'N/I':<8} {fmt_brl(val):>16}")
    print("=" * 85 + "\n")


def main():
    parser = argparse.ArgumentParser(description="CLI de Inteligência de Prefeitos")
    parser.add_argument("termo", nargs="?", help="Nome do município ou prefeito")
    parser.add_argument("--buscar", type=str, help="Busca por termo")
    parser.add_argument("--ranking", action="store_true", help="Exibir ranking de captação")
    args = parser.parse_args()

    termo = args.termo or args.buscar

    if args.ranking:
        mostrar_ranking_prefeitos()
        return

    if not termo:
        parser.print_help()
        sys.exit(1)

    if not mostrar_perfil_prefeito(termo):
        prefeitos = buscar_prefeitos(termo)
        if prefeitos:
            print(f"\n🔍 Nenhum resultado exato encontrado para '{termo}'. Sugestões:")
            for _mun_id, mun_nome, uf, pref_nome, part, val in prefeitos:
                print(f"  - {pref_nome} ({part}/{uf}) — {mun_nome} (R$ {val:,.2f})")
        else:
            print(f"\n❌ Nenhum prefeito ou município encontrado para '{termo}'.")


if __name__ == "__main__":
    main()
