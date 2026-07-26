"""Test TSE datasets from mcp-brasil — downloads + queries."""

from __future__ import annotations

import asyncio
import os
import time

os.environ["MCP_BRASIL_DATASETS"] = "tse_candidatos,tse_votacao"


class FakeCtx:
    """Minimal FastMCP Context for testing tools outside MCP server."""

    async def info(self, msg: str) -> None:
        print(f"  [info] {msg}")


async def test_tse_candidatos() -> None:
    """Download tse_candidatos and run a test query."""
    print("\n" + "=" * 60)
    print("  TSE CANDIDATOS — download + query test")
    print("=" * 60)

    from mcp_brasil.datasets.tse_candidatos.tools import (
        buscar_candidatos,
        info_tse_candidatos,
        resumo_cargo_partido,
    )

    ctx = FakeCtx()

    # 1. Check cache status
    print("\n--- info_tse_candidatos ---")
    t0 = time.time()
    info = await info_tse_candidatos(ctx)
    print(info)
    print(f"  ({time.time() - t0:.1f}s)")

    # 2. Search for PI deputados federais in 2022
    print("\n--- buscar_candidatos: DEPUTADO FEDERAL, PI, 2022 ---")
    t0 = time.time()
    result = await buscar_candidatos(
        ctx,
        cargo="DEPUTADO FEDERAL",
        uf="PI",
        ano=2022,
        limite=10,
    )
    print(result)
    print(f"  ({time.time() - t0:.1f}s)")

    # 3. Search for a specific name
    print("\n--- buscar_candidatos: AFONSO FLORENCE, BA ---")
    t0 = time.time()
    result = await buscar_candidatos(
        ctx,
        nome="AFONSO FLORENCE",
        uf="BA",
        limite=5,
    )
    print(result)
    print(f"  ({time.time() - t0:.1f}s)")

    # 4. Resumo by cargo/partido
    print("\n--- resumo_cargo_partido: DEPUTADO FEDERAL, PI, 2022 ---")
    t0 = time.time()
    result = await resumo_cargo_partido(
        ctx,
        cargo="DEPUTADO FEDERAL",
        uf="PI",
        ano=2022,
    )
    print(result)
    print(f"  ({time.time() - t0:.1f}s)")


async def test_tse_votacao() -> None:
    """Download tse_votacao and run a test query."""
    print("\n" + "=" * 60)
    print("  TSE VOTACAO — download + query test")
    print("=" * 60)

    from mcp_brasil.datasets.tse_votacao.tools import (
        info_tse_votacao,
        soma_votos_uf,
        top_votados_cargo,
    )

    ctx = FakeCtx()

    # 1. Check cache status
    print("\n--- info_tse_votacao ---")
    t0 = time.time()
    info = await info_tse_votacao(ctx)
    print(info)
    print(f"  ({time.time() - t0:.1f}s)")

    # 2. Top votados — DEPUTADO FEDERAL, PI, 2022
    print("\n--- top_votados_cargo: DEPUTADO FEDERAL, PI, 2022 ---")
    t0 = time.time()
    result = await top_votados_cargo(
        ctx,
        cargo="DEPUTADO FEDERAL",
        uf="PI",
        ano=2022,
        limite=10,
    )
    print(result)
    print(f"  ({time.time() - t0:.1f}s)")

    # 3. Soma votos por UF
    print("\n--- soma_votos_uf: DEPUTADO FEDERAL, 2022 ---")
    t0 = time.time()
    result = await soma_votos_uf(
        ctx,
        ano=2022,
        cargo="DEPUTADO FEDERAL",
    )
    print(result)
    print(f"  ({time.time() - t0:.1f}s)")


async def main() -> None:
    print("MCP_BRASIL_DATASETS =", os.environ.get("MCP_BRASIL_DATASETS"))
    print("This will download ~290MB (candidatos) + ~1.6GB (votacao) on first run.")

    try:
        await test_tse_candidatos()
    except Exception as e:
        print(f"\n  ERROR in tse_candidatos: {e}")
        import traceback

        traceback.print_exc()

    try:
        await test_tse_votacao()
    except Exception as e:
        print(f"\n  ERROR in tse_votacao: {e}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("  DONE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
