#!/usr/bin/env bash
# skills_audit.sh — Auditoria do ecossistema de skills (fonte única + symlinks)
#
# Semântica (regra de ouro — ver AGENTS.md "Topologia de Skills"):
#   - Skill COMPARTILHADA (canônica em ~/.agents/skills sem `agent-specific: true`)
#     deve ser symlink em cada store de agente. Cópia direta = DRIFT.
#   - Skill agent-specific (`agent-specific: true` no frontmatter da canônica)
#     pode ser cópia direta legítima em stores de agentes (ex.: plannotator).
#   - Skill project-specific (ex.: .gemini/skills do transferegov, variantes
#     plannotator do Unity) NÃO duplica canônico → é legítima e pode ser
#     git-tracked no repo do projeto.
#
# Verifica:
#   1. Symlinks por store de agente (~/.claude/skills, ~/.hermes/skills) resolvem
#      e apontam para o store canônico ~/.agents/skills; cópias diretas de skill
#      compartilhada são flagradas como drift.
#   2. md5 de SKILL.md idêntico entre canônica e cada symlink (zero drift).
#   3. Diretórios de skills git-tracked em repos: flagrados apenas se duplicam
#      skills do canônico (compartilhadas OU agent-specific) — cópia em repo de
#      skill que já existe em user-level viola a regra de ouro.
#
# Uso:
#   scripts/skills_audit.sh                 # auditoria completa (default)
#   scripts/skills_audit.sh --md5           # só comparação md5
#   scripts/skills_audit.sh --symlinks      # só resolução de symlinks
#   scripts/skills_audit.sh --repos         # só drift git-tracked
#
# Exit code: 0 = tudo OK; 1 = problemas encontrados.

set -u

CANON="/home/athar/.agents/skills"
AGENT_STORES=(
  "/home/athar/.claude/skills"
  "/home/athar/.hermes/skills"
)

# Repos onde skills git-tracked NÃO devem duplicar o user-level
REPOS=(
  "/mnt/data/Projects_SSD/tranfere_gov_api"
  "/mnt/data/Projects_SSD/Unity_Projects/Unity_Linux_LLM"
)

# Diretórios de skills candidatos a drift dentro de repos
SKILL_DIRS=(
  "agent/skills"
  "data/skills"
  ".agents/skills"
  ".gemini/skills"
)

MODE_ALL=1
MODE_MD5=0
MODE_SYMLINKS=0
MODE_REPOS=0

for arg in "$@"; do
  case "$arg" in
    --md5) MODE_ALL=0; MODE_MD5=1 ;;
    --symlinks) MODE_ALL=0; MODE_SYMLINKS=1 ;;
    --repos) MODE_ALL=0; MODE_REPOS=1 ;;
    -h|--help) head -35 "$0"; exit 0 ;;
    *) echo "argumento desconhecido: $arg" >&2; exit 2 ;;
  esac
done

# shellcheck disable=SC2034
if [[ "$MODE_ALL" -eq 1 ]]; then MODE_MD5=1; MODE_SYMLINKS=1; MODE_REPOS=1; fi

FAIL=0

# is_shared <skill_dir>: 0 se a skill é compartilhada (deve ser symlink),
# 1 se é agent-specific (cópia direta permitida) ou canônica inexistente.
is_shared() {
  local skill_dir="$1"
  [[ -f "$skill_dir/SKILL.md" ]] || return 1
  if grep -qE '^agent-specific:[[:space:]]*true' "$skill_dir/SKILL.md"; then
    return 1
  fi
  return 0
}

echo "== skills_audit.sh =="
echo "canônico: $CANON"
echo

