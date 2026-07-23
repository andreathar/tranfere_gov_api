#!/usr/bin/env python3
"""
Extração COMPLETA e NORMALIZADA de Transferências Especiais (Emendas Pix)
com separação das áreas de políticas públicas em tabelas relacionais.

API: https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao_especial
Total: ~57.827 registros | 26 campos originais

Estrutura normalizada:
1. plano_acao (tabela principal) - 23 campos + chaves
2. area_politica_publica (dimensão) - códigos únicos de área/subárea
3. plano_acao_area (junção) - relacionamento N:N
4. emenda_parlamentar (dimensão) - dados da emenda
5. municipio (dimensão) - dados do município beneficiário
"""

import os
import sys
import logging
import time
import requests
import pandas as pd
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('extract_full_normalized.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class TransfereGovFullExtractor:
    """Extrator completo com normalização de áreas de políticas públicas."""
    
    BASE_URL = "https://api.transferegov.gestao.gov.br/transferenciasespeciais"
    ENDPOINT = "/plano_acao_especial"
    
    # TODOS os 26 campos da API
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
    
    def __init__(self, 
                 timeout: int = 120,
                 max_retries: int = 3,
                 retry_delay: float = 2.0,
                 page_size: int = 1000):
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.page_size = min(page_size, 1000)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json',
            'User-Agent': 'TransfereGov-Full-Extractor/1.0'
        })
        
        # Cache para normalização
        self._area_cache = {}
        self._emenda_cache = {}
        self._municipio_cache = {}
    
    def _make_request(self, params: Dict[str, str], offset: int = 0) -> Optional[requests.Response]:
        """Requisição com retry e paginação via offset/limit."""
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
        """Extrai total do header Content-Range."""
        cr = response.headers.get('Content-Range', '')
        try:
            if '/' in cr:
                return int(cr.split('/')[-1])
        except (ValueError, IndexError):
            pass
        return 0
    
    @staticmethod
    def parse_areas_publicas(areas_str: str) -> List[Dict[str, str]]:
        """
        Normaliza o campo codigo_descricao_areas_politicas_publicas_plano_acao.
        
        Formato: "15-Urbanismo / 451-Infraestrutura Urbana , 20-Agricultura / 605-Abastecimento"
        Retorna lista de dicts: [{'area_cod': '15', 'area_nome': 'Urbanismo', 'subarea_cod': '451', 'subarea_nome': 'Infraestrutura Urbana'}, ...]
        """
        if not areas_str or not areas_str.strip():
            return []
        
        results = []
        # Split por vírgula (separador de áreas)
        for area_part in areas_str.split(','):
            area_part = area_part.strip()
            if not area_part:
                continue
            
            # Split por " / " (separador área/subárea)
            if ' / ' in area_part:
                area_str, subarea_str = area_part.split(' / ', 1)
            else:
                area_str, subarea_str = area_part, ''
            
            # Parse área: "15-Urbanismo"
            area_match = re.match(r'^(\d+)-(.+)$', area_str.strip())
            if area_match:
                area_cod, area_nome = area_match.groups()
            else:
                area_cod, area_nome = '', area_str.strip()
            
            # Parse subárea: "451-Infraestrutura Urbana"
            subarea_cod, subarea_nome = '', ''
            if subarea_str:
                subarea_match = re.match(r'^(\d+)-(.+)$', subarea_str.strip())
                if subarea_match:
                    subarea_cod, subarea_nome = subarea_match.groups()
                else:
                    subarea_nome = subarea_str.strip()
            
            results.append({
                'area_codigo': area_cod,
                'area_nome': area_nome.strip(),
                'subarea_codigo': subarea_cod,
                'subarea_nome': subarea_nome.strip()
            })
        
        return results
    
    @staticmethod
    def extract_ibge_from_cnpj(cnpj: str) -> Optional[str]:
        """Extrai código IBGE (7 primeiros dígitos) do CNPJ do município."""
        if not cnpj:
            return None
        digits = re.sub(r'\D', '', cnpj)
        if len(digits) >= 8:
            return digits[:7]
        return None
    
    def extract_all(self, 
                    ano: Optional[int] = None,
                    parlamentar: Optional[str] = None,
                    uf: Optional[str] = None,
                    max_records: Optional[int] = None) -> Dict[str, pd.DataFrame]:
        """
        Extrai todos os registros e retorna dicionário com DataFrames normalizados.
        
        Returns:
            Dict com chaves:
            - 'plano_acao': tabela principal
            - 'areas': dimensão áreas políticas públicas
            - 'plano_acao_areas': junção N:N
            - 'emendas': dimensão emendas parlamentares
            - 'municipios': dimensão municípios
            - 'wide': tabela desnormalizada completa (para Excel)
        """
        params = {
            'select': ','.join(self.ALL_FIELDS),
            'order': 'nome_parlamentar_emenda_plano_acao.asc,ano_plano_acao.desc,uf_beneficiario_plano_acao.asc',
        }
        
        if ano:
            params['ano_plano_acao'] = f'eq.{ano}'
        if parlamentar:
            params['nome_parlamentar_emenda_plano_acao'] = f'ilike.*{parlamentar}*'
        if uf:
            params['uf_beneficiario_plano_acao'] = f'eq.{uf}'
        
        logger.info(f"Iniciando extração completa: ano={ano}, parlamentar={parlamentar}, uf={uf}")
        
        all_records = []
        offset = 0
        total_count = None
        consecutive_empty = 0
        
        while True:
            if max_records and len(all_records) >= max_records:
                logger.info(f"Limite de {max_records} registros atingido.")
                break
            
            current_page_size = self.page_size
            if max_records:
                remaining = max_records - len(all_records)
                current_page_size = min(self.page_size, remaining)
            
            response = self._make_request(params, offset)
            
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
            
            if len(data) < current_page_size:
                logger.info("Última página alcançada.")
                break
            
            offset += current_page_size
            time.sleep(0.03)
        
        if not all_records:
            logger.warning("Nenhum registro encontrado")
            return self._empty_result()
        
        logger.info(f"Extração bruta concluída: {len(all_records)} registros. Iniciando normalização...")
        
        # Normalizar
        return self._normalize(all_records)
    
    def _normalize(self, records: List[Dict]) -> Dict[str, pd.DataFrame]:
        """Normaliza registros em tabelas relacionais."""
        
        # 1. Tabela principal: plano_acao
        plano_rows = []
        plano_area_rows = []
        areas_dict = {}  # (area_cod, subarea_cod) -> {area_cod, area_nome, subarea_cod, subarea_nome}
        emendas_dict = {}  # codigo_emenda_formatado -> emenda data
        municipios_dict = {}  # cnpj -> municipio data
        
        for r in records:
            id_plano = r.get('id_plano_acao')
            
            # --- MUNICÍPIO ---
            cnpj = r.get('cnpj_beneficiario_plano_acao', '')
            ibge = self.extract_ibge_from_cnpj(cnpj)
            
            if cnpj not in municipios_dict:
                municipios_dict[cnpj] = {
                    'cnpj_municipio': cnpj,
                    'codigo_ibge': ibge,
                    'nome_municipio': r.get('nome_beneficiario_plano_acao', ''),
                    'uf': r.get('uf_beneficiario_plano_acao', ''),
                }
            
            # --- EMENDA ---
            emenda_fmt = r.get('codigo_emenda_parlamentar_formatado_plano_acao', '')
            if emenda_fmt and emenda_fmt not in emendas_dict:
                emendas_dict[emenda_fmt] = {
                    'codigo_emenda_formatado': emenda_fmt,
                    'numero_emenda': r.get('numero_emenda_parlamentar_plano_acao', ''),
                    'ano_emenda': r.get('ano_emenda_parlamentar_plano_acao', ''),
                    'codigo_parlamentar': r.get('codigo_parlamentar_emenda_plano_acao', ''),
                    'sequencial_emenda': r.get('sequencial_emenda_parlamentar_plano_acao', ''),
                    'nome_parlamentar': r.get('nome_parlamentar_emenda_plano_acao', ''),
                }
            
            # --- ÁREAS POLÍTICAS PÚBLICAS ---
            areas_str = r.get('codigo_descricao_areas_politicas_publicas_plano_acao', '')
            parsed_areas = self.parse_areas_publicas(areas_str)
            
            for area in parsed_areas:
                key = (area['area_codigo'], area['subarea_codigo'])
                if key not in areas_dict:
                    areas_dict[key] = area.copy()
                
                plano_area_rows.append({
                    'id_plano_acao': id_plano,
                    'area_codigo': area['area_codigo'],
                    'subarea_codigo': area['subarea_codigo'],
                })
            
            # --- PLANO AÇÃO (tabela principal) ---
            plano_rows.append({
                'id_plano_acao': id_plano,
                'codigo_plano_acao': r.get('codigo_plano_acao', ''),
                'ano_exercicio': r.get('ano_plano_acao'),
                'modalidade': r.get('modalidade_plano_acao', ''),
                'situacao': r.get('situacao_plano_acao', ''),
                'motivo_impedimento': r.get('motivo_impedimento_plano_acao', ''),
                'cnpj_municipio': cnpj,
                'codigo_ibge': ibge,
                'codigo_banco': r.get('codigo_banco_plano_acao', ''),
                'nome_banco': r.get('nome_banco_plano_acao', ''),
                'agencia': r.get('numero_agencia_plano_acao'),
                'dv_agencia': r.get('dv_agencia_plano_acao', ''),
                'conta': r.get('numero_conta_plano_acao'),
                'dv_conta': r.get('dv_conta_plano_acao', ''),
                'codigo_emenda_formatado': emenda_fmt,
                'id_programa': r.get('id_programa'),
                'descricao_acao': r.get('descricao_programacao_orcamentaria_plano_acao', ''),
                'areas_publicas_raw': areas_str,
                'valor_custeio': r.get('valor_custeio_plano_acao'),
                'valor_investimento': r.get('valor_investimento_plano_acao'),
                'valor_total': (r.get('valor_custeio_plano_acao') or 0) + (r.get('valor_investimento_plano_acao') or 0),
            })
        
        # Criar DataFrames
        df_plano = pd.DataFrame(plano_rows)
        df_areas = pd.DataFrame(list(areas_dict.values()))
        df_plano_areas = pd.DataFrame(plano_area_rows)
        df_emendas = pd.DataFrame(list(emendas_dict.values()))
        df_municipios = pd.DataFrame(list(municipios_dict.values()))
        
        # Tipos
        for df in [df_plano, df_emendas, df_municipios]:
            for col in df.columns:
                if 'valor' in col.lower() or 'custeio' in col.lower() or 'investimento' in col.lower():
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Tabela wide (desnormalizada) para Excel
        df_wide = self._create_wide_table(df_plano, df_areas, df_plano_areas, df_emendas, df_municipios)
        
        logger.info(f"Normalização concluída:")
        logger.info(f"  plano_acao: {len(df_plano)} registros")
        logger.info(f"  areas: {len(df_areas)} áreas únicas")
        logger.info(f"  plano_acao_areas: {len(df_plano_areas)} relacionamentos")
        logger.info(f"  emendas: {len(df_emendas)} emendas únicas")
        logger.info(f"  municipios: {len(df_municipios)} municípios únicos")
        logger.info(f"  wide: {len(df_wide)} linhas")
        
        return {
            'plano_acao': df_plano,
            'areas': df_areas,
            'plano_acao_areas': df_plano_areas,
            'emendas': df_emendas,
            'municipios': df_municipios,
            'wide': df_wide,
        }
    
    def _create_wide_table(self, df_plano, df_areas, df_plano_areas, df_emendas, df_municipios) -> pd.DataFrame:
        """Cria tabela desnormalizada ampla para análise no Excel."""
        
        # Merge áreas como string concatenada
        areas_agg = df_plano_areas.merge(df_areas, on=['area_codigo', 'subarea_codigo'], how='left')
        areas_agg['area_full'] = areas_agg.apply(
            lambda r: f"{r['area_codigo']}-{r['area_nome']}" + (f" / {r['subarea_codigo']}-{r['subarea_nome']}" if r['subarea_codigo'] else ''),
            axis=1
        )
        areas_concat = areas_agg.groupby('id_plano_acao')['area_full'].apply(lambda x: ' ; '.join(x.dropna())).reset_index()
        areas_concat.columns = ['id_plano_acao', 'areas_publicas_normalizadas']
        
        # Merge emendas
        emendas_cols = ['codigo_emenda_formatado', 'numero_emenda', 'ano_emenda', 'codigo_parlamentar', 'sequencial_emenda', 'nome_parlamentar']
        df_emendas_slim = df_emendas[emendas_cols].copy()
        
        # Merge municípios
        municipios_cols = ['cnpj_municipio', 'codigo_ibge', 'nome_municipio', 'uf']
        df_municipios_slim = df_municipios[municipios_cols].copy()
        
        # Construir wide
        df_wide = df_plano.merge(areas_concat, on='id_plano_acao', how='left')
        df_wide = df_wide.merge(df_emendas_slim, on='codigo_emenda_formatado', how='left')
        df_wide = df_wide.merge(df_municipios_slim, on='cnpj_municipio', how='left')
        
        # Reordenar colunas
        cols_order = [
            'id_plano_acao', 'codigo_plano_acao', 'ano_exercicio',
            'nome_parlamentar', 'codigo_emenda_formatado', 'numero_emenda', 'ano_emenda', 'codigo_parlamentar', 'sequencial_emenda',
            'nome_municipio', 'uf', 'codigo_ibge', 'cnpj_municipio',
            'modalidade', 'situacao', 'motivo_impedimento',
            'valor_investimento', 'valor_custeio', 'valor_total',
            'descricao_acao', 'areas_publicas_raw', 'areas_publicas_normalizadas',
            'codigo_banco', 'nome_banco', 'agencia', 'dv_agencia', 'conta', 'dv_conta',
            'id_programa',
        ]
        
        # Adicionar colunas que existam
        final_cols = [c for c in cols_order if c in df_wide.columns]
        remaining = [c for c in df_wide.columns if c not in final_cols]
        df_wide = df_wide[final_cols + remaining]
        
        return df_wide
    
    def _empty_result(self) -> Dict[str, pd.DataFrame]:
        """Retorna estrutura vazia."""
        return {
            'plano_acao': pd.DataFrame(),
            'areas': pd.DataFrame(),
            'plano_acao_areas': pd.DataFrame(),
            'emendas': pd.DataFrame(),
            'municipios': pd.DataFrame(),
            'wide': pd.DataFrame(),
        }
    
    def export_to_excel(self, data: Dict[str, pd.DataFrame], filepath: str) -> bool:
        """Exporta todas as tabelas para Excel com múltiplas abas."""
        try:
            logger.info(f"Exportando Excel: {filepath}")
            
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                # Aba 1: Tabela Wide (pronta para análise)
                data['wide'].to_excel(writer, index=False, sheet_name='Dados_Completos')
                self._format_sheet(writer.sheets['Dados_Completos'], data['wide'])
                
                # Aba 2: Plano Ação (fato)
                data['plano_acao'].to_excel(writer, index=False, sheet_name='Plano_Acao')
                self._format_sheet(writer.sheets['Plano_Acao'], data['plano_acao'])
                
                # Aba 3: Áreas Políticas Públicas (dimensão)
                data['areas'].to_excel(writer, index=False, sheet_name='Areas_Politicas_Publicas')
                self._format_sheet(writer.sheets['Areas_Politicas_Publicas'], data['areas'])
                
                # Aba 4: Junção Plano-Áreas
                data['plano_acao_areas'].to_excel(writer, index=False, sheet_name='Plano_Acao_Areas')
                self._format_sheet(writer.sheets['Plano_Acao_Areas'], data['plano_acao_areas'])
                
                # Aba 5: Emendas (dimensão)
                data['emendas'].to_excel(writer, index=False, sheet_name='Emendas_Parlamentares')
                self._format_sheet(writer.sheets['Emendas_Parlamentares'], data['emendas'])
                
                # Aba 6: Municípios (dimensão)
                data['municipios'].to_excel(writer, index=False, sheet_name='Municipios')
                self._format_sheet(writer.sheets['Municipios'], data['municipios'])
                
                # Aba 7: Resumo por Parlamentar
                if not data['plano_acao'].empty:
                    resumo = self._create_parlamentar_summary(data['plano_acao'])
                    resumo.to_excel(writer, index=False, sheet_name='Resumo_Parlamentar')
                    self._format_sheet(writer.sheets['Resumo_Parlamentar'], resumo)
                
                # Aba 8: Resumo por Área
                if not data['areas'].empty:
                    resumo_area = self._create_area_summary(data['plano_acao_areas'], data['areas'])
                    resumo_area.to_excel(writer, index=False, sheet_name='Resumo_Areas')
                    self._format_sheet(writer.sheets['Resumo_Areas'], resumo_area)
            
            logger.info(f"Excel salvo: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Erro ao exportar Excel: {e}")
            return False
    
    def _create_parlamentar_summary(self, df_plano: pd.DataFrame, df_wide: pd.DataFrame) -> pd.DataFrame:
        """Cria resumo agregado por parlamentar usando a tabela wide."""
        if df_wide.empty:
            return pd.DataFrame()
        
        # Verificar qual coluna de parlamentar existe
        parlamentar_col = None
        for col in ['nome_parlamentar', 'parlamentar', 'nome_parlamentar_emenda']:
            if col in df_wide.columns:
                parlamentar_col = col
                break
        
        if parlamentar_col is None:
            logger.warning("Coluna de parlamentar não encontrada na tabela wide")
            return pd.DataFrame()
        
        # Verificar colunas disponíveis para agregação
        agg_dict = {
            'total_registros': ('id_plano_acao', 'count'),
        }
        
        # Adicionar agregações condicionais
        if 'codigo_ibge' in df_wide.columns:
            agg_dict['municipios_unicos'] = ('codigo_ibge', 'nunique')
        elif 'cnpj_municipio' in df_wide.columns:
            agg_dict['municipios_unicos'] = ('cnpj_municipio', 'nunique')
        
        if 'uf' in df_wide.columns:
            agg_dict['ufs'] = ('uf', lambda x: ', '.join(sorted(x.dropna().unique())))
        
        if 'ano_exercicio' in df_wide.columns:
            agg_dict['anos'] = ('ano_exercicio', lambda x: ', '.join(map(str, sorted(x.dropna().unique()))))
        
        if 'valor_investimento' in df_wide.columns:
            agg_dict['valor_total_investimento'] = ('valor_investimento', 'sum')
        
        if 'valor_custeio' in df_wide.columns:
            agg_dict['valor_total_custeio'] = ('valor_custeio', 'sum')
        
        if 'valor_total' in df_wide.columns:
            agg_dict['valor_total'] = ('valor_total', 'sum')
            agg_dict['media_por_registro'] = ('valor_total', 'mean')
            agg_dict['maior_valor'] = ('valor_total', 'max')
            agg_dict['menor_valor'] = ('valor_total', 'min')
        
        if 'situacao' in df_wide.columns:
            agg_dict['situacoes'] = ('situacao', lambda x: x.value_counts().to_dict())
        
        if 'nome_banco' in df_wide.columns:
            agg_dict['bancos'] = ('nome_banco', lambda x: ', '.join(sorted(x.dropna().unique())))
        
        summary = df_wide.groupby(parlamentar_col).agg(**agg_dict).reset_index()
        
        # Renomear coluna
        summary = summary.rename(columns={parlamentar_col: 'parlamentar'})
        
        # Formatar valores
        for col in ['valor_total_investimento', 'valor_total_custeio', 'valor_total', 
                    'media_por_registro', 'maior_valor', 'menor_valor']:
            if col in summary.columns:
                summary[col] = summary[col].round(2)
        
        summary = summary.sort_values('valor_total', ascending=False).reset_index(drop=True)
        summary.insert(0, 'ranking', range(1, len(summary) + 1))
        
        return summary
    
    def _create_area_summary(self, df_plano_areas: pd.DataFrame, df_areas: pd.DataFrame) -> pd.DataFrame:
        """Cria resumo agregado por área política pública."""
        if df_plano_areas.empty or df_areas.empty:
            return pd.DataFrame()
        
        merged = df_plano_areas.merge(df_areas, on=['area_codigo', 'subarea_codigo'], how='left')
        
        summary = merged.groupby(['area_codigo', 'area_nome', 'subarea_codigo', 'subarea_nome']).agg(
            qtd_planos=('id_plano_acao', 'count'),
            parlamentares_unicos=('id_plano_acao', lambda x: len(set(x))),  # placeholder
        ).reset_index()
        
        # Adicionar parlamentares únicos (precisa merge com plano_acao)
        # Por simplicidade, retornar contagem básica
        summary = summary.sort_values('qtd_planos', ascending=False).reset_index(drop=True)
        summary.insert(0, 'ranking', range(1, len(summary) + 1))
        
        return summary
    
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
    
    def export_to_csv(self, data: Dict[str, pd.DataFrame], base_path: str, sep: str = ';') -> bool:
        """Exporta cada tabela para CSV separado."""
        try:
            for name, df in data.items():
                if not df.empty:
                    filepath = f"{base_path}_{name}.csv"
                    df.to_csv(filepath, index=False, sep=sep, encoding='utf-8-sig')
                    logger.info(f"CSV salvo: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Erro ao exportar CSV: {e}")
            return False
    
    def print_summary(self, data: Dict[str, pd.DataFrame]):
        """Imprime resumo no console."""
        df_plano = data['plano_acao']
        df_wide = data['wide']
        if df_plano.empty:
            print("Nenhum dado para resumo.")
            return
        
        print("\n" + "="*90)
        print("RESUMO COMPLETO - TRANSFERÊNCIAS ESPECIAIS (Emendas Pix) - NORMALIZADO")
        print("="*90)
        print(f"Total de registros (plano_acao): {len(data['plano_acao']):,}")
        print(f"Áreas políticas públicas únicas: {len(data['areas']):,}")
        print(f"Relacionamentos plano-área: {len(data['plano_acao_areas']):,}")
        print(f"Emendas parlamentares únicas: {len(data['emendas']):,}")
        print(f"Municípios únicos: {len(data['municipios']):,}")
        print(f"Tabela wide (desnormalizada): {len(data['wide']):,}")
        
        # Usar wide table para UFs e anos
        print(f"\nAnos cobertos: {sorted(df_wide['ano_exercicio'].dropna().unique())}")
        print(f"Estados (UFs): {sorted(df_wide['uf'].dropna().unique())}")
        
        def fmt(val):
            return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        print(f"Valor total investimento: {fmt(df_plano['valor_investimento'].sum())}")
        print(f"Valor total custeio: {fmt(df_plano['valor_custeio'].sum())}")
        print(f"Valor total geral: {fmt(df_plano['valor_total'].sum())}")
        
        print(f"\nSituações: {df_plano['situacao'].value_counts().to_dict()}")
        print(f"Modalidades: {df_plano['modalidade'].value_counts().to_dict()}")
        
        # Top 15 parlamentares
        summary = self._create_parlamentar_summary(df_plano, df_wide)
        print("\n" + "-"*90)
        print("TOP 15 PARLAMENTARES POR VALOR TOTAL")
        print("-"*90)
        print(f"{'Rank':>4} | {'Parlamentar':<35} | {'Total (R$)':>18} | {'Reg':>5} | {'Mun':>5} | {'Anos'}")
        print("-"*90)
        for _, row in summary.head(15).iterrows():
            total_fmt = f"R$ {row['valor_total']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            print(f"{row['ranking']:>4} | {row['parlamentar']:<35} | {total_fmt:>18} | {row['total_registros']:>5} | {row['municipios_unicos']:>5} | {row['anos']}")
        print("="*90 + "\n")


