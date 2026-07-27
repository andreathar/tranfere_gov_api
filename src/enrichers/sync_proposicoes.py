"""
Script para sincronizar proposições (PLs, etc.) dos deputados federais da API da Câmara.
Popula a tabela parlamentar_proposicoes para enriquecer o contexto do LLaMA (RAG).

Uso: python3 -m src.enrichers.sync_proposicoes [--limit N]
"""

import argparse
import time
import logging
import requests

from config.settings import CAMARA_API_BASE, ENRICH_RATE_LIMIT
from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

def sync_proposicoes_deputado(deputado_id: int, nome: str, limit_props: int = 50) -> int:
    """Busca proposições de um deputado e salva no banco de dados."""
    url = f"{CAMARA_API_BASE}/proposicoes"
    params = {
        "idDeputadoAutor": deputado_id,
        "ordem": "DESC",
        "ordenarPor": "id",
        "itens": limit_props
    }
    
    inseridos = 0
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            dados = resp.json().get("dados", [])
            if not dados:
                return 0
                
            with get_connection() as conn, conn.cursor() as cur:
                for prop in dados:
                    proposicao_id = prop.get("id")
                    
                    cur.execute("SELECT proposicao_id FROM parlamentar_proposicoes WHERE proposicao_id = %s", (proposicao_id,))
                    if cur.fetchone():
                        continue
                        
                    data_apres = prop.get("dataApresentacao")
                    if data_apres:
                        data_apres = data_apres.split('T')[0]
                        
                    cur.execute("""
                        INSERT INTO parlamentar_proposicoes 
                        (proposicao_id, deputado_id, parlamentar_nome, sigla_tipo, numero, ano, ementa, data_apresentacao)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (proposicao_id) DO UPDATE SET
                            ementa = EXCLUDED.ementa,
                            data_apresentacao = EXCLUDED.data_apresentacao
                    """, (
                        proposicao_id,
                        deputado_id,
                        nome,
                        prop.get("siglaTipo"),
                        prop.get("numero"),
                        prop.get("ano"),
                        prop.get("ementa"),
                        data_apres
                    ))
                    inseridos += 1
                conn.commit()
    except Exception as e:
        log.error(f"Erro ao buscar proposições para {nome}: {e}")
        
    return inseridos

def main():
    parser = argparse.ArgumentParser(description="Sincronizar proposições dos deputados.")
    parser.add_argument("--limit", type=int, default=0, help="Limitar N deputados para buscar (0=todos)")
    parser.add_argument("--itens", type=int, default=50, help="Quantidade de proposições por deputado (padrão=50)")
    args = parser.parse_args()

    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT deputado_id, nome FROM parlamentares_dados ORDER BY nome")
        deputados = cur.fetchall()
        
    if args.limit > 0:
        deputados = deputados[:args.limit]
        
    log.info(f"Iniciando sincronização para {len(deputados)} deputados...")
    
    total_inseridos = 0
    for i, (dep_id, nome) in enumerate(deputados, 1):
        if i % 10 == 0:
            log.info(f"[{i}/{len(deputados)}] Processando {nome}...")
            
        inseridos = sync_proposicoes_deputado(dep_id, nome, args.itens)
        total_inseridos += inseridos
        
        time.sleep(ENRICH_RATE_LIMIT)
        
    log.info(f"Sincronização concluída! {total_inseridos} novas proposições inseridas no total.")

if __name__ == "__main__":
    main()