# ---------- 1. Resolução de symlinks ----------
if [[ "$MODE_SYMLINKS" -eq 1 ]]; then
  echo "== [1/3] Symlinks por store =="
  for store in "${AGENT_STORES[@]}"; do
    [[ -d "$store" ]] || { echo "  ! store inexistente: $store"; FAIL=1; continue; }
    count=0
    bad=0
    while IFS= read -r entry; do
      [[ -z "$entry" ]] && continue
      name="$(basename "$entry")"
      count=$((count + 1))
      if [[ -L "$entry" ]]; then
        resolved="$(readlink -f "$entry")"
        if [[ "$resolved" != "$CANON"/* ]]; then
          echo "  ! symlink fora do canônico: $name -> $(readlink "$entry")"
          bad=$((bad + 1))
        fi
      elif [[ -d "$entry" ]]; then
        if [[ -d "$CANON/$name" ]] && is_shared "$CANON/$name"; then
          echo "  ! DRIFT: $name — cópia direta de skill compartilhada (deveria ser symlink)"
          bad=$((bad + 1))
        fi
      fi
    done < <(find "$store" -mindepth 1 -maxdepth 1 \( -type l -o -type d \) | sort)
    echo "  $store: $count entradas, $bad fora do padrão"
    [[ "$bad" -gt 0 ]] && FAIL=1
  done
  echo
fi

# ---------- 2. md5 canônica vs symlinks ----------
if [[ "$MODE_MD5" -eq 1 ]]; then
  echo "== [2/3] md5 canônica vs symlinks (drift) =="
  md5_fail=0
  checked=0
  for store in "${AGENT_STORES[@]}"; do
    [[ -d "$store" ]] || continue
    for skill in "$store"/*; do
      [[ -L "$skill" ]] || continue
      name="$(basename "$skill")"
      canon_skill="$CANON/$name"
      [[ -f "$canon_skill/SKILL.md" ]] || { echo "  ! canônica ausente: $name"; md5_fail=1; continue; }
      if [[ -f "$skill/SKILL.md" ]]; then
        canon_md5="$(md5sum "$canon_skill/SKILL.md" | awk '{print $1}')"
        link_md5="$(md5sum "$skill/SKILL.md" | awk '{print $1}')"
        checked=$((checked + 1))
        if [[ "$canon_md5" != "$link_md5" ]]; then
          echo "  ! DRIFT: $name (canônica $canon_md5 ≠ symlink $link_md5)"
          md5_fail=1
        fi
      else
        echo "  ! SKILL.md inacessível via symlink: $name"
        md5_fail=1
      fi
    done
  done
  echo "  $checked symlinks com SKILL.md idêntico à canônica"
  [[ "$md5_fail" -gt 0 ]] && FAIL=1
  echo
fi

# ---------- 3. Drift git-tracked em repos ----------
if [[ "$MODE_REPOS" -eq 1 ]]; then
  echo "== [3/3] Skills git-tracked em repos (regra de ouro) =="
  for repo in "${REPOS[@]}"; do
    [[ -d "$repo/.git" ]] || { echo "  ! repo inexistente: $repo"; continue; }
    hits=0
    for sdir in "${SKILL_DIRS[@]}"; do
      if git -C "$repo" ls-files --error-unmatch "$sdir" >/dev/null 2>&1; then
        for name in "$repo/$sdir"/*/; do
          [[ -d "$name" ]] || continue
          base="$(basename "$name")"
          if [[ -d "$CANON/$base" ]]; then
            echo "  ! $repo: $sdir/$base duplica skill do user-level ($CANON/$base)"
            hits=$((hits + 1))
          fi
        done
      fi
    done
    [[ "$hits" -eq 0 ]] && echo "  ok: $repo — nenhum dir de skills tracked duplicando user-level"
    [[ "$hits" -gt 0 ]] && FAIL=1
  done
  echo
fi

if [[ "$FAIL" -eq 0 ]]; then
  echo "RESULTADO: OK — ecossistema de skills consistente."
  exit 0
else
  echo "RESULTADO: PROBLEMAS ENCONTRADOS (ver acima)." >&2
  exit 1
fi
