#!/usr/bin/env python3
"""
Script para extrair dados de Transferências Especiais (Emendas Pix) 
destinadas a construção/reforma de cemitérios.

API Base: https://api.transferegov.gestao.gov.br/transferenciasespeciais/
Endpoint: /plano_acao_especial

Campos de busca:
- descricao_programacao_orcamentaria_plano_acao: contém descrição das ações (busca por "cemitério", "cemiterio", etc.)
- ano_plano_acao: ano do exercício

NOTA IMPORTANTE: A API atualmente tem dados até 2025. Dados de 2026 ainda não estão disponíveis.
Registros de cemitérios só existem para 2021-2023.
"""

import os
import sys
import logging
import time
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extract_cemiterios.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TransfereGovCemeteryExtractor:
    """Extrator de dados de Transferências Especiais para cemitérios."""
    
    BASE_URL = "https://api.transferegov.gestao.gov.br/transferenciasespeciais"
    ENDPOINT = "/plano_acao_especial"
    
    # Termos de busca para cemitérios (testados e funcionando na API)
    CEMETERY_SEARCH_TERMS = [
        'cemitério',
        'cemiterio', 
        'cemitérios',
        'cemiterios',
        'cemiterio publico',
        'cemiterio municipal',
        'cemitério público',
        'cemitério municipal'
    ]
    
    # Mapeamento de colunas da API para nomes amigáveis
    COLUMN_MAPPING = {
        'id_plano_acao': 'id_plano',
        'codigo_plano_acao': 'codigo_plano',
        'ano_plano_acao': 'ano_exercicio',
        'modalidade_plano_acao': 'modalidade',
        'situacao_plano_acao': 'situacao_plano',
        'cnpj_beneficiario_plano_acao': 'cnpj_municipio',
        'nome_beneficiario_plano_acao': 'nome_municipio',
        'uf_beneficiario_plano_acao': 'uf',
        'codigo_banco_plano_acao': 'codigo_banco',
        'nome_banco_plano_acao': 'nome_banco',
        'numero_agencia_plano_acao': 'numero_agencia',
        'dv_agencia_plano_acao': 'dv_agencia',
        'numero_conta_plano_acao': 'numero_conta',
        'dv_conta_plano_acao': 'dv_conta',
        'nome_parlamentar_emenda_plano_acao': 'parlamentar',
        'ano_emenda_parlamentar_plano_acao': 'ano_emenda',
        'codigo_parlamentar_emenda_plano_acao': 'codigo_parlamentar',
        'sequencial_emenda_parlamentar_plano_acao': 'sequencial_emenda',
        'numero_emenda_parlamentar_plano_acao': 'numero_emenda',
        'codigo_emenda_parlamentar_formatado_plano_acao': 'codigo_emenda_formatado',
        'codigo_descricao_areas_politicas_publicas_plano_acao': 'areas_politicas_publicas',
        'descricao_programacao_orcamentaria_plano_acao': 'descricao_acao',
        'motivo_impedimento_plano_acao': 'motivo_impedimento',
        'valor_custeio_plano_acao': 'valor_custeio',
        'valor_investimento_plano_acao': 'valor_investimento',
        'id_programa': 'id_programa',
    }
    
    # Colunas finais para exportação (ordem desejada)
    EXPORT_COLUMNS = [
        'id_plano',
        'codigo_plano',
        'ano_exercicio',
        'nome_municipio',
        'uf',
        'cnpj_municipio',
        'valor_investimento',
        'valor_custeio',
        'valor_total_repasse',
        'descricao_acao',
        'areas_politicas_publicas',
        'parlamentar',
        'codigo_emenda_formatado',
        'ano_emenda',
        'situacao_plano',
        'modalidade',
        'nome_banco',
        'codigo_banco',
        'numero_agencia',
        'dv_agencia',
        'numero_conta',
        'dv_conta',
        'motivo_impedimento',
        'id_programa',
    ]
    
    def __init__(self, 
                 base_url: str = None,
                 timeout: int = 60,
                 max_retries: int = 3,
                 retry_delay: float = 2.0,
                 page_size: int = 100):
        """
        Inicializa o extrator.
        
        Args:
            base_url: URL base da API (opcional)
            timeout: Timeout em segundos para requisições HTTP
            max_retries: Número máximo de tentativas em caso de falha
            retry_delay: Delay inicial entre tentativas (exponential backoff)
            page_size: Tamanho da página para paginação (máx 1000 na API)
        """
        self.base_url = base_url or self.BASE_URL
        self.endpoint = self.ENDPOINT
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.page_size = min(page_size, 1000)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'TransfereGov-Cemetery-Extractor/1.0'
        })
        
    def _build_filter_params(self, 
                            ano: int = None,
                            search_term: str = None) -> Dict[str, str]:
        """
        Constrói os parâmetros de filtro usando sintaxe PostgREST.
        
        Args:
            ano: Ano do exercício (opcional)
            search_term: Termo para busca textual em descricao_programacao_orcamentaria_plano_acao
            
        Returns:
            Dicionário com parâmetros de query
        """
        params = {
            'select': ','.join(self.COLUMN_MAPPING.keys()),
            'order': 'uf_beneficiario_plano_acao.asc,nome_beneficiario_plano_acao.asc,id_plano_acao.asc',
            'limit': str(self.page_size)
        }
        
        if ano:
            params['ano_plano_acao'] = f'eq.{ano}'
            
        if search_term:
            # Usar ilike para busca case-insensitive
            params['descricao_programacao_orcamentaria_plano_acao'] = f'ilike.*{search_term}*'
        
        return params
    
    def _make_request(self, url: str, params: Dict[str, str], 
                     range_start: int = 0) -> Optional[requests.Response]:
        """
        Faz requisição HTTP com retry e paginação via header Range.
        
        Args:
            url: URL completa do endpoint
            params: Parâmetros de query
            range_start: Início do range para paginação
            
        Returns:
            Response object ou None se falhar
        """
        headers = {
            'Range': f'items={range_start}-{range_start + self.page_size - 1}',
            'Prefer': 'count=exact'
        }
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Requisição: GET {url} | Params: {params} | Range: {headers['Range']}")
                
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout
                )
                
                if response.status_code in (200, 206):
                    return response
                elif response.status_code == 429:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limit atingido. Aguardando {wait_time}s antes de retry...")
                    time.sleep(wait_time)
                    continue
                elif response.status_code >= 500:
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Erro do servidor ({response.status_code}). Retry em {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Erro HTTP {response.status_code}: {response.text[:500]}")
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout na requisição (tentativa {attempt + 1}/{self.max_retries})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Erro de conexão (tentativa {attempt + 1}/{self.max_retries})")
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro na requisição: {e}")
                break
                
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (2 ** attempt))
        
        return None
    
    def _parse_response(self, response: requests.Response) -> List[Dict[str, Any]]:
        """Processa a resposta da API e retorna lista de registros."""
        try:
            data = response.json()
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'data' in data:
                return data['data']
            else:
                logger.warning(f"Formato de resposta inesperado: {type(data)}")
                return []
        except ValueError as e:
            logger.error(f"Erro ao parsear JSON: {e}")
            return []
    
    def _get_total_count(self, response: requests.Response) -> int:
        """Extrai o total de registros do header Content-Range."""
        content_range = response.headers.get('Content-Range', '')
        try:
            if '/' in content_range:
                total = content_range.split('/')[-1]
                return int(total)
        except (ValueError, IndexError):
            pass
        return 0
    
    def extract(self, 
                ano: int = None,
                search_terms: List[str] = None,
                max_records: Optional[int] = None) -> pd.DataFrame:
        """
        Extrai todos os registros de planos de ação para cemitérios.
        
        Args:
            ano: Ano do exercício (None = todos os anos)
            search_terms: Lista de termos para busca textual
            max_records: Limite máximo de registros (None = sem limite)
            
        Returns:
            DataFrame com os dados extraídos
        """
        if search_terms is None:
            search_terms = self.CEMETERY_SEARCH_TERMS
        
        url = f"{self.base_url}{self.endpoint}"
        
        logger.info(f"Iniciando extração: {url}")
        logger.info(f"Filtros: ano={ano if ano else 'todos'}, termos={len(search_terms)} termos de busca")
        
        all_records = []
        seen_ids = set()  # Para evitar duplicatas entre termos de busca
        
        for term_idx, term in enumerate(search_terms):
            logger.info(f"Buscando termo {term_idx + 1}/{len(search_terms)}: '{term}'")
            
            params = self._build_filter_params(ano=ano, search_term=term)
            range_start = 0
            total_count = None
            term_records = 0
            
            while True:
                if max_records and len(all_records) >= max_records:
                    logger.info(f"Limite de {max_records} registros atingido.")
                    break
                
                current_page_size = self.page_size
                if max_records:
                    remaining = max_records - len(all_records)
                    current_page_size = min(self.page_size, remaining)
                
                response = self._make_request(url, params, range_start)
                
                if response is None:
                    logger.error(f"Falha na requisição para termo '{term}' após todas as tentativas.")
                    break
                
                if total_count is None:
                    total_count = self._get_total_count(response)
                    logger.info(f"  Total estimado para '{term}': {total_count} registros")
                
                records = self._parse_response(response)
                
                if not records:
                    logger.info(f"  Nenhum registro retornado. Fim da paginação para '{term}'.")
                    break
                
                # Filtrar duplicatas por id_plano_acao
                new_records = []
                for r in records:
                    pid = r.get('id_plano_acao')
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        new_records.append(r)
                
                all_records.extend(new_records)
                term_records += len(new_records)
                logger.info(f"  Registros novos: {len(new_records)} (total acumulado: {len(all_records)})")
                
                if len(records) < current_page_size:
                    logger.info(f"  Última página alcançada para '{term}'.")
                    break
                
                range_start += current_page_size
                time.sleep(0.1)  # Pequeno delay para não sobrecarregar a API
            
            logger.info(f"Termo '{term}': {term_records} registros únicos encontrados")
        
        # Criar DataFrame
        if all_records:
            df = pd.DataFrame(all_records)
            
            # Renomear colunas
            df = df.rename(columns=self.COLUMN_MAPPING)
            
            # Garantir que todas as colunas de exportação existam
            for col in self.EXPORT_COLUMNS:
                if col not in df.columns:
                    df[col] = None
            
            # Reordenar colunas
            df = df[self.EXPORT_COLUMNS]
            
            # Converter valores numéricos
            for col in ['valor_investimento', 'valor_custeio']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Calcular valor total de repasse
            df['valor_total_repasse'] = df['valor_investimento'].fillna(0) + df['valor_custeio'].fillna(0)
            
            logger.info(f"Extração concluída. Total de registros únicos: {len(df)}")
            return df
        else:
            logger.warning("Nenhum registro encontrado.")
            return pd.DataFrame(columns=self.EXPORT_COLUMNS)
    
    def export_to_excel(self, df: pd.DataFrame, filepath: str) -> bool:
        """Exporta DataFrame para Excel com formatação."""
        try:
            # Convert numpy types to native Python types for Excel compatibility
            df_export = df.copy()
            for col in df_export.columns:
                if df_export[col].dtype == 'object':
                    df_export[col] = df_export[col].apply(
                        lambda x: x.item() if hasattr(x, 'item') else x
                    )
                elif 'int' in str(df_export[col].dtype):
                    df_export[col] = df_export[col].astype('Int64')
                elif 'float' in str(df_export[col].dtype):
                    df_export[col] = df_export[col].astype('float64')
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                df_export.to_excel(writer, index=False, sheet_name='Cemiterios')
                
                worksheet = writer.sheets['Cemiterios']
                for idx, col in enumerate(df_export.columns):
                    # Calculate column width safely - convert all to string first
                    try:
                        col_str = df_export[col].astype(str)
                        col_str = col_str.replace({'nan': '', 'None': '', '<NA>': '', 'NaN': ''})
                        max_len = max(
                            col_str.map(len).max() if len(df_export) > 0 else 0,
                            len(str(col))
                        ) + 2
                    except Exception:
                        max_len = len(str(col)) + 2
                    
                    # Handle column letters beyond Z
                    if idx < 26:
                        col_letter = chr(65 + idx)
                    else:
                        col_letter = chr(64 + idx // 26) + chr(65 + idx % 26)
                    worksheet.column_dimensions[col_letter].width = min(max_len, 60)
            
            logger.info(f"Arquivo Excel salvo: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Erro ao exportar Excel: {e}")
            return False
    
    def export_to_csv(self, df: pd.DataFrame, filepath: str, sep: str = ';') -> bool:
        """Exporta DataFrame para CSV."""
        try:
            df.to_csv(filepath, index=False, sep=sep, encoding='utf-8-sig')
            logger.info(f"Arquivo CSV salvo: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Erro ao exportar CSV: {e}")
            return False
    
    def print_summary(self, df: pd.DataFrame) -> None:
        """Imprime resumo dos dados extraídos."""
        if df.empty:
            logger.info("Nenhum dado para resumo.")
            return
        
        print("\n" + "="*70)
        print("RESUMO DA EXTRAÇÃO - CEMITÉRIOS (Transferências Especiais)")
        print("="*70)
        print(f"Total de registros: {len(df)}")
        print(f"Municípios únicos: {df['nome_municipio'].nunique()}")
        print(f"Estados (UFs): {sorted(df['uf'].dropna().unique())}")
        print(f"Ano(s): {sorted(df['ano_exercicio'].dropna().unique())}")
        
        def fmt(val):
            return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        print(f"Valor total investimento: {fmt(df['valor_investimento'].sum())}")
        print(f"Valor total custeio: {fmt(df['valor_custeio'].sum())}")
        print(f"Valor total repasse: {fmt(df['valor_total_repasse'].sum())}")
        print(f"Situações: {df['situacao_plano'].value_counts().to_dict()}")
        print("="*70 + "\n")


def main():
    """Função principal."""
    # Configurações
    # ATENÇÃO: Dados de cemitérios só existem para 2021-2023.
    # 2024, 2025 e 2026 não têm registros de cemitérios ainda.
    # Use ANO = None para buscar todos os anos disponíveis.
    ANO = None  # None = todos os anos; ou especifique: 2023, 2022, 2021
    MAX_RECORDS = None  # None = sem limite
    
    # Arquivos de saída com timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ano_str = str(ANO) if ANO else 'todos_anos'
    output_excel = f'cemiterios_transferencias_especiais_{ano_str}_{timestamp}.xlsx'
    output_csv = f'cemiterios_transferencias_especiais_{ano_str}_{timestamp}.csv'
    
    logger.info("="*70)
    logger.info("INICIANDO EXTRAÇÃO - CEMITÉRIOS (Transferências Especiais)")
    logger.info("="*70)
    logger.info(f"NOTA: Dados de cemitérios disponíveis apenas para 2021-2023.")
    logger.info(f"      Ano solicitado: {ANO if ANO else 'Todos (padrão)'}")
    logger.info(f"      2024, 2025, 2026 não possuem registros de cemitérios ainda.")
    
    extractor = TransfereGovCemeteryExtractor(
        timeout=60,
        max_retries=3,
        retry_delay=2.0,
        page_size=100
    )
    
    try:
        df = extractor.extract(
            ano=ANO,
            search_terms=extractor.CEMETERY_SEARCH_TERMS,
            max_records=MAX_RECORDS
        )
        
        if df.empty:
            logger.warning("Nenhum registro encontrado para os critérios informados.")
            return 1
        
        extractor.print_summary(df)
        
        success_excel = extractor.export_to_excel(df, output_excel)
        success_csv = extractor.export_to_csv(df, output_csv)
        
        if success_excel or success_csv:
            logger.info("Extração concluída com sucesso!")
            logger.info(f"Arquivos gerados: {output_excel}, {output_csv}")
            return 0
        else:
            logger.error("Falha ao exportar arquivos.")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Extração interrompida pelo usuário.")
        return 130
    except Exception as e:
        logger.exception(f"Erro inesperado: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())