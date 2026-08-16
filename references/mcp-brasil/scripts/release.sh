#!/usr/bin/env bash
# release.sh — Bump version, generate changelog, tag, and push.
# Usage: ./scripts/release.sh patch|minor|major
set -euo pipefail

BUMP_TYPE="${1:?Usage: $0 patch|minor|major}"

# Ensure clean working tree
if [[ -n "$(git status --porcelain)" ]]; then
    echo "ERROR: Working directory not clean. Commit or stash changes first."
    exit 1
fi

# Ensure on main branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [[ "$BRANCH" != "main" ]]; then
    echo "ERROR: Must be on 'main' branch (currently on '$BRANCH')."
    exit 1
fi

# Bump version
uv version --bump "$BUMP_TYPE"
NEW_VERSION=$(uv version)
echo "==> Bumped to v$NEW_VERSION"

# Generate changelog (if git-cliff is available)
if command -v git-cliff &>/dev/null; then
    git-cliff --tag "v$NEW_VERSION" -o CHANGELOG.md
    echo "==> Generated CHANGELOG.md"
    CHANGELOG_FILES="CHANGELOG.md"
else
    echo "==> git-cliff not found, skipping changelog generation"
    echo "    Install: brew install git-cliff"
    CHANGELOG_FILES=""
fi

# Commit version bump + changelog
git add pyproject.toml uv.lock $CHANGELOG_FILES
git commit -m "chore(release): v$NEW_VERSION"

# Create annotated tag
git tag -a "v$NEW_VERSION" -m "Release v$NEW_VERSION"

echo "==> Created tag v$NEW_VERSION"
echo ""
echo "Ready to push. Run:"
echo "  git push origin main --follow-tags"
echo ""
echo "Or to also publish to PyPI:"
echo "  git push origin main --follow-tags && uv build && uv publish"
