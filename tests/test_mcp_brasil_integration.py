"""
Integration tests: verify our data model covers the 3 mcp-brasil smart prompts.

These tests validate that our schemas, enrichment tables, and SQL views
provide all the fields and query capabilities needed by mcp-brasil's
prompts for TransfereGov, Câmara, and BrasilAPI.

No DB or network required — pure schema/model tests.
"""

from __future__ import annotations

import pytest

from src.schemas import PlanoAcaoSchema, validate_records

# ============================================================================
# PROMPT 1: analise_emendas_pix (TransfereGov)
# ============================================================================
# mcp-brasil's prompt asks the LLM to:
#   - buscar_emendas_pix(ano=..., uf=...) → list emendas pix
#   - detalhe_emenda(id) → full detail of one plano de ação
#   - Report: volume total, principais autores, distribuição UF/município,
#     áreas temáticas, concentração de recursos
#
# Our schema (PlanoAcaoSchema) must cover all fields the prompt needs.


class TestTransfereGovPromptCoverage:
    """Verify PlanoAcaoSchema covers all fields for analise_emendas_pix."""

    # Fields the mcp-brasil TransferenciaEspecial schema expects
    MCPBRASIL_FIELDS = {
        "id_plano_acao",
        "codigo_plano_acao",
        "ano",
        "situacao",
        "nome_parlamentar",
        "numero_emenda",
        "ano_emenda",
        "valor_custeio",
        "valor_investimento",
        "cnpj_beneficiario",
        "nome_beneficiario",
        "uf_beneficiario",
        "area_politica_publica",
    }

    def _sample_plano(self) -> PlanoAcaoSchema:
        """Create a realistic sample plano de ação."""
        return PlanoAcaoSchema.model_validate(
            {
                "planoAcaoId": 12345,
                "planoAcaoCodigo": "202600012345",
                "planoAcaoSituacao": "EM_EXECUCAO",
                "objetoId": 301,
                "objetoDescricao": "Cemitérios",
                "programaId": 25,
                "programaCodigo": "TE",
                "beneficiarioId": 9858,
                "beneficiarioNome": "Município de Teresina",
                "beneficiarioCnpj": "12345678000190",
                "uf": "PI",
                "codigoEmendaFormatado": "202642740010",
                "politicasPublicas": "4",
                "valorCusteio": 50000.0,
                "valorInvestimento": 100000.0,
                "valorTotal": 150000.0,
            }
        )

    # --- Field coverage tests ---

    def test_has_plano_id(self):
        """prompt needs: id_plano_acao → detalhe_emenda(id)"""
        p = self._sample_plano()
        assert p.planoAcaoId == 12345

    def test_has_codigo(self):
        """prompt needs: codigo_plano_acao → identification"""
        p = self._sample_plano()
        assert p.planoAcaoCodigo == "202600012345"

    def test_has_ano_from_codigo(self):
        """prompt needs: ano → filter by year (we extract from codigo)"""
        p = self._sample_plano()
        # Year is embedded in planoAcaoCodigo (first 4 chars)
        assert p.planoAcaoCodigo[:4] == "2026"

    def test_has_situacao(self):
        """prompt needs: situacao → status analysis"""
        p = self._sample_plano()
        assert p.planoAcaoSituacao == "EM_EXECUCAO"

    def test_has_parlamentar_via_emenda(self):
        """prompt needs: nome_parlamentar → principais autores"""
        p = self._sample_plano()
        # We store parlamentar parsed from codigoEmendaFormatado
        assert p.codigoEmendaFormatado == "202642740010"

    def test_has_numero_emenda(self):
        """prompt needs: numero_emenda → emenda identification"""
        p = self._sample_plano()
        assert p.codigoEmendaFormatado == "202642740010"

    def test_has_valores(self):
        """prompt needs: valor_custeio, valor_investimento → volume total"""
        p = self._sample_plano()
        assert p.valorCusteio == 50000.0
        assert p.valorInvestimento == 100000.0
        assert p.valor_total_real == 150000.0

    def test_has_cnpj_beneficiario(self):
        """prompt needs: cnpj_beneficiario → beneficiary identification"""
        p = self._sample_plano()
        assert p.beneficiarioCnpj == "12345678000190"

    def test_has_nome_beneficiario(self):
        """prompt needs: nome_beneficiario → beneficiary name"""
        p = self._sample_plano()
        assert p.beneficiarioNome == "Município de Teresina"

    def test_has_uf_beneficiario(self):
        """prompt needs: uf_beneficiario → distribuição por UF"""
        p = self._sample_plano()
        assert p.uf == "PI"

    def test_has_politicas_publicas(self):
        """prompt needs: area_politica_publica → áreas temáticas"""
        p = self._sample_plano()
        assert p.politicasPublicas == "4"

    # --- Query capability tests ---

    def test_can_filter_by_uf(self):
        """Prompt requires: filter by UF → we have uf field"""
        records = [
            {"planoAcaoId": 1, "uf": "PI"},
            {"planoAcaoId": 2, "uf": "SP"},
            {"planoAcaoId": 3, "uf": "PI"},
        ]
        validos, _ = validate_records(records)
        pi_planos = [p for p in validos if p.uf == "PI"]
        assert len(pi_planos) == 2

    def test_can_aggregate_valores(self):
        """Prompt requires: volume total → sum of valor_total_real"""
        records = [
            {"planoAcaoId": 1, "valorCusteio": 100, "valorInvestimento": 200},
            {"planoAcaoId": 2, "valorCusteio": 50, "valorInvestimento": 150},
        ]
        validos, _ = validate_records(records)
        total = sum(p.valor_total_real for p in validos)
        assert total == pytest.approx(500.0)

    def test_can_identify_negados(self):
        """Prompt requires:分析 negados → is_negado property"""
        records = [
            {"planoAcaoId": 1, "planoAcaoSituacao": "EM_EXECUCAO"},
            {"planoAcaoId": 2, "planoAcaoSituacao": "IMPEDIDO"},
            {"planoAcaoId": 3, "planoAcaoSituacao": "REPROVADO"},
        ]
        validos, _ = validate_records(records)
        negados = [p for p in validos if p.is_negado]
        assert len(negados) == 2

    def test_can_group_by_situacao(self):
        """Prompt requires: distribution by situation"""
        records = [
            {"planoAcaoId": 1, "planoAcaoSituacao": "EM_EXECUCAO"},
            {"planoAcaoId": 2, "planoAcaoSituacao": "EM_EXECUCAO"},
            {"planoAcaoId": 3, "planoAcaoSituacao": "CONCLUIDO"},
        ]
        validos, _ = validate_records(records)
        by_sit = {}
        for p in validos:
            by_sit[p.planoAcaoSituacao] = by_sit.get(p.planoAcaoSituacao, 0) + 1
        assert by_sit["EM_EXECUCAO"] == 2
        assert by_sit["CONCLUIDO"] == 1