def main():
    """Função principal."""
    # Configurações
    ANO = None  # None = todos os anos (2020-2026)
    PARLAMENTAR = None  # None = todos, ou nome parcial
    UF = None  # None = todos
    MAX_RECORDS = None  # None = sem limite
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filtros = []
    if ANO: filtros.append(f"ano{ANO}")
    if PARLAMENTAR: filtros.append(f"parl_{PARLAMENTAR.replace(' ', '_')}")
    if UF: filtros.append(f"uf{UF}")
    filtro_str = "_".join(filtros) if filtros else "todos_anos"
    
    output_excel = f'transferencias_especiais_COMPLETO_normalizado_{filtro_str}_{timestamp}.xlsx'
    output_csv_base = f'transferencias_especiais_COMPLETO_normalizado_{filtro_str}_{timestamp}'
    
    logger.info("="*90)
    logger.info("EXTRAÇÃO COMPLETA E NORMALIZADA - TRANSFERÊNCIAS ESPECIAIS")
    logger.info("="*90)
    logger.info(f"Filtros: ano={ANO}, parlamentar={PARLAMENTAR}, uf={UF}")
    logger.info(f"Saída: {output_excel}")
    
    extractor = TransfereGovFullExtractor(
        timeout=120,
        max_retries=3,
        retry_delay=2.0,
        page_size=1000
    )
    
    try:
        data = extractor.extract_all(
            ano=ANO,
            parlamentar=PARLAMENTAR,
            uf=UF,
            max_records=MAX_RECORDS
        )
        
        if data['plano_acao'].empty:
            logger.warning("Nenhum registro encontrado")
            return 1
        
        extractor.print_summary(data)
        
        # Exportar
        success_excel = extractor.export_to_excel(data, output_excel)
        success_csv = extractor.export_to_csv(data, output_csv_base)
        
        if success_excel or success_csv:
            logger.info("Extração e normalização concluídas com sucesso!")
            logger.info(f"Arquivos: {output_excel}, {output_csv_base}_*.csv")
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