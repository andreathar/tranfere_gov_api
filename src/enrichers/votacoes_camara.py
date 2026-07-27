"""
Enriquecimento: Votações da Câmara dos Deputados.

Uso: python3 -m src.enrichers.votacoes_camara [--ano ANO] [--dry-run] [--limit N]

Busca todas as votações de um ano na API Dados Abertos da Câmara,
para cada votação busca os votos nominais, e salva tudo no PostgreSQL.
Fluxo:
  1. GET /votacoes?dataInicio=ANO-01-01&dataFim=ANO-12-31  (paginado)
  2. Para cada votação: GET /votacoes/{id}/votos
  3. UPSERT em votacoes_camara + votos_camara
"""

import argparse
import time

import requests

from config.settings import CAMARA_API_BASE, ENRICH_RATE_LIMIT
from src.db_utils import get_connection

# Endpoints da API
VOTACOES_URL = f"{CAMARA_API_BASE}/votacoes"
ITENS_POR_PAGINA = 50  # Máximo seguro para a API


def _get_paginated(url: str, params: dict, max_pages: int = 200, limit: int = 0) -> list[dict]:
    """Busca paginada de uma lista na API da Câmara.
    Se limit > 0, para ao atingir o limite de itens.
    """
    all_items: list[dict] = []
    for page in range(1, max_pages + 1):
        p = {**params, "pagina": page, "itens": ITENS_POR_PAGINA}
        try:
            resp = requests.get(url, params=p, timeout=30)
            resp.raise_for_status()
            data = resp.json().get("dados", [])
        except Exception as e:
            print(f"  ⚠️  Erro na página {page}: {e}", flush=True)
            break
        if not data:
            break
        all_items.extend(data)
        if limit > 0 and len(all_items) >= limit:
            all_items = all_items[:limit]
            break
        # Verificar header de total
        links = resp.json().get("links", [])
        has_next = any(lnk.get("rel") == "next" for lnk in links)
        if not has_next:
            break
        time.sleep(ENRICH_RATE_LIMIT)
    return all_items


def _get_all_votacoes_ano(ano: int, limit: int = 0) -> list[dict]:
    """Busca todas as votações do ano, dividindo em blocos de 3 meses (limite da API).
    Se limit > 0, para ao atingir o limite total.
    """
    trimestres = [
        (f"{ano}-01-01", f"{ano}-03-31"),
        (f"{ano}-04-01", f"{ano}-06-30"),
        (f"{ano}-07-01", f"{ano}-09-30"),
        (f"{ano}-10-01", f"{ano}-12-31"),
    ]
    all_votacoes: list[dict] = []
    for i, (data_inicio, data_fim) in enumerate(trimestres, 1):
        remaining = limit - len(all_votacoes) if limit > 0 else 0
        if limit > 0 and remaining <= 0:
            break
        print(f"  📅 Trimestre {i}: {data_inicio} → {data_fim}", end=" → ", flush=True)
        votacoes = _get_paginated(
            VOTACOES_URL,
            {
                "dataInicio": data_inicio,
                "dataFim": data_fim,
                "ordem": "DESC",
                "ordenarPor": "dataHoraRegistro",
            },
            limit=remaining if limit > 0 else 0,
        )
        print(f"{len(votacoes)} votações", flush=True)
        all_votacoes.extend(votacoes)
    return all_votacoes


def _parse_votacao(raw: dict) -> dict:
    """Extrai campos relevantes de uma votação da API."""
    prop = raw.get("proposicaoObjeto") or raw.get("proposicao") or {}
    evento = raw.get("evento") or {}
    orgaos = raw.get("orgaos") or []
    sigla_orgao = None
    if isinstance(orgaos, list) and orgaos:
        sigla_orgao = orgaos[0].get("sigla") or orgaos[0].get("nome")

    return {
        "votacao_id": str(raw.get("id", "")),
        "data_registro": raw.get("dataHoraRegistro") or raw.get("data"),
        "descricao": raw.get("descricao"),
        "aprovacao": raw.get("aprovacao"),
        "proposicao_id": prop.get("id") if isinstance(prop, dict) else None,
        "proposicao_ementa": prop.get("ementa") if isinstance(prop, dict) else None,
        "tipo_evento": evento.get("descricaoTipo") if isinstance(evento, dict) else None,
        "sigla_orgao": sigla_orgao,
        "situacao": raw.get("situacao"),
    }


def _get_votos(votacao_id: str) -> list[dict]:
    """Busca os votos nominais de uma votação específica."""
    url = f"{VOTACOES_URL}/{votacao_id}/votos"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json().get("dados", [])
    except Exception as e:
        print(f"  ⚠️  Erro ao buscar votos da votação {votacao_id}: {e}")
        return []