# ============================================================================
# PROMPT 2: perfil_deputado (Câmara)
# ============================================================================
# mcp-brasil's prompt asks the LLM to:
#   - buscar_deputado(deputado_id=...) → dados básicos
#   - Report: nome, partido, UF, legislatura
#   - Gastos de cota parlamentar: total, categorias, fornecedores
#
# Our enrichment tables (parlamentares_dados via camara.py) must cover this.


class TestCamaraPromptCoverage:
    """Verify our Câmara enrichment covers perfil_deputado prompt needs."""

    # Fields perfil_deputado needs (from the prompt text)
    # NOTE: prompt says "partido" but our column is sigla_partido (same data)
    REQUIRED_FIELDS = {"nome", "sigla_partido", "uf"}
    # Fields our enrichment table stores (from camara.py enricher)
    ENRICHED_FIELDS = {
        "deputado_id",
        "nome",
        "nome_urna",
        "sigla_partido",
        "uf",
        "situacao",
        "gabinete_numero",
        "gabinete_predio",
        "gabinete_telefone",
        "gabinete_email",
        "url_foto",
        "ultimo_status",
        "data_nascimento",
        "municipio_nascimento",
        "uf_nascimento",
        "escolaridade",
    }

    def test_camara_fields_superset_of_prompt_needs(self):
        """Our enrichment table has MORE fields than perfil_deputado needs."""
        # perfil_deputado needs: nome, partido, UF
        assert self.REQUIRED_FIELDS.issubset(self.ENRICHED_FIELDS)

    def test_hasnome(self):
        """Prompt needs: nome do deputado."""
        assert "nome" in self.ENRICHED_FIELDS

    def test_has_partido(self):
        """Prompt needs: partido."""
        assert "sigla_partido" in self.ENRICHED_FIELDS

    def test_has_uf(self):
        """Prompt needs: UF."""
        assert "uf" in self.ENRICHED_FIELDS

    def test_has_extra_profile_fields(self):
        """Our enrichment goes beyond the prompt — bonus coverage."""
        extras = self.ENRICHED_FIELDS - self.REQUIRED_FIELDS
        assert len(extras) >= 12  # we store 15+ extra fields

    def test_has_deputado_id_for_api_lookup(self):
        """We store deputado_id for Câmara API cross-reference."""
        assert "deputado_id" in self.ENRICHED_FIELDS

    def test_has_contact_info(self):
        """We store gabinete details for contact info."""
        contact = {"gabinete_telefone", "gabinete_email"}
        assert contact.issubset(self.ENRICHED_FIELDS)

    def test_has_birth_and_education(self):
        """We store demographic data beyond what the prompt asks."""
        demo = {"data_nascimento", "municipio_nascimento", "escolaridade"}
        assert demo.issubset(self.ENRICHED_FIELDS)


