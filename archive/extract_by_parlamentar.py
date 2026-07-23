#!/usr/bin/env python3
"""
Script para extrair TODOS os dados de Transferências Especiais (Emendas Pix)
e organizar por PARLAMENTAR para análise de gastos por político.

API: https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao_especial
Total: ~57.827 registros | 175 parlamentares | Anos 2020-2025
"""

import os
import sys
import logging
import time
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extract_by_parlamentar.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TransfereGovParlamentarExtractor:
    """Extrator de dados organizados por parlamentar."""
    
    BASE_URL = "https://api.transferegov.gestao.gov.br/transferenciasespeciais"
    ENDPOINT = "/plano_acao_especial"
    
    # Todos os campos da API
    ALL_FIELDS = [
        'id_plano_acao',
        'codigo_plano_acao',
        'ano_plano_acao',
        'modalidade_plano_acao',
        'situacao_plano_acao',
        'motivo_impedimento_plano_acao',
        'cnpj_beneficiario_plano_acao',
        'nome_beneficiario_plano_acao',
        'uf_beneficiario_plano_acao',
        'codigo_banco_plano_acao',
        'nome_banco_plano_acao',
        'numero_agencia_plano_acao',
        'dv_agencia_plano_acao',
        'numero_conta_plano_acao',
        'dv_conta_plano_acao',
        'nome_parlamentar_emenda_plano_acao',
        'ano_emenda_parlamentar_plano_acao',
        'codigo_parlamentar_emenda_plano_acao',
        'sequencial_emenda_parlamentar_plano_acao',
        'numero_emenda_parlamentar_plano_acao',
        'codigo_emenda_parlamentar_formatado_plano_acao',
        'codigo_descricao_areas_politicas_publicas_plano_acao',
        'descricao_programacao_orcamentaria_plano_acao',
        'valor_custeio_plano_acao',
        'valor_investimento_plano_acao',
        'id_programa',
    ]
    
    # Mapeamento para nomes amigáveis
    COLUMN_MAPPING = {
        'id_plano_acao': 'id_plano',
        'codigo_plano_acao': 'codigo_plano',
        'ano_plano_acao': 'ano_exercicio',
        'modalidade_plano_acao': 'modalidade',
        'situacao_plano_acao': 'situacao',
        'motivo_impedimento_plano_acao': 'motivo_impedimento',
        'cnpj_beneficiario_plano_acao': 'cnpj_municipio',
        'nome_beneficiario_plano_acao': 'municipio',
        'uf_beneficiario_plano_acao': 'uf',
        'codigo_banco_plano_acao': 'codigo_banco',
        'nome_banco_plano_acao': 'banco',
        'numero_agencia_plano_acao': 'agencia',
        'dv_agencia_plano_acao': 'dv_agencia',
        'numero_conta_plano_acao': 'conta',
        'dv_conta_plano_acao': 'dv_conta',
        'nome_parlamentar_emenda_plano_acao': 'parlamentar',
        'ano_emenda_parlamentar_plano_acao': 'ano_emenda',
        'codigo_parlamentar_emenda_plano_acao': 'codigo_parlamentar',
        'sequencial_emenda_parlamentar_plano_acao': 'sequencial_emenda',
        'numero_emenda_parlamentar_plano_acao': 'numero_emenda',
        'codigo_emenda_parlamentar_formatado_plano_acao': 'emenda_formatada',
        'codigo_descricao_areas_politicas_publicas_plano_acao': 'areas_publicas',
        'descricao_programacao_orcamentaria_plano_acao': 'descricao_acao',
        'valor_custeio_plano_acao': 'valor_custeio',
        'valor_investimento_plano_acao': 'valor_investimento',
        'id_programa': 'id_programa',
    }
    
    def __init__(self, 
                 timeout: int = 120,
                 max_retries: int = 3,
                 retry_delay: float = 2.0,
                 page_size: int = 500):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.page_size = min(page_size, 1000)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'TransfereGov-Parlamentar-Extractor/1.0'
        })
    
    def _make_request(self, params: Dict[str, str], offset: int = 0) -> Optional[requests.Response]:
        """Faz requisição com retry e paginação via offset/limit."""
        # Copiar params e adicionar offset
        request_params = params.copy()
        request_params['offset'] = str(offset)
        request_params['limit'] = str(self.page_size)
        
        for attempt in range(self.max_retries):
            try:
                response = self.session.get(
                    f"{self.BASE_URL}{self.ENDPOINT}",
                    params=request_params,
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limit. Aguardando {wait}s...")
                    time.sleep(wait)
                    continue
                elif response.status_code >= 500:
                    wait = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Erro servidor ({response.status_code}). Retry em {wait}s...")
                    time.sleep(wait)
                    continue
                else:
                    logger.error(f"HTTP {response.status_code}: {response.text[:300]}")
                    return None
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout (tentativa {attempt + 1}/{self.max_retries})")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Erro conexão (tentativa {attempt + 1}/{self.max_retries})")
            except requests.exceptions.RequestException as e:
                logger.error(f"Erro requisição: {e}")
                break
            
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (2 ** attempt))
        
        return None
    
    def _get_total_count(self, response: requests.Response) -> int:
        """Extrai total do header Content-Range (se disponível) ou estima."""
        cr = response.headers.get('Content-Range', '')
        try:
            if '/' in cr:
                return int(cr.split('/')[-1])
        except (ValueError, IndexError):
            pass
        return 0
    
    def extract_all(self, 
                    ano: Optional[int] = None,
                    parlamentar: Optional[str] = None,
                    uf: Optional[str] = None,
                    max_records: Optional[int] = None) -> pd.DataFrame:
        """
        Extrai todos os registros com filtros opcionais.
        
        Args:
            ano: Filtrar por ano do exercício
            parlamentar: Filtrar por nome do parlamentar (busca parcial)
            uf: Filtrar por UF
            max_records: Limite máximo de registros
        """
        params = {
            'select': ','.join(self.ALL_FIELDS),
            'order': 'nome_parlamentar_emenda_plano_acao.asc,ano_plano_acao.desc,uf_beneficiario_plano_acao.asc',
            'limit': str(self.page_size)
        }
        
        if ano:
            params['ano_plano_acao'] = f'eq.{ano}'
        if parlamentar:
            params['nome_parlamentar_emenda_plano_acao'] = f'ilike.*{parlamentar}*'
        if uf:
            params['uf_beneficiario_plano_acao'] = f'eq.{uf}'
        
        logger.info(f"Iniciando extração: ano={ano}, parlamentar={parlamentar}, uf={uf}")
        
        all_records = []
        range_start = 0
        total_count = None
        consecutive_empty = 0
        
        while True:
            # Verificar limite máximo
            if max_records and len(all_records) >= max_records:
                logger.info(f"Limite de {max_records} registros atingido.")
                break
            
            # Verificar se já atingimos o total conhecido
            if total_count and len(all_records) >= total_count:
                logger.info(f"Total de {total_count} registros atingido.")
                break
            
            current_page_size = self.page_size
            if max_records:
                remaining = max_records - len(all_records)
                current_page_size = min(self.page_size, remaining)
            
            response = self._make_request(params, range_start)
            
            if response is None:
                logger.error("Falha na requisição após todas as tentativas")
                break
            
            if total_count is None:
                total_count = self._get_total_count(response)
                logger.info(f"Total estimado: {total_count} registros")
            
            data = response.json()
            if not data:
                consecutive_empty += 1
                logger.info(f"Página vazia ({consecutive_empty}/3).")
                if consecutive_empty >= 3:
                    logger.info("3 páginas vazias consecutivas. Fim da paginação.")
                    break
            else:
                consecutive_empty = 0
                all_records.extend(data)
                logger.info(f"Registros: {len(all_records)}/{total_count if total_count else '?'}")
            
            # Verificar se é a última página
            if len(data) < current_page_size:
                logger.info("Última página alcançada (registros < page_size).")
                break
            
            range_start += current_page_size
            time.sleep(0.05)  # Pequeno delay
        
        if not all_records:
            logger.warning("Nenhum registro encontrado")
            return pd.DataFrame(columns=list(self.COLUMN_MAPPING.values()) + ['valor_total'])
        
        # Criar DataFrame
        df = pd.DataFrame(all_records)
        df = df.rename(columns=self.COLUMN_MAPPING)
        
        # Calcular valor total
        for col in ['valor_investimento', 'valor_custeio']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['valor_total'] = df['valor_investimento'].fillna(0) + df['valor_custeio'].fillna(0)
        
        # Ordenar
        df = df.sort_values(['parlamentar', 'ano_exercicio', 'municipio'], 
                           ascending=[True, False, True]).reset_index(drop=True)
        
        logger.info(f"Extração concluída: {len(df)} registros únicos")
        return df
    
    def create_parlamentar_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cria resumo agregado por parlamentar."""
        if df.empty:
            return pd.DataFrame()
        
        # Agregações
        summary = df.groupby('parlamentar').agg(
            total_registros=('id_plano', 'count'),
            municipios_unicos=('municipio', 'nunique'),
            ufs=('uf', lambda x: ', '.join(sorted(x.dropna().unique()))),
            anos=('ano_exercicio', lambda x: ', '.join(map(str, sorted(x.dropna().unique())))),
            valor_total_investimento=('valor_investimento', 'sum'),
            valor_total_custeio=('valor_custeio', 'sum'),
            valor_total=('valor_total', 'sum'),
            media_por_registro=('valor_total', 'mean'),
            maior_valor=('valor_total', 'max'),
            menor_valor=('valor_total', 'min'),
            situacoes=('situacao', lambda x: x.value_counts().to_dict()),
            bancos=('banco', lambda x: ', '.join(sorted(x.dropna().unique()))),
        ).reset_index()
        
        # Formatar valores
        for col in ['valor_total_investimento', 'valor_total_custeio', 'valor_total', 
                    'media_por_registro', 'maior_valor', 'menor_valor']:
            summary[col] = summary[col].round(2)
        
        # Ordenar por valor total decrescente
        summary = summary.sort_values('valor_total', ascending=False).reset_index(drop=True)
        summary.insert(0, 'ranking', range(1, len(summary) + 1))
        
        return summary
    
    def create_municipio_breakdown(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cria detalhamento por município dentro de cada parlamentar."""
        if df.empty:
            return pd.DataFrame()
        
        breakdown = df.groupby(['parlamentar', 'municipio', 'uf', 'ano_exercicio']).agg(
            qtd_registros=('id_plano', 'count'),
            valor_investimento=('valor_investimento', 'sum'),
            valor_custeio=('valor_custeio', 'sum'),
            valor_total=('valor_total', 'sum'),
            areas_publicas=('areas_publicas', lambda x: '; '.join(x.dropna().unique()[:3])),
            descricoes=('descricao_acao', lambda x: '; '.join(x.dropna().unique()[:3])),
        ).reset_index()
        
        for col in ['valor_investimento', 'valor_custeio', 'valor_total']:
            breakdown[col] = breakdown[col].round(2)
        
        breakdown = breakdown.sort_values(['parlamentar', 'valor_total'], 
                                         ascending=[True, False]).reset_index(drop=True)
        return breakdown
    
    def create_emenda_breakdown(self, df: pd.DataFrame) -> pd.DataFrame:
        """Cria detalhamento por emenda parlamentar."""
        if df.empty:
            return pd.DataFrame()
        
        # Filtrar apenas onde tem emenda
        df_emenda = df[df['emenda_formatada'].notna() & (df['emenda_formatada'] != '')].copy()
        
        if df_emenda.empty:
            return pd.DataFrame()
        
        breakdown = df_emenda.groupby(['parlamentar', 'emenda_formatada', 'ano_emenda']).agg(
            qtd_registros=('id_plano', 'count'),
            municipios=('municipio', lambda x: ', '.join(sorted(x.dropna().unique()))),
            ufs=('uf', lambda x: ', '.join(sorted(x.dropna().unique()))),
            valor_investimento=('valor_investimento', 'sum'),
            valor_custeio=('valor_custeio', 'sum'),
            valor_total=('valor_total', 'sum'),
        ).reset_index()
        
        for col in ['valor_investimento', 'valor_custeio', 'valor_total']:
            breakdown[col] = breakdown[col].round(2)
        
        breakdown = breakdown.sort_values(['parlamentar', 'valor_total'], 
                                         ascending=[True, False]).reset_index(drop=True)
        return breakdown
    
    def export_to_excel(self, df: pd.DataFrame, filepath: str) -> bool:
        """Exporta para Excel com múltiplas abas organizadas."""
        try:
            logger.info(f"Gerando Excel: {filepath}")
            
            # Criar resumos
            summary = self.create_parlamentar_summary(df)
            municipio_breakdown = self.create_municipio_breakdown(df)
            emenda_breakdown = self.create_emenda_breakdown(df)
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Aba 1: Resumo por Parlamentar
                summary.to_excel(writer, index=False, sheet_name='Resumo_Parlamentares')
                self._format_sheet(writer.sheets['Resumo_Parlamentares'], summary)
                
                # Aba 2: Detalhamento por Município
                municipio_breakdown.to_excel(writer, index=False, sheet_name='Por_Municipio')
                self._format_sheet(writer.sheets['Por_Municipio'], municipio_breakdown)
                
                # Aba 3: Detalhamento por Emenda
                if not emenda_breakdown.empty:
                    emenda_breakdown.to_excel(writer, index=False, sheet_name='Por_Emenda')
                    self._format_sheet(writer.sheets['Por_Emenda'], emenda_breakdown)
                
                # Aba 4: Dados Completos (opcional - pode ser grande)
                # Comentado por padrão para não criar arquivo enorme
                # df.to_excel(writer, index=False, sheet_name='Dados_Completos')
                # self._format_sheet(writer.sheets['Dados_Completos'], df)
                
                # Aba 5: Estatísticas Gerais
                stats = self._create_general_stats(df, summary)
                stats.to_excel(writer, index=False, sheet_name='Estatisticas_Gerais')
                self._format_sheet(writer.sheets['Estatisticas_Gerais'], stats)
            
            logger.info(f"Excel salvo com sucesso: {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao exportar Excel: {e}")
            return False
    
    def _format_sheet(self, worksheet, df: pd.DataFrame):
        """Formata colunas do Excel."""
        for idx, col in enumerate(df.columns):
            try:
                col_data = df[col].astype(str).replace({'nan': '', 'None': '', '<NA>': ''})
                max_len = max(col_data.map(len).max() if len(df) > 0 else 0, len(str(col))) + 2
            except Exception:
                max_len = len(str(col)) + 2
            
            if idx < 26:
                col_letter = chr(65 + idx)
            else:
                col_letter = chr(64 + idx // 26) + chr(65 + idx % 26)
            
            worksheet.column_dimensions[col_letter].width = min(max_len, 60)
    
    def _create_general_stats(self, df: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
        """Cria estatísticas gerais."""
        stats = []
        
        stats.append({'Metrica': 'Total de Registros', 'Valor': len(df)})
        stats.append({'Metrica': 'Total de Parlamentares', 'Valor': df['parlamentar'].nunique()})
        stats.append({'Metrica': 'Total de Municípios', 'Valor': df['municipio'].nunique()})
        stats.append({'Metrica': 'Total de UFs', 'Valor': df['uf'].nunique()})
        stats.append({'Metrica': 'Anos Cobertos', 'Valor': ', '.join(map(str, sorted(df['ano_exercicio'].dropna().unique())))})
        
        total_inv = df['valor_investimento'].sum()
        total_cus = df['valor_custeio'].sum()
        total_all = df['valor_total'].sum()
        
        stats.append({'Metrica': 'Valor Total Investimento', 'Valor': f"R$ {total_inv:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')})
        stats.append({'Metrica': 'Valor Total Custeio', 'Valor': f"R$ {total_cus:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')})
        stats.append({'Metrica': 'Valor Total Geral', 'Valor': f"R$ {total_all:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')})
        
        stats.append({'Metrica': 'Parlamentar com Maior Valor', 'Valor': f"{summary.iloc[0]['parlamentar']} (R$ {summary.iloc[0]['valor_total']:,.2f})".replace(',', 'X').replace('.', ',').replace('X', '.')})
        stats.append({'Metrica': 'Parlamentar com Mais Registros', 'Valor': f"{summary.loc[summary['total_registros'].idxmax(), 'parlamentar']} ({summary['total_registros'].max()} registros)"})
        stats.append({'Metrica': 'Parlamentar com Mais Municípios', 'Valor': f"{summary.loc[summary['municipios_unicos'].idxmax(), 'parlamentar']} ({summary['municipios_unicos'].max()} municípios)"})
        
        # Top 10
        top10 = summary.head(10)[['parlamentar', 'valor_total', 'total_registros', 'municipios_unicos']].copy()
        top10['valor_total'] = top10['valor_total'].apply(lambda x: f"R$ {x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        stats.append({'Metrica': 'TOP 10 Parlamentares', 'Valor': ''})
        for _, row in top10.iterrows():
            stats.append({'Metrica': f"  {row['parlamentar']}", 'Valor': f"Total: {row['valor_total']} | Registros: {row['total_registros']} | Municípios: {row['municipios_unicos']}"})
        
        return pd.DataFrame(stats)
    
    def export_to_csv(self, df: pd.DataFrame, filepath: str, sep: str = ';') -> bool:
        """Exporta para CSV."""
        try:
            df.to_csv(filepath, index=False, sep=sep, encoding='utf-8-sig')
            logger.info(f"CSV salvo: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Erro ao exportar CSV: {e}")
            return False
    
    def print_summary(self, df: pd.DataFrame):
        """Imprime resumo no console."""
        if df.empty:
            print("Nenhum dado para resumo.")
            return
        
        summary = self.create_parlamentar_summary(df)
        
        print("\n" + "="*80)
        print("RESUMO POR PARLAMENTAR - Transferências Especiais (Emendas Pix)")
        print("="*80)
        print(f"Total de registros: {len(df):,}")
        print(f"Total de parlamentares: {df['parlamentar'].nunique()}")
        print(f"Total de municípios: {df['municipio'].nunique()}")
        print(f"Anos: {sorted(df['ano_exercicio'].dropna().unique())}")
        print(f"Valor total: R$ {df['valor_total'].sum():,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        print(f"  - Investimento: R$ {df['valor_investimento'].sum():,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        print(f"  - Custeio: R$ {df['valor_custeio'].sum():,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        print("-"*80)
        print(f"{'Rank':>4} | {'Parlamentar':<30} | {'Total (R$)':>15} | {'Registros':>8} | {'Municípios':>10} | {'Anos'}")
        print("-"*80)
        for _, row in summary.head(20).iterrows():
            print(f"{row['ranking']:>4} | {row['parlamentar']:<30} | {row['valor_total']:>15,.2f} | {row['total_registros']:>8} | {row['municipios_unicos']:>10} | {row['anos']}")
        print("="*80 + "\n")


def main():
    """Função principal."""
    # Configurações
    # ANO = 2025  # Descomente para filtrar ano específico
    ANO = None  # None = todos os anos
    PARLAMENTAR = None  # None = todos, ou nome parcial ex: "Bacelar"
    UF = None  # None = todas, ou "SP", "RJ", etc.
    MAX_RECORDS = None  # None = sem limite
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filtros = []
    if ANO: filtros.append(f"ano{ANO}")
    if PARLAMENTAR: filtros.append(f"parl_{PARLAMENTAR.replace(' ', '_')}")
    if UF: filtros.append(f"uf{UF}")
    filtro_str = "_".join(filtros) if filtros else "todos"
    
    output_excel = f'transferencias_especiais_por_parlamentar_{filtro_str}_{timestamp}.xlsx'
    output_csv = f'transferencias_especiais_por_parlamentar_{filtro_str}_{timestamp}.csv'
    
    logger.info("="*70)
    logger.info("EXTRAÇÃO TRANSFEREGOV - ORGANIZADO POR PARLAMENTAR")
    logger.info("="*70)
    logger.info(f"Filtros: ano={ANO}, parlamentar={PARLAMENTAR}, uf={UF}")
    
    extractor = TransfereGovParlamentarExtractor(
        timeout=120,
        max_retries=3,
        retry_delay=2.0,
        page_size=500
    )
    
    try:
        df = extractor.extract_all(
            ano=ANO,
            parlamentar=PARLAMENTAR,
            uf=UF,
            max_records=MAX_RECORDS
        )
        
        if df.empty:
            logger.warning("Nenhum registro encontrado")
            return 1
        
        extractor.print_summary(df)
        
        # Exportar
        success_excel = extractor.export_to_excel(df, output_excel)
        success_csv = extractor.export_to_csv(df, output_csv)
        
        if success_excel or success_csv:
            logger.info("Extração concluída com sucesso!")
            logger.info(f"Arquivos: {output_excel}, {output_csv}")
            return 0
        else:
            logger.error("Falha na exportação")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário")
        return 130
    except Exception as e:
        logger.exception(f"Erro inesperado: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())