def _parse_voto(raw: dict, votacao_id: str) -> dict:
    """Extrai campos relevantes de um voto nominal."""
    dep = raw.get("deputado_") or raw.get("deputado") or {}
    return {
        "votacao_id": votacao_id,
        "deputado_id": dep.get("id") if isinstance(dep, dict) else None,
        "deputado_nome": dep.get("nome") if isinstance(dep, dict) else None,
        "deputado_urna": dep.get("nomeEleitoral") if isinstance(dep, dict) else None,
        "sigla_partido": dep.get("siglaPartido") if isinstance(dep, dict) else None,
        "sigla_uf": dep.get("siglaUf") if isinstance(dep, dict) else None,
        "tipo_voto": raw.get("tipoVoto"),
        "em_segredo": raw.get("emSegredo", False),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Buscar votações e votos nominais da Câmara dos Deputados"
    )
    parser.add_argument("--ano", type=int, default=2026, help="Ano das votações (default: 2026)")
    parser.add_argument("--dry-run", action="store_true", help="Apenas listar, não salvar")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N votações (0=todas)")
    parser.add_argument(
        "--skip-votos", action="store_true", help="Pular busca de votos (só votações)"
    )
    parser.add_argument(
        "--only-nominais",
        action="store_true",
        help="Só salvar votações que tenham votos nominais (plenario)",
    )
    args = parser.parse_args()

    ano = args.ano
    data_inicio = f"{ano}-01-01"
    data_fim = f"{ano}-12-31"

    print(f"🔍 Buscando votações de {ano} ({data_inicio} → {data_fim})...")

    # 1. Buscar todas as votações do ano (em blocos de 3 meses)
    votacoes = _get_all_votacoes_ano(ano, limit=args.limit)
    print(f"   Total: {len(votacoes)} votações")

    if args.limit > 0 and len(votacoes) >= args.limit:
        print(f"   (limitado a {args.limit})")

    if args.dry_run:
        for v in votacoes:
            parsed = _parse_votacao(v)
            aprov = "✅" if parsed["aprovacao"] else "❌" if parsed["aprovacao"] is False else "❓"
            print(
                f"  {aprov} {parsed['votacao_id']:>8} | {parsed['data_registro'][:10] if parsed['data_registro'] else '?':10} | {parsed['descricao'][:60] if parsed['descricao'] else '?'}"
            )
        print(f"\nDry-run: {len(votacoes)} votações listadas (sem salvar)")
        return

    # 2. Salvar no PostgreSQL
    conn = get_connection()
    cur = conn.cursor()

    total_votos_salvos = 0

    for i, raw in enumerate(votacoes, 1):
        votacao = _parse_votacao(raw)
        vid = votacao["votacao_id"]
        if not vid:
            continue

        # UPSERT votação
        aprovacao_bool = bool(votacao["aprovacao"]) if votacao["aprovacao"] is not None else None
        cur.execute(
            """
            INSERT INTO votacoes_camara
                (votacao_id, data_registro, descricao, aprovacao,
                 proposicao_id, proposicao_ementa, tipo_evento, sigla_orgao, situacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (votacao_id) DO UPDATE SET
                data_registro = EXCLUDED.data_registro,
                descricao = EXCLUDED.descricao,
                aprovacao = EXCLUDED.aprovacao,
                proposicao_id = EXCLUDED.proposicao_id,
                proposicao_ementa = EXCLUDED.proposicao_ementa,
                tipo_evento = EXCLUDED.tipo_evento,
                sigla_orgao = EXCLUDED.sigla_orgao,
                situacao = EXCLUDED.situacao,
                updated_at = NOW()
            """,
            (
                votacao["votacao_id"],
                votacao["data_registro"],
                votacao["descricao"],
                aprovacao_bool,
                votacao["proposicao_id"],
                votacao["proposicao_ementa"],
                votacao["tipo_evento"],
                votacao["sigla_orgao"],
                votacao["situacao"],
            ),
        )

        # 3. Buscar e salvar votos nominais
        if not args.skip_votos:
            votos_raw = _get_votos(vid)
            votos = [_parse_voto(v, vid) for v in votos_raw]

            # Se --only-nominais, pular votações sem votos
            if args.only_nominais and not votos:
                cur.execute("DELETE FROM votacoes_camara WHERE votacao_id = %s", (vid,))
                if i % 50 == 0 or i == len(votacoes):
                    conn.commit()
                    print(
                        f"  [{i}/{len(votacoes)}] votações | {total_votos_salvos} votos salvos (skip sem nominais)",
                        flush=True,
                    )
                time.sleep(ENRICH_RATE_LIMIT)
                continue

            for voto in votos:
                if not voto["deputado_id"]:
                    continue
                cur.execute(
                    """
                    INSERT INTO votos_camara
                        (votacao_id, deputado_id, deputado_nome, deputado_urna,
                         sigla_partido, sigla_uf, tipo_voto, em_segredo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (votacao_id, deputado_id) DO UPDATE SET
                        deputado_nome = EXCLUDED.deputado_nome,
                        deputado_urna = EXCLUDED.deputado_urna,
                        sigla_partido = EXCLUDED.sigla_partido,
                        sigla_uf = EXCLUDED.sigla_uf,
                        tipo_voto = EXCLUDED.tipo_voto,
                        em_segredo = EXCLUDED.em_segredo
                    """,
                    (
                        voto["votacao_id"],
                        voto["deputado_id"],
                        voto["deputado_nome"],
                        voto["deputado_urna"],
                        voto["sigla_partido"],
                        voto["sigla_uf"],
                        voto["tipo_voto"],
                        voto["em_segredo"],
                    ),
                )
            total_votos_salvos += len(votos)
            if i % 10 == 0 or i == len(votacoes):
                conn.commit()
                print(
                    f"  [{i}/{len(votacoes)}] votações | {total_votos_salvos} votos salvos",
                    flush=True,
                )
            time.sleep(ENRICH_RATE_LIMIT)
        else:
            if i % 10 == 0 or i == len(votacoes):
                conn.commit()
                print(f"  [{i}/{len(votacoes)}] votações salvas (--skip-votos)")

    # 4. Log de extração
    cur.execute(
        """
        INSERT INTO votacoes_extract_log
            (ano, total_votacoes, total_votos, data_inicio, data_fim)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (ano, len(votacoes), total_votos_salvos, data_inicio, data_fim),
    )
    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Concluído: {len(votacoes)} votações, {total_votos_salvos} votos nominais salvos")


if __name__ == "__main__":
    main()
