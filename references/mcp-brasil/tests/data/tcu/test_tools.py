"""Tests for the TCU tool functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_brasil.data.tcu import tools
from mcp_brasil.data.tcu.schemas import (
    Acordao,
    CertidaoConsolidada,
    CertidaoItem,
    Inabilitado,
    Inidoneo,
    PautaSessao,
    PedidoCongresso,
    PessoaCadirreg,
    ResultadoDebito,
    TermoContratual,
)

CLIENT_MODULE = "mcp_brasil.data.tcu.client"


def _mock_ctx() -> MagicMock:
    """Create a mock Context with async log methods."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.warning = AsyncMock()
    return ctx


class TestConsultarAcordaos:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Acordao(
                key="ACORDAO-COMPLETO-123",
                tipo="ACORDAO",
                anoAcordao="2026",
                titulo="ACORDAO 100/2026 ATA 1/2026 - PLENARIO",
                numeroAcordao="100",
                numeroAta="1/2026",
                colegiado="Plenário",
                dataSessao="18/03/2026",
                relator="BRUNO DANTAS",
                situacao="OFICIALIZADO",
                sumario="EMBARGOS DE DECLARAÇÃO",
                urlAcordao="https://contas.tcu.gov.br/...",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_acordaos(ctx)
        assert "100" in result
        assert "2026" in result
        assert "Plenário" in result
        assert "BRUNO DANTAS" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_acordaos(ctx)
        assert "Nenhum acórdão" in result

    @pytest.mark.asyncio
    async def test_filter_by_colegiado(self) -> None:
        mock_data = [
            Acordao(
                key="A1",
                anoAcordao="2026",
                numeroAcordao="100",
                colegiado="Plenário",
                relator="BRUNO DANTAS",
                sumario="Embargos",
            ),
            Acordao(
                key="A2",
                anoAcordao="2026",
                numeroAcordao="200",
                colegiado="1ª Câmara",
                relator="ANA ARRAES",
                sumario="Recurso",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_acordaos(ctx, colegiado="Plenário")
        assert "BRUNO DANTAS" in result
        assert "ANA ARRAES" not in result
        assert "colegiado: 'Plenário'" in result

    @pytest.mark.asyncio
    async def test_filter_by_relator(self) -> None:
        mock_data = [
            Acordao(
                key="A1",
                anoAcordao="2026",
                numeroAcordao="100",
                colegiado="Plenário",
                relator="BRUNO DANTAS",
                sumario="Embargos",
            ),
            Acordao(
                key="A2",
                anoAcordao="2026",
                numeroAcordao="200",
                colegiado="1ª Câmara",
                relator="ANA ARRAES",
                sumario="Recurso",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_acordaos(ctx, relator="arraes")
        assert "ANA ARRAES" in result
        assert "BRUNO DANTAS" not in result

    @pytest.mark.asyncio
    async def test_filter_by_ano(self) -> None:
        mock_data = [
            Acordao(
                key="A1",
                anoAcordao="2026",
                numeroAcordao="100",
                colegiado="Plenário",
                relator="BRUNO DANTAS",
                sumario="Embargos",
            ),
            Acordao(
                key="A2",
                anoAcordao="2025",
                numeroAcordao="200",
                colegiado="1ª Câmara",
                relator="ANA ARRAES",
                sumario="Recurso",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_acordaos(ctx, ano="2025")
        assert "ANA ARRAES" in result
        assert "BRUNO DANTAS" not in result

    @pytest.mark.asyncio
    async def test_filter_by_busca(self) -> None:
        mock_data = [
            Acordao(
                key="A1",
                anoAcordao="2026",
                numeroAcordao="100",
                colegiado="Plenário",
                relator="BRUNO DANTAS",
                sumario="EMBARGOS DE DECLARAÇÃO em recurso",
            ),
            Acordao(
                key="A2",
                anoAcordao="2026",
                numeroAcordao="200",
                colegiado="1ª Câmara",
                relator="ANA ARRAES",
                sumario="TOMADA DE CONTAS ESPECIAL",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_acordaos(ctx, busca="embargos")
        assert "BRUNO DANTAS" in result
        assert "ANA ARRAES" not in result
        assert "busca: 'embargos'" in result

    @pytest.mark.asyncio
    async def test_filter_empty_result(self) -> None:
        mock_data = [
            Acordao(
                key="A1",
                anoAcordao="2026",
                numeroAcordao="100",
                colegiado="Plenário",
                relator="BRUNO DANTAS",
                sumario="Embargos",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_acordaos(ctx, relator="inexistente")
        assert "Nenhum acórdão" in result

    @pytest.mark.asyncio
    async def test_filter_fetches_larger_batch(self) -> None:
        mock_data = [
            Acordao(
                key="A1",
                anoAcordao="2026",
                numeroAcordao="100",
                colegiado="Plenário",
                relator="BRUNO DANTAS",
                sumario="Embargos",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ) as mock_client:
            await tools.consultar_acordaos(ctx, quantidade=10, ano="2026")
        # With filters, should fetch max(10*10, 200) = 200
        mock_client.assert_called_once_with(inicio=0, quantidade=200)

    @pytest.mark.asyncio
    async def test_truncates_long_sumario(self) -> None:
        mock_data = [
            Acordao(
                key="ACORDAO-COMPLETO-456",
                anoAcordao="2026",
                numeroAcordao="200",
                numeroAta="2/2026",
                colegiado="1ª Câmara",
                dataSessao="19/03/2026",
                relator="ANA ARRAES",
                sumario="A" * 200,
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_acordaos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_acordaos(ctx)
        assert "..." in result


class TestConsultarInabilitados:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Inabilitado(
                nome="FULANO DA SILVA",
                cpf="123.456.789-00",
                processo="026.615/2020-7",
                deliberacao="AC-000738/2022-PL",
                data_transito_julgado="2022-07-16T03:00:00Z",
                data_final="2027-07-16T03:00:00Z",
                data_acordao="2022-04-06T17:30:00Z",
                uf="MA",
                municipio="SANTA INES",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_inabilitados",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_inabilitados(ctx)
        assert "FULANO DA SILVA" in result
        assert "123.456.789-00" in result
        assert "MA" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_inabilitados",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_inabilitados(ctx)
        assert "Nenhum inabilitado" in result

    @pytest.mark.asyncio
    async def test_with_cpf(self) -> None:
        mock_data = [
            Inabilitado(
                nome="BELTRANO",
                cpf="999.888.777-66",
                processo="001.000/2023-1",
                deliberacao="AC-001000/2023-PL",
                data_transito_julgado="2023-01-01T00:00:00Z",
                data_final="2028-01-01T00:00:00Z",
                data_acordao="2023-01-01T00:00:00Z",
                uf="SP",
                municipio="SAO PAULO",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_inabilitados",
            new_callable=AsyncMock,
            return_value=mock_data,
        ) as mock_client:
            result = await tools.consultar_inabilitados(ctx, cpf="99988877766")
        mock_client.assert_called_once_with(cpf="99988877766", offset=0, limit=25)
        assert "BELTRANO" in result


class TestConsultarInidoneos:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            Inidoneo(
                nome="EMPRESA LTDA",
                cpf_cnpj="07.405.573/0001-44",
                processo="007.720/2012-2",
                deliberacao="AC-002099/2015-PL",
                data_transito_julgado="2021-09-30T03:00:00Z",
                data_final="2026-09-30T03:00:00Z",
                data_acordao="2015-08-19T17:30:00Z",
                uf="DF",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_inidoneos",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_inidoneos(ctx)
        assert "EMPRESA LTDA" in result
        assert "07.405.573/0001-44" in result
        assert "DF" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_inidoneos",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_inidoneos(ctx)
        assert "Nenhum licitante inidôneo" in result


class TestConsultarCertidoes:
    @pytest.mark.asyncio
    async def test_formats_result(self) -> None:
        mock_data = CertidaoConsolidada(
            razaoSocial="Banco do Brasil S.A.",
            nomeFantasia="BB",
            cnpj="00.000.000/0001-91",
            certidoes=[
                CertidaoItem(
                    emissor="TCU",
                    tipo="Inidoneos",
                    descricao="Licitantes Inidôneos",
                    situacao="NADA_CONSTA",
                    dataHoraEmissao="22/03/2026 23:14",
                ),
                CertidaoItem(
                    emissor="CNJ",
                    tipo="CNIA",
                    descricao="CNIA",
                    situacao="NADA_CONSTA",
                    dataHoraEmissao="22/03/2026 23:14",
                ),
            ],
            seCnpjEncontradoNaBaseTcu=True,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_certidoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_certidoes(ctx, cnpj="00000000000191")
        assert "Banco do Brasil" in result
        assert "NADA_CONSTA" in result
        assert "TCU" in result
        assert "CNJ" in result

    @pytest.mark.asyncio
    async def test_empty_certidoes(self) -> None:
        mock_data = CertidaoConsolidada(
            razaoSocial="Empresa X",
            nomeFantasia="",
            cnpj="11.111.111/0001-11",
            certidoes=[],
            seCnpjEncontradoNaBaseTcu=False,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_certidoes",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_certidoes(ctx, cnpj="11111111000111")
        assert "Nenhuma certidão" in result


class TestConsultarPedidosCongresso:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            PedidoCongresso(
                tipo="REQ",
                numero=4,
                data_aprovacao="2026-02-19T03:00:00Z",
                assunto="Informações sobre obras ferroviárias",
                autor="Dr. Hiran",
                processo_scn="004.808/2026-6",
                link_proposicao="https://senado.leg.br/...",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pedidos_congresso",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_pedidos_congresso(ctx)
        assert "REQ" in result
        assert "Dr. Hiran" in result
        assert "004.808/2026-6" in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pedidos_congresso",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_pedidos_congresso(ctx)
        assert "Nenhum pedido" in result


class TestCalcularDebito:
    @pytest.mark.asyncio
    async def test_formats_result(self) -> None:
        mock_data = ResultadoDebito(
            data="22/03/2026",
            saldoDebito=1000.0,
            saldoVariacaoSelic=577.38,
            saldoJuros=0.0,
            saldoTotal=1577.38,
        )
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.calcular_debito",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.calcular_debito(
                ctx,
                data_atualizacao="22/03/2026",
                data_fato="01/01/2020",
                valor_original=1000.0,
            )
        assert "R$ 1.000,00" in result
        assert "R$ 577,38" in result
        assert "R$ 1.577,38" in result
        assert "01/01/2020" in result


class TestConsultarTermosContratuais:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            TermoContratual(
                numero=1,
                ano=2025,
                tipoContratacao="CONTRATO",
                nomeFornecedor="EMPRESA ABC LTDA",
                cnpjFornecedor="12345678000100",
                objeto="Prestação de serviços de TI",
                valorInicial=100000.0,
                valorAtualizado=120000.0,
                dataAssinatura="2025-01-15T00:00:00-0300",
                dataTerminoVigencia="2025-12-31T00:00:00-0300",
                modalidadeLicitacao="PREGAO ELETRONICO",
                numeroProcesso="001.000/2025-1",
                unidadeGestora="STI",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_termos_contratuais",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_termos_contratuais(ctx)
        assert "EMPRESA ABC LTDA" in result
        assert "R$ 120.000,00" in result

    @pytest.mark.asyncio
    async def test_filter_by_ano(self) -> None:
        mock_data = [
            TermoContratual(numero=1, ano=2025, nomeFornecedor="A", valorAtualizado=100.0),
            TermoContratual(numero=2, ano=2024, nomeFornecedor="B", valorAtualizado=200.0),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_termos_contratuais",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_termos_contratuais(ctx, ano=2025)
        assert "A" in result
        assert "B" not in result

    @pytest.mark.asyncio
    async def test_empty_after_filter(self) -> None:
        mock_data = [
            TermoContratual(numero=1, ano=2025, nomeFornecedor="A", valorAtualizado=100.0),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_termos_contratuais",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_termos_contratuais(ctx, ano=2020)
        assert "Nenhum termo" in result


class TestConsultarPautasSessao:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            PautaSessao(
                nomeColegiado="Plenário",
                siglaColegiado="PL",
                dataSessao="18/03/2026",
                siglaRelator="MIN-BD",
                nomeRelator="BRUNO DANTAS",
                numeroProcesso="001.438/2020-0",
                naturezaProcesso="CONTROLE EXTERNO",
                tipoProcesso="TOMADA DE CONTAS ESPECIAL",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pautas_sessao",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_pautas_sessao(ctx)
        assert "BRUNO DANTAS" in result
        assert "001.438/2020-0" in result
        assert "Plenário" in result
        assert "TOMADA DE CONTAS ESPECIAL" in result

    @pytest.mark.asyncio
    async def test_filter_by_colegiado(self) -> None:
        mock_data = [
            PautaSessao(
                nomeColegiado="Plenário",
                nomeRelator="BRUNO DANTAS",
                numeroProcesso="001/2026",
                tipoProcesso="TCE",
            ),
            PautaSessao(
                nomeColegiado="Segunda Câmara",
                nomeRelator="ANA ARRAES",
                numeroProcesso="002/2026",
                tipoProcesso="APOSENTADORIA",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pautas_sessao",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_pautas_sessao(ctx, colegiado="Plenário")
        assert "BRUNO DANTAS" in result
        assert "ANA ARRAES" not in result

    @pytest.mark.asyncio
    async def test_filter_by_relator(self) -> None:
        mock_data = [
            PautaSessao(
                nomeColegiado="Plenário",
                nomeRelator="BRUNO DANTAS",
                numeroProcesso="001/2026",
            ),
            PautaSessao(
                nomeColegiado="Plenário",
                nomeRelator="ANA ARRAES",
                numeroProcesso="002/2026",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pautas_sessao",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_pautas_sessao(ctx, relator="arraes")
        assert "ANA ARRAES" in result
        assert "BRUNO DANTAS" not in result

    @pytest.mark.asyncio
    async def test_filter_by_numero_processo(self) -> None:
        mock_data = [
            PautaSessao(
                nomeColegiado="Plenário",
                nomeRelator="BRUNO DANTAS",
                numeroProcesso="001.438/2020-0",
            ),
            PautaSessao(
                nomeColegiado="Plenário",
                nomeRelator="ANA ARRAES",
                numeroProcesso="999.999/2025-1",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pautas_sessao",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_pautas_sessao(ctx, numero_processo="001.438")
        assert "BRUNO DANTAS" in result
        assert "ANA ARRAES" not in result

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_pautas_sessao",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_pautas_sessao(ctx)
        assert "Nenhuma pauta" in result


class TestConsultarCadirreg:
    @pytest.mark.asyncio
    async def test_formats_table(self) -> None:
        mock_data = [
            PessoaCadirreg(
                nomeResponsavel="FULANO DE TAL",
                numCPF="12345678900",
                numProcesso="001",
                anoProcesso="2020",
                julgamento="Contas irregulares",
                unidadeTecnicaProcesso="SECEX-PI",
                seDetentorCargoFuncaoPublica="Sim",
                seFalecido="Não",
            ),
        ]
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_cadirreg",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await tools.consultar_cadirreg(ctx, cpf="12345678900")
        assert "FULANO DE TAL" in result
        assert "001/2020" in result

    @pytest.mark.asyncio
    async def test_not_found(self) -> None:
        ctx = _mock_ctx()
        with patch(
            f"{CLIENT_MODULE}.consultar_cadirreg",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await tools.consultar_cadirreg(ctx, cpf="00000000000")
        assert "não consta" in result
