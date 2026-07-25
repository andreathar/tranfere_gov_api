"""
TransfereGov — Painel Web de Inteligência Parlamentar.

Aplicação FastAPI que serve a interface web interativa e
expõe a API REST para consulta de deputados, emendas, despesas,
comissões, votações e proposições.

Uso:
    uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import deputados, prefeitos, analytics, auditoria, diario, compras

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TransfereGov — Painel de Inteligência Parlamentar & Municipal",
    description="API REST para consulta de deputados, prefeitos, emendas pix, despesas CEAP, "
                "comissões, votações e proposições legislativas.",
    version="1.0.0",
)

# CORS — configurable via env var; permissive only in dev
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(","
)
allow_all = "*" in CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if allow_all else CORS_ORIGINS,
    allow_credentials=not allow_all,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Rotas da API
app.include_router(
    deputados.router,
    prefix="/api/v1/deputados",
    tags=["deputados"],
)

# Register prefeitos routes
app.include_router(
    prefeitos.router,
    prefix="/api/v1/prefeitos",
    tags=["prefeitos"],
)


# Register analytics routes
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])

# Register auditoria routes
app.include_router(auditoria.router, prefix="/api/v1/auditoria", tags=["auditoria"])

# Register diario oficial routes
app.include_router(diario.router, prefix="/api/v1/diario", tags=["diario"])

# Register compras públicas routes
app.include_router(compras.router, prefix="/api/v1/compras", tags=["compras"])

# ---------------------------------------------------------------------------
# Arquivos estáticos e frontend
# ---------------------------------------------------------------------------
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def root():
    """Serve o frontend (index.html)."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "API TransfereGov rodando. Acesse /docs para documentação."}
