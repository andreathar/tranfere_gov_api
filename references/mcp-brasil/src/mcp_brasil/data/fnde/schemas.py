"""Pydantic models for FNDE API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FundebMatricula(BaseModel):
    """Matrícula ponderada FUNDEB por município/rede/etapa."""

    ano_censo: int = Field(alias="AnoCenso", description="Ano do Censo Escolar")
    uf: str = Field(alias="Uf", description="Sigla da UF")
    municipio: str = Field(alias="MunicipioGe", description="Nome do município")
    tipo_rede: str = Field(alias="TipoRedeEducacao", description="Tipo de rede educacional")
    tipo_educacao: str = Field(
        alias="DescricaoTipoEducacao", description="Ex: Ensino Regular, Educação Especial"
    )
    tipo_ensino: str = Field(
        alias="DescricaoTipoEnsino", description="Ex: Ensino Fundamental, Ensino Infantil"
    )
    tipo_turma: str = Field(
        alias="DescricaoTipoTurma", description="Ex: Anos Iniciais, Creche, Pré-Escola"
    )
    carga_horaria: str = Field(
        alias="DescricaoTipoCargaHoraria", description="Parcial ou Integral"
    )
    localizacao: str = Field(alias="DescricaoTipoLocalizacao", description="Urbana ou Rural")
    quantidade: int = Field(alias="QtdMatricula", description="Quantidade de matrículas")


class PnaeAluno(BaseModel):
    """Aluno atendido pelo PNAE (alimentação escolar)."""

    id: str = Field(alias="Co_alunos_atendidos")
    ano: str = Field(alias="Ano", description="Ano de referência")
    estado: str = Field(alias="Estado", description="Sigla da UF")
    municipio: str = Field(alias="Municipio", description="Nome do município")
    regiao: str = Field(alias="Regiao", description="Região do Brasil")
    esfera_governo: str = Field(
        alias="Esfera_governo", description="Municipal, Estadual ou Federal"
    )
    etapa_ensino: str = Field(alias="Etapa_ensino", description="Etapa de ensino")
    quantidade: int = Field(alias="Qt_alunos_pnae", description="Quantidade de alunos PNAE")


class PnldLivro(BaseModel):
    """Livro didático distribuído pelo PNLD."""

    programa: str = Field(alias="Programa", description="Nome do programa")
    ano: str = Field(alias="Ano", description="Ano do programa")
    editora: str = Field(alias="Editora", description="Editora do livro")
    codigo: str = Field(alias="Cod_livro", description="Código do livro")
    titulo: str = Field(alias="Titulo_livro", description="Título do livro")
    criterio: str = Field(alias="Criterio", description="Critério de distribuição")
    quantidade: int = Field(alias="Qt_titulos", description="Quantidade de títulos")
    custo: float = Field(alias="Custo_titulos", description="Custo total em R$")


class PnateTransporte(BaseModel):
    """Alunos atendidos pelo PNATE (transporte escolar)."""

    uf: str = Field(alias="Uf", description="Sigla da UF")
    municipio: str = Field(alias="Municipio", description="Nome do município")
    entidade: str = Field(alias="EntidadeExecutora", description="Entidade executora")
    cnpj: str = Field(alias="Cnpj", description="CNPJ da entidade")
    quantidade: int = Field(
        alias="QtdAlunosAtendidos", description="Quantidade de alunos atendidos"
    )
