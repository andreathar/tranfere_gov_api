"""Resources: templates e normas de redação oficial.

Resources são dados que o LLM carrega como contexto.
O client MCP pode ler esses resources para entender
a estrutura e as normas de cada tipo de documento.
"""

from __future__ import annotations

from pathlib import Path

TEMPLATES_DIR = Path(__file__).parent / "templates"
NORMAS_DIR = Path(__file__).parent / "normas"


def _load_file(directory: Path, filename: str) -> str:
    """Carrega um arquivo de template ou norma."""
    filepath = directory / filename
    if not filepath.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")
    return filepath.read_text(encoding="utf-8")


# === Templates de documentos ===


def get_template_oficio() -> str:
    """Template oficial para Ofício (padrão ofício — 3ª edição)."""
    return _load_file(TEMPLATES_DIR, "oficio.md")


def get_template_memorando() -> str:
    """Template oficial para Memorando interno."""
    return _load_file(TEMPLATES_DIR, "memorando.md")


def get_template_despacho() -> str:
    """Template oficial para Despacho administrativo."""
    return _load_file(TEMPLATES_DIR, "despacho.md")


def get_template_portaria() -> str:
    """Template oficial para Portaria."""
    return _load_file(TEMPLATES_DIR, "portaria.md")


def get_template_parecer() -> str:
    """Template oficial para Parecer técnico."""
    return _load_file(TEMPLATES_DIR, "parecer.md")


def get_template_nota_tecnica() -> str:
    """Template oficial para Nota Técnica."""
    return _load_file(TEMPLATES_DIR, "nota_tecnica.md")


def get_template_ata() -> str:
    """Template oficial para Ata de reunião."""
    return _load_file(TEMPLATES_DIR, "ata.md")


# === Normas de redação ===


def get_manual_redacao() -> str:
    """Resumo das normas do Manual de Redação da Presidência da República (3ª ed.)."""
    return _load_file(NORMAS_DIR, "manual_redacao.md")


def get_pronomes_tratamento() -> str:
    """Tabela de pronomes de tratamento oficiais."""
    return _load_file(NORMAS_DIR, "pronomes.md")


def get_fechos_oficiais() -> str:
    """Fechos e saudações para correspondência oficial."""
    return _load_file(NORMAS_DIR, "fechos.md")
