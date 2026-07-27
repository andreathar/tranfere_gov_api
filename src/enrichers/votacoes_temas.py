"""
Enriquecimento: Identificação de Temas de Votações via LLM.

Uso: python3 -m src.enrichers.votacoes_temas [--limit N]

Para cada votação na tabela `votacoes_camara` que ainda não possui um tema definido,
usa o modelo LLaMA (via LocalAI) para classificar o assunto da votação em um termo
ou categoria concisa (ex: "Saúde", "Orçamento", "Segurança Pública", "Direitos Humanos").
"""

import argparse
import logging
import time

from config.settings import LOCALAI_MODELS
from src.db_utils import get_connection
from src.localai_manager import manager as localai_manager
from src.localai_client import LocalAIClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

PROMPT_TEMPLATE = """
Você é um cientista político especializado no Congresso Brasileiro.
Sua tarefa é analisar a descrição e a ementa de uma votação da Câmara dos Deputados
e retornar APENAS O TEMA PRINCIPAL em 1 a 3 palavras.

Exemplos de temas:
- Economia e Orçamento
- Saúde
- Educação
- Segurança Pública
- Direitos Humanos
- Infraestrutura
- Meio Ambiente
- Política Externa
- Administração Pública
- Direitos Trabalhistas
- Homenagens e Honrarias

Votação:
Descrição: {descricao}
Ementa da Proposição: {ementa}

Qual é o tema principal? Retorne APENAS o tema, sem nenhuma outra palavra.
"""

def generate_theme(descricao: str, ementa: str) -> str:
    """Usa o LLaMA para classificar a votação."""
    llm_model = LOCALAI_MODELS["general"]
    localai_manager.ensure_model_loaded(llm_model)
    ai_client = LocalAIClient(model=llm_model)
    
    desc_safe = descricao or "Sem descrição"
    ementa_safe = ementa or "Sem ementa"
    prompt = PROMPT_TEMPLATE.format(descricao=desc_safe, ementa=ementa_safe)
    
    try:
        resposta = ai_client.chat(
            prompt=prompt,
            system="Você classifica votações políticas em um único termo sucinto. Nunca explique sua resposta.",
            temperature=0.1  # Baixa temperatura para respostas mais determinísticas e curtas
        )
        return resposta.strip()
    except Exception as e:
        log.error(f"Erro ao classificar tema: {e}")
        return "Erro de Classificação"

def main():
    parser = argparse.ArgumentParser(description="Classificar Temas de Votações via LLM")
    parser.add_argument("--limit", type=int, default=50, help="Limitar N votações por vez")
    args = parser.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT votacao_id, descricao, proposicao_ementa 
        FROM votacoes_camara 
        WHERE tema IS NULL
        LIMIT %s
    """, (args.limit,))
    
    votacoes = cur.fetchall()
    
    if not votacoes:
        log.info("Todas as votações já possuem tema.")
        return
        
    log.info(f"Classificando {len(votacoes)} votações...")
    
    total = 0
    for row in votacoes:
        vid, desc, ementa = row
        tema = generate_theme(desc, ementa)
        
        # O modelo pode retornar algo com aspas, vamos limpar um pouco
        tema_limpo = tema.replace('"', '').replace('*', '').split('\n')[0].strip()
        if len(tema_limpo) > 100:
            tema_limpo = tema_limpo[:97] + "..."
            
        log.info(f"Votação {vid} -> Tema: {tema_limpo}")
        
        cur.execute(
            "UPDATE votacoes_camara SET tema = %s WHERE votacao_id = %s",
            (tema_limpo, vid)
        )
        conn.commit()
        total += 1
        
    cur.close()
    conn.close()
    log.info(f"✅ Concluído! {total} votações atualizadas com temas.")

if __name__ == "__main__":
    main()
