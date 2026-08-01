#!/usr/bin/env python3
"""Guarda de segredos e dados pessoais para commits (pre-commit).

Verifica arquivos staged (ou passados como argumento) e aborta o commit se
encontrar:

  1. Chaves privadas (BEGIN * PRIVATE KEY).
  2. Tokens/segredos de alta confiança (GitHub, OpenAI, AWS, Google, Slack...).
  3. CPF/CNPJ **válidos** (passam no dígito verificador) — exemplos fictícios
     como 12.345.678/0001-90 (checksum inválido) são permitidos.

Uso:
    python3 scripts/check_secrets.py                # arquivos staged
    python3 scripts/check_secrets.py arquivo.py ... # arquivos explícitos

Exit code 0 = ok; 1 = violações encontradas.

Convenção do projeto: PT-BR em comentários/logs. Rodar com .venv ativado.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Padrões de segredo de alta confiança (evita falsos positivos de "password="
# em código, que normalmente referencia variáveis de ambiente).
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("chave privada", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("GitHub token (ghp_)", re.compile(r"\bghp_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained (github_pat_)", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("OpenAI API key (sk-)", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("Google API key (AIza)", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("Slack token (xox)", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("Heroku API key", re.compile(r"\b(?:API_KEY|HEROKU_API_KEY)\s*=\s*[0-9a-fA-F]{32}\b")),
    ("JWT (eyJ)", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
]

# Segredos já vazados e purgados do histórico — re-incluir deve falhar no commit.
# NOTA: nunca guardar aqui o valor literal de uma credencial real (não queremos
# o segredo em texto puro no repositório). O formato base64(usuario:senha) usado
# pelo DataJud/CNJ é coberto pela heurística `_detect_base64_creds`.
KNOWN_LEAKS: list[tuple[str, str]] = []

# Arquivos/prefixos que nunca devem conter credenciais (não é allowlist — é
# apenas para ignorar binários e o próprio script).
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".xlsx", ".ipynb"}
# O próprio script contém os segredos conhecidos (para detectá-los) — auto-excluir.
SKIP_PATHS = {"scripts/check_secrets.py"}

# base64(usuario:senha) — formato usado por DataJud/CNJ e vários serviços.
# Sem `\b` no final: `=` não é caractere de palavra, então o boundary quebraria
# a detecção em strings com padding (ex.: "...dw==" com aspas na sequência).
RE_B64_CRED = re.compile(r"\b[A-Za-z0-9+/]{16,}={1,2}")


def _detect_base64_creds(linha: str) -> bool:
    """Flags base64 que decodifica para 'usuario:senha' (credencial embutida)."""
    import base64

    for token in RE_B64_CRED.findall(linha):
        try:
            decodificado = base64.b64decode(token, validate=False).decode("utf-8", errors="ignore")
        except Exception:
            continue
        if ":" in decodificado and not any(ch.isspace() for ch in decodificado):
            return True
    return False

RE_CPF = re.compile(r"\b(\d{3})\.(\d{3})\.(\d{3})-(\d{2})\b")
RE_CNPJ = re.compile(r"\b(\d{2})\.(\d{3})\.(\d{3})/(\d{4})-(\d{2})\b")


def _only_digits(n: str) -> str:
    return re.sub(r"\D", "", n)


def _valida_cpf(cpf: str) -> bool:
    """Valida os dois dígitos verificadores do CPF (algoritmo da Receita Federal)."""
    if len(set(cpf)) == 1:
        return False
    for peso_inicial in (10, 11):
        soma = sum(int(cpf[i]) * (peso_inicial - i) for i in range(peso_inicial - 1))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(cpf[peso_inicial - 1]):
            return False
    return True


def _valida_cnpj(cnpj: str) -> bool:
    """Valida os dois dígitos verificadores do CNPJ."""
    if len(set(cnpj)) == 1:
        return False
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(int(cnpj[i]) * pesos_1[i] for i in range(12))
    resto1 = soma1 % 11
    dv1 = 0 if resto1 < 2 else 11 - resto1
    if dv1 != int(cnpj[12]):
        return False
    soma2 = sum(int(cnpj[i]) * pesos_2[i] for i in range(13))
    resto2 = soma2 % 11
    dv2 = 0 if resto2 < 2 else 11 - resto2
    return dv2 == int(cnpj[13])


def _arquivos_alvo(args: list[str]) -> list[Path]:
    if args:
        return [Path(a) for a in args]
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [Path(p) for p in out.stdout.splitlines() if p.strip()]


def _checar_arquivo(path: Path) -> list[str]:
    if str(path) in SKIP_PATHS:
        return []
    if path.suffix.lower() in SKIP_SUFFIXES:
        return []
    try:
        conteudo = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    violacoes: list[str] = []

    for nome, padrao in SECRET_PATTERNS:
        for i, linha in enumerate(conteudo.splitlines(), 1):
            if padrao.search(linha):
                violacoes.append(f"  {path}:{i} — possível {nome}")

    # Segredos conhecidos (já vazados) e credenciais base64(usuario:senha).
    for i, linha in enumerate(conteudo.splitlines(), 1):
        for nome, segredo in KNOWN_LEAKS:
            if segredo in linha:
                violacoes.append(f"  {path}:{i} — {nome} (não reintroduzir!)")
        if _detect_base64_creds(linha):
            violacoes.append(f"  {path}:{i} — credencial base64(usuario:senha) embutida")

    # CPF/CNPJ — só marca se o dígito verificador for VÁLIDO (dado real).
    for i, linha in enumerate(conteudo.splitlines(), 1):
        for m in RE_CPF.finditer(linha):
            cpf = _only_digits(m.group(0))
            if _valida_cpf(cpf):
                violacoes.append(f"  {path}:{i} — CPF real detectado: {m.group(0)}")
        for m in RE_CNPJ.finditer(linha):
            cnpj = _only_digits(m.group(0))
            if _valida_cnpj(cnpj):
                violacoes.append(f"  {path}:{i} — CNPJ real detectado: {m.group(0)}")

    return violacoes


def main() -> int:
    alvos = _arquivos_alvo(sys.argv[1:])
    if not alvos:
        print("check_secrets: nenhum arquivo staged. OK.")
        return 0

    violacoes: list[str] = []
    for p in alvos:
        if p.is_file():
            violacoes.extend(_checar_arquivo(p))

    if violacoes:
        print("check_secrets: VIOLAÇÕES ENCONTRADAS — commit abortado:")
        print("\n".join(violacoes))
        print(
            "\nAção: remova o segredo/dado do arquivo e refaça o stage. "
            "Se for um exemplo intencional, use um valor de checksum inválido "
            "(ex.: CNPJ 12.345.678/0001-90)."
        )
        return 1

    print(f"check_secrets: ok ({len(alvos)} arquivo(s) verificados, sem segredos).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
