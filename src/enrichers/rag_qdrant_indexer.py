"""
Indexer para base do Qdrant usando dados do banco.
Objetivo: criar os embeds para o sistema de RAG (Perfis de Deputados).

Model: nomic-embed-text-v1.5 (768d)
Metric: Cosine
"""

import logging
import argparse
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.db_utils import get_connection
from src.localai_manager import manager as localai_manager
from config.settings import LOCALAI_BASE_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "deputados_perfis"
EMBEDDER_MODEL = "nomic-embed-text-v1.5"
VECTOR_SIZE = 768

def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int):
    """Cria a coleção se não existir com os parâmetros corretos."""
    try:
        collections = client.get_collections().collections
        if not any(c.name == collection_name for c in collections):
            log.info(f"Criando coleção {collection_name} com {vector_size} dimensões...")
            client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=vector_size,
                    distance=models.Distance.COSINE
                )
            )
            log.info("Coleção criada com sucesso.")
        else:
            log.info(f"Coleção {collection_name} já existe.")
    except Exception as e:
        log.error(f"Erro ao verificar/criar coleção Qdrant: {e}")
        raise

def get_deputado_texts(deputado_id: int) -> List[Dict[str, Any]]:
    """Extrai informações textuais do deputado e formata em chunks para embedding."""
    docs = []
    
    with get_connection() as conn, conn.cursor() as cur:
        # 1. Perfil Base
        cur.execute("SELECT nome, sigla_partido, uf FROM parlamentares_dados WHERE deputado_id = %s", (deputado_id,))
        perfil = cur.fetchone()
        if perfil:
            nome, partido, uf = perfil
            txt_perfil = f"Deputado: {nome}. Partido: {partido}. Estado: {uf}. Atuação geral parlamentar na Câmara."
            docs.append({"text": txt_perfil, "type": "perfil", "deputado_id": deputado_id})

        # 2. Proposições (PLs)
        cur.execute(
            "SELECT sigla_tipo, numero, ano, ementa FROM parlamentar_proposicoes WHERE deputado_id = %s", 
            (deputado_id,)
        )
        for prop in cur.fetchall():
            sigla, num, ano, ementa = prop
            txt_prop = f"Proposição do deputado {nome}: {sigla} {num}/{ano}. Ementa: {ementa}"
            docs.append({
                "text": txt_prop, 
                "type": "proposicao", 
                "deputado_id": deputado_id,
                "ref": f"{sigla} {num}/{ano}"
            })

        # 3. Emendas e Atos (Diário Oficial)
        # Nota: o script diario_oficial_worker insere em plano_acao_diario e pode ter ementas extraídas
        # Para fins de MVP, vamos pegar as emendas diretamente de planos_acao
        cur.execute("""
            SELECT b.nome, b.uf, o.descricao, pa.valor_total 
            FROM planos_acao pa 
            JOIN beneficiarios b ON pa.beneficiario_id = b.beneficiario_id
            JOIN objetos o ON pa.objeto_id = o.objeto_id
            JOIN parlamentares_dados pd ON pa.parlamentar_nome = pd.nome_urna OR pa.parlamentar_nome = pd.nome
            WHERE pd.deputado_id = %s
            LIMIT 20
        """, (deputado_id,))
        for emenda in cur.fetchall():
            municipio, emp_uf, obj, valor = emenda
            txt_emenda = f"Emenda do deputado {nome} para {municipio}-{emp_uf}. Objeto: {obj}. Valor repassado: R$ {valor:,.2f}."
            docs.append({
                "text": txt_emenda,
                "type": "emenda",
                "deputado_id": deputado_id,
                "ref": f"Emenda para {municipio}"
            })
            
    return docs

def embed_text(text: str) -> List[float]:
    """Gera o embedding usando o LocalAI via API compatível com OpenAI."""
    import requests
    url = f"{LOCALAI_BASE_URL.rstrip('/')}/embeddings"
    payload = {
        "input": text,
        "model": EMBEDDER_MODEL
    }
    resp = requests.post(url, json=payload, timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        return data["data"][0]["embedding"]
    else:
        log.error(f"Erro ao embeddar texto: {resp.status_code} - {resp.text}")
        return []

def main():
    parser = argparse.ArgumentParser(description="Popula o Qdrant com dados dos Deputados para RAG")
    parser.add_argument("--limit", type=int, default=10, help="Limitar número de deputados processados")
    args = parser.parse_args()

    # 1. Garantir Load Inteligente no LocalAI
    localai_manager.ensure_model_loaded(EMBEDDER_MODEL)

    # 2. Conectar e preparar Qdrant
    client = QdrantClient(url=QDRANT_URL)
    ensure_collection(client, COLLECTION_NAME, VECTOR_SIZE)

    # 3. Buscar Deputados para indexar
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT deputado_id, nome FROM parlamentares_dados ORDER BY deputado_id LIMIT %s", (args.limit,))
        deputados = cur.fetchall()

    log.info(f"Processando {len(deputados)} deputados...")

    point_id = 1
    for deputado_id, nome in deputados:
        docs = get_deputado_texts(deputado_id)
        if not docs:
            continue
            
        log.info(f"Deputado {nome} ({deputado_id}): {len(docs)} documentos para embeddar.")
        
        points = []
        for doc in docs:
            vector = embed_text(doc["text"])
            if vector and len(vector) == VECTOR_SIZE:
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload=doc
                    )
                )
                point_id += 1
                
        if points:
            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )
            log.info(f"  -> Inseridos {len(points)} vetores no Qdrant.")

if __name__ == "__main__":
    main()
