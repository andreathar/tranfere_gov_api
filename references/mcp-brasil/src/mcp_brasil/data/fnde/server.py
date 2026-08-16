"""FNDE feature server — registers tools.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .tools import (
    consultar_fundeb_matriculas,
    consultar_pnae_alunos,
    consultar_pnate_transporte,
    consultar_pnld_livros,
)

mcp = FastMCP("mcp-brasil-fnde")

mcp.tool(consultar_fundeb_matriculas, tags={"educação", "fundeb", "matrículas"})
mcp.tool(consultar_pnae_alunos, tags={"educação", "pnae", "alimentação"})
mcp.tool(consultar_pnld_livros, tags={"educação", "pnld", "livros"})
mcp.tool(consultar_pnate_transporte, tags={"educação", "pnate", "transporte"})