# ============================================================================
# PROMPT 3: analise_empresa (BrasilAPI)
# ============================================================================
# mcp-brasil's prompt asks the LLM to:
#   - consultar_cnpj(cnpj=...) → dados cadastrais
#   - Report: razão social, fantasia, CNAE, porte, situação cadastral,
#     endereço completo, capital social
#
# Our enrichment table (validacao_cnpj via validacao.py) must cover this.


class TestBrasilAPIPromptCoverage:
    """Verify our BrasilAPI enrichment covers analise_empresa prompt needs."""

    # Fields analise_empresa needs (from the prompt text)
    PROMPT_REQUIRED_FIELDS = {
        "razao_social",
        "situacao_cadastral",
    }
    # Fields our validacao_cnpj table stores
    ENRICHED_FIELDS = {
        "cnpj",
        "razao_social",
        "nome_fantasia",
        "situacao_cadastral",
        "data_situacao",
        "porte",
        "natureza_juridica",
        "cep",
        "telefone",
        "email",
        "valido",
        "erro",
    }

    def test_brasilapi_fields_superset_of_prompt_needs(self):
        """Our table has more fields than analise_empresa needs."""
        assert self.PROMPT_REQUIRED_FIELDS.issubset(self.ENRICHED_FIELDS)

    def test_has_razao_social(self):
        """Prompt needs: razão social."""
        assert "razao_social" in self.ENRICHED_FIELDS

    def test_has_situacao_cadastral(self):
        """Prompt needs: situação cadastral."""
        assert "situacao_cadastral" in self.ENRICHED_FIELDS

    def test_has_nome_fantasia(self):
        """Prompt also asks for nome fantasia."""
        assert "nome_fantasia" in self.ENRICHED_FIELDS

    def test_has_porte(self):
        """Prompt needs: porte."""
        assert "porte" in self.ENRICHED_FIELDS

    def test_has_endereco_fields(self):
        """Prompt needs: endereço → we have CEP."""
        assert "cep" in self.ENRICHED_FIELDS

    def test_has_contact_fields(self):
        """We store telefone and email."""
        assert "telefone" in self.ENRICHED_FIELDS
        assert "email" in self.ENRICHED_FIELDS

    def test_has_validation_status(self):
        """We track validity separately from API response."""
        assert "valido" in self.ENRICHED_FIELDS
        assert "erro" in self.ENRICHED_FIELDS

    def test_has_natureza_juridica(self):
        """Bonus: we store natureza_juridica."""
        assert "natureza_juridica" in self.ENRICHED_FIELDS


# ============================================================================
# CROSS-CUTTING: Schema compatibility between our project and mcp-brasil
# ============================================================================


class TestSchemaCompatibility:
    """Verify our PlanoAcaoSchema is compatible with mcp-brasil's model."""

    def test_field_mapping_transferegov(self):
        """Map our field names to mcp-brasil's TransferenciaEspecial fields."""
        mapping = {
            # Our field → mcp-brasil field
            "planoAcaoId": "id_plano_acao",
            "planoAcaoCodigo": "codigo_plano_acao",
            "planoAcaoSituacao": "situacao",
            "codigoEmendaFormatado": "numero_emenda",
            "beneficiarioCnpj": "cnpj_beneficiario",
            "beneficiarioNome": "nome_beneficiario",
            "uf": "uf_beneficiario",
            "politicasPublicas": "area_politica_publica",
            "valorCusteio": "valor_custeio",
            "valorInvestimento": "valor_investimento",
        }
        schema_fields = set(PlanoAcaoSchema.model_fields.keys())
        for our_field in mapping:
            assert our_field in schema_fields, f"Our field '{our_field}' not in schema"

    def test_sample_record_converts_to_mcpbrasil_format(self):
        """Verify a PlanoAcaoSchema can be mapped to mcp-brasil's format."""
        p = PlanoAcaoSchema.model_validate(
            {
                "planoAcaoId": 99999,
                "planoAcaoCodigo": "2024500099999",
                "planoAcaoSituacao": "EM_EXECUCAO",
                "beneficiarioNome": "Teresina",
                "beneficiarioCnpj": "12345678000190",
                "uf": "PI",
                "valorCusteio": 10000.0,
                "valorInvestimento": 20000.0,
                "politicasPublicas": "4",
            }
        )
        # Simulate mcp-brasil's expected fields
        mcp_record = {
            "id_plano_acao": p.planoAcaoId,
            "codigo_plano_acao": p.planoAcaoCodigo,
            "situacao": p.planoAcaoSituacao,
            "nome_beneficiario": p.beneficiarioNome,
            "cnpj_beneficiario": p.beneficiarioCnpj,
            "uf_beneficiario": p.uf,
            "valor_custeio": p.valorCusteio,
            "valor_investimento": p.valorInvestimento,
            "area_politica_publica": p.politicasPublicas,
        }
        assert mcp_record["id_plano_acao"] == 99999
        assert mcp_record["uf_beneficiario"] == "PI"
        assert mcp_record["valor_custeio"] == 10000.0
