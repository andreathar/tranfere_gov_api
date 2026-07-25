import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

# Add project root to path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from src.db_utils import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TRANSPARENCIA_API_URL = "https://api.portaldatransparencia.gov.br/api-de-dados/emendas"

def get_db_connection():
    return get_connection()

def fetch_emendas_transparencia(api_key: str, pagina: int = 1) -> list[dict[str, Any]]:
    """Busca emendas (Transferências Discricionárias) no Portal da Transparência."""
    headers = {
        "chave-api-dados": api_key,
        "Accept": "application/json"
    }
    params = {
        "pagina": pagina
    }

    logger.info(f"Buscando página {pagina} no Portal da Transparência...")
    response = httpx.get(TRANSPARENCIA_API_URL, headers=headers, params=params, timeout=30.0)

    if response.status_code == 401:
        logger.error("Erro 401: TRANSPARENCIA_API_KEY inválida ou não autorizada.")
        return []

    response.raise_for_status()
    return response.json()

def upsert_emendas_discricionarias(emendas: list[dict[str, Any]]) -> None:
    """Insere ou atualiza registros na tabela emendas_discricionarias."""
    if not emendas:
        return

    query = """
        INSERT INTO emendas_discricionarias (
            codigo_emenda, numero_convenio, ano, parlamentar_nome, 
            beneficiario_nome, beneficiario_cnpj, valor_total, 
            status_execucao, data_assinatura, objeto
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (codigo_emenda) DO UPDATE SET
            numero_convenio = EXCLUDED.numero_convenio,
            ano = EXCLUDED.ano,
            parlamentar_nome = EXCLUDED.parlamentar_nome,
            beneficiario_nome = EXCLUDED.beneficiario_nome,
            beneficiario_cnpj = EXCLUDED.beneficiario_cnpj,
            valor_total = EXCLUDED.valor_total,
            status_execucao = EXCLUDED.status_execucao,
            data_assinatura = EXCLUDED.data_assinatura,
            objeto = EXCLUDED.objeto,
            updated_at = NOW();
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for emenda in emendas:
                # O formato do response da API da Transparência pode variar,
                # aqui extraímos os campos baseando-se no padrão comum do portal.
                codigo_emenda = emenda.get("codigoEmenda")
                if not codigo_emenda:
                    continue

                # Para convênios, o Portal da Transparência retorna objetos compostos
                autor = emenda.get("autor", {})
                parlamentar_nome = autor.get("nomeAutor")

                beneficiario = emenda.get("beneficiario", {})
                beneficiario_nome = beneficiario.get("nome")
                beneficiario_cnpj = beneficiario.get("cnpjFormatado")

                valor_total = emenda.get("valorEmpenhado", 0.0)
                status = "DESCONHECIDO" # A API de emendas pura pode não ter o status do convênio diretamente

                cur.execute(query, (
                    codigo_emenda,
                    None, # numero_convenio
                    emenda.get("ano"),
                    parlamentar_nome,
                    beneficiario_nome,
                    beneficiario_cnpj,
                    valor_total,
                    status,
                    None, # data_assinatura
                    emenda.get("funcao", {}).get("nome") # Usando função como objeto
                ))
        conn.commit()
    logger.info(f"Foram inseridos/atualizados {len(emendas)} registros com sucesso no banco de dados.")

def main():
    api_key = os.getenv("TRANSPARENCIA_API_KEY")
    if not api_key:
        logger.error("A variável de ambiente 'TRANSPARENCIA_API_KEY' não está definida.")
        logger.info("Por favor, obtenha uma chave em: https://portaldatransparencia.gov.br/api-de-dados")
        logger.info("E exporte a variável executando: export TRANSPARENCIA_API_KEY='sua_chave_aqui'")
        sys.exit(1)

    pagina = 1
    while True:
        try:
            emendas = fetch_emendas_transparencia(api_key, pagina)
            if not emendas:
                break

            upsert_emendas_discricionarias(emendas)
            pagina += 1
            time.sleep(1) # Rate limit cortesia
        except Exception as e:
            logger.error(f"Erro ao processar página {pagina}: {e}")
            break

if __name__ == "__main__":
    main()
