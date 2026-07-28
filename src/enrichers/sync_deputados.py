"""
Puxa todos os deputados faltantes da API da Câmara e os insere no DB.
Também atualiza dados dos deputados já existentes (partido pode mudar).

Uso:
    python3 -m src.enrichers.sync_deputados [--limit N] [--force]
"""

import argparse
import logging
import time

import httpx

from config.settings import CAMARA_API_BASE, ENRICH_RATE_LIMIT
from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Campos relevantes do endpoint /deputados/{id}
_PERFIL_FIELDS = (
    "id, nome, nomeCivil, siglaUfNascimento, municipioNascimento, "
    "dataNascimento, escolaridade"
)


def fetch_all_deputies() -> list[dict]:
    """Busca todos os deputados ativos da API da Câmara (paginado)."""
    all_deps: list[dict] = []
    page = 1
    while True:
        resp = httpx.get(
            f"{CAMARA_API_BASE}/deputados",
            params={"itens": 100, "pagina": page, "ordem": "ASC", "ordenarPor": "nome"},
            timeout=30,
        )
        resp.raise_for_status()
        dados = resp.json().get("dados", [])
        if not dados:
            break
        all_deps.extend(dados)
        log.info("Pagina %d: %d deputados (total: %d)", page, len(dados), len(all_deps))
        page += 1
        time.sleep(0.3)
    return all_deps


def fetch_deputy_detail(dep_id: int) -> dict | None:
    """Busca detalhes completos de um deputado."""
    try:
        resp = httpx.get(f"{CAMARA_API_BASE}/deputados/{dep_id}", timeout=15)
        if resp.status_code == 200:
            return resp.json().get("dados", {})
    except Exception as e:
        log.warning("Erro ao buscar detalhes do deputado %d: %s", dep_id, e)
    return None


def upsert_deputado(cur, dep: dict, detail: dict | None = None) -> bool:
    """Insere ou atualiza um deputado. Retorna True se foi inserido (novo)."""
    dep_id = dep["id"]
    nome = dep["nome"]
    sigla_partido = dep.get("siglaPartido")
    uf = dep.get("siglaUf")
    situacao = dep.get("ultimoStatus", {}).get("situacao") if isinstance(dep.get("ultimoStatus"), dict) else None
    ultimo_status = str(dep.get("ultimoStatus", ""))[:500]

    # Dados do detalhe (mais completos)
    data_nasc = None
    municipio_nasc = None
    uf_nasc = None
    escolaridade = None
    nome_urna = None
    if detail:
        data_nasc = detail.get("dataNascimento", "").split("T")[0] if detail.get("dataNascimento") else None
        municipio_nasc = detail.get("municipioNascimento")
        uf_nasc = detail.get("siglaUfNascimento")
        escolaridade = detail.get("escolaridade")
        nome_urna = detail.get("nomeCivil")

    # Verificar se já existe
    cur.execute("SELECT deputado_id FROM parlamentares_dados WHERE deputado_id = %s", (dep_id,))
    exists = cur.fetchone()

    if exists:
        # Atualizar dados que podem mudar (partido, situação)
        cur.execute("""
            UPDATE parlamentares_dados
            SET sigla_partido = %s, situacao = %s, ultimo_status = %s,
                data_nascimento = COALESCE(%s, data_nascimento),
                municipio_nascimento = COALESCE(%s, municipio_nascimento),
                uf_nascimento = COALESCE(%s, uf_nascimento),
                escolaridade = COALESCE(%s, escolaridade),
                nome_urna = COALESCE(%s, nome_urna)
            WHERE deputado_id = %s
        """, (sigla_partido, situacao, ultimo_status, data_nasc,
              municipio_nasc, uf_nasc, escolaridade, nome_urna, dep_id))
        return False
    else:
        cur.execute("""
            INSERT INTO parlamentares_dados
            (deputado_id, nome, nome_urna, sigla_partido, uf, situacao,
             data_nascimento, municipio_nascimento, uf_nascimento, escolaridade,
             ultimo_status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """, (dep_id, nome, nome_urna, sigla_partido, uf, situacao,
              data_nasc, municipio_nasc, uf_nasc, escolaridade, ultimo_status))
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Sincronizar deputados da API da Câmara.")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N deputados (0=todos)")
    parser.add_argument("--force", action="store_true", help="Re-sincronizar todos (UPDATE mesmo existentes)")
    args = parser.parse_args()

    log.info("Buscando lista completa de deputados da API da Câmara...")
    all_deps = fetch_all_deputies()
    log.info("Total de deputados na API: %d", len(all_deps))

    if args.limit > 0:
        all_deps = all_deps[:args.limit]

    with get_connection() as conn, conn.cursor() as cur:
        # IDs existentes
        existing: set[int] = set()
        if not args.force:
            cur.execute("SELECT deputado_id FROM parlamentares_dados")
            existing = {r[0] for r in cur.fetchall()}
            missing = [d for d in all_deps if d["id"] not in existing]
            log.info("Deputados no DB: %d | Faltando: %d", len(existing), len(missing))
        else:
            missing = all_deps
            log.info("Modo --force: re-sincronizando todos %d deputados", len(missing))

        inseridos = 0
        atualizados = 0
        for i, dep in enumerate(missing, 1):
            # Buscar detalhes completos para deputados novos
            detail = None
            if dep["id"] not in (existing if not args.force else set()):
                detail = fetch_deputy_detail(dep["id"])
                time.sleep(0.3)

            is_new = upsert_deputado(cur, dep, detail)
            if is_new:
                inseridos += 1
            else:
                atualizados += 1

            if i % 25 == 0:
                conn.commit()
                log.info("[%d/%d] +%d novos, %d atualizados", i, len(missing), inseridos, atualizados)

            time.sleep(ENRICH_RATE_LIMIT)

        conn.commit()
        log.info(
            "Concluído! +%d novos, %d atualizados de %d processados",
            inseridos, atualizados, len(missing),
        )


if __name__ == "__main__":
    main()
