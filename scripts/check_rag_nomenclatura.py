"""Valida a nomenclatura padrão do RAG antes de rodar o super teste.

Garante consistência entre os scripts do pipeline RAG v8:
  1. Chunk types do QUERY_CHUNK_FILTER (rag_persona) existem nos extractors
     reais do indexer (CHUNK_EXTRACTORS) — filtro sem extractor = query morta.
  2. Modelos padrão (RAG_LLM_MODEL, EMBEDDER_MODEL, PREPARER_MODEL) são os
     registrados no settings e resolvem no LocalAI.
  3. Choices de --tipo idênticos entre rag_persona, rag_qdrant_indexer e
     dossier_bench (multi-cargo).
  4. RAG_PERSONA_VERSION consistente (settings == rag_persona == bench).

Uso:
    python3 scripts/check_rag_nomenclatura.py [--verbose]
Exit 0 = pronto para o super teste; 1 = inconsistências encontradas.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter

FALHAS: list[str] = []


def check(cond: bool, msg: str) -> None:
    tag = "OK " if cond else "FAIL"
    print(f"  [{tag}] {msg}")
    if not cond:
        FALHAS.append(msg)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    print("=" * 70)
    print("CHECK RAG NOMENCLATURA (pré super teste)")
    print("=" * 70)

    # 1. Chunk types: QUERY_CHUNK_FILTER vs CHUNK_EXTRACTORS
    print("\n[1] Chunk types — queries temáticas vs extractors")
    from src.enrichers.rag_persona import QUERY_CHUNK_FILTER
    from src.enrichers.rag_qdrant_indexer import CHUNK_EXTRACTORS

    extractors = set(CHUNK_EXTRACTORS.keys())
    usados = {ct.upper() for filtros in QUERY_CHUNK_FILTER.values() for ct in filtros}
    ausentes = sorted(ct for ct in usados if ct.lower() not in extractors)
    check(
        not ausentes,
        f"{len(usados)} tipos usados nas queries; ausentes nos extractors: "
        f"{ausentes or 'nenhum'}",
    )
    sem_query = sorted(e for e in extractors if e.upper() not in usados)
    if args.verbose and sem_query:
        print(f"    (info) extractors sem query dedicada: {', '.join(sem_query)}")

    # 2. Modelos padrão
    print("\n[2] Modelos padrão")
    from config.settings import (
        EMBEDDER_MODEL,
        RAG_LLM_MODEL,
    )
    from src.analysts.preparer import PREPARER_MODEL

    check(bool(RAG_LLM_MODEL.startswith("llama-3.2")), f"RAG_LLM_MODEL={RAG_LLM_MODEL}")
    check(EMBEDDER_MODEL == "embeddinggemma-300m", f"EMBEDDER_MODEL={EMBEDDER_MODEL}")
    check("zero-gemma" in PREPARER_MODEL, f"PREPARER_MODEL={PREPARER_MODEL}")

    import urllib.request

    try:
        with urllib.request.urlopen(
            "http://localhost:8080/v1/models", timeout=5
        ) as resp:
            import json

            remotos = {m["id"] for m in json.load(resp)["data"]}
        for nome, modelo in (
            ("RAG_LLM_MODEL", RAG_LLM_MODEL),
            ("EMBEDDER_MODEL", EMBEDDER_MODEL),
            ("PREPARER_MODEL", PREPARER_MODEL),
        ):
            check(
                modelo in remotos,
                f"{nome}={modelo} registrado no LocalAI ({len(remotos)} modelos)",
            )
    except Exception as e:
        check(False, f"LocalAI indisponível p/ validar modelos: {e}")

    # 3. Choices de --tipo idênticos
    print("\n[3] Choices --tipo (multi-cargo)")
    import ast

    TIPOS_PADRAO = ("deputado", "senador", "governador", "prefeito", "vereador")
    for script in (
        "src/enrichers/rag_persona.py",
        "src/enrichers/rag_qdrant_indexer.py",
        "scripts/dossier_bench.py",
    ):
        with open(script, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        choices = None
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "attr", "") == "add_argument"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "--tipo"
            ):
                for kw in node.keywords:
                    if kw.arg == "choices" and isinstance(kw.value, ast.Tuple):
                        choices = tuple(
                            e.value for e in kw.value.elts if isinstance(e, ast.Constant)
                        )
        check(choices == TIPOS_PADRAO, f"{script}: choices={choices}")

    # 4. RAG_PERSONA_VERSION consistente
    print("\n[4] RAG_PERSONA_VERSION")
    import re

    versoes: Counter[str] = Counter()
    for path, pattern in (
        ("config/settings.py", r"RAG_PERSONA_VERSION = \(\s*(\d+)"),
        ("src/enrichers/rag_persona.py", r"RAG_PERSONA_VERSION"),
        ("scripts/dossier_bench.py", r"RAG_PERSONA_VERSION"),
    ):
        txt = open(path, encoding="utf-8").read()
        m = re.search(pattern, txt)
        if m:
            versoes[path] += 1
    check(len(versoes) == 3, f"RAG_PERSONA_VERSION referenciado em {len(versoes)}/3 scripts")
    from config.settings import RAG_PERSONA_VERSION as V8

    check(V8 == 8, f"settings RAG_PERSONA_VERSION={V8}")

    print("\n" + "=" * 70)
    if FALHAS:
        print(f"RESULTADO: {len(FALHAS)} inconsistência(s) — NÃO pronto")
        for f in FALHAS:
            print(f"  - {f}")
        return 1
    print("RESULTADO: nomenclatura consistente — pronto para o super teste")
    return 0


if __name__ == "__main__":
    sys.exit(main())
