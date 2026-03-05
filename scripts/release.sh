#!/usr/bin/env bash
set -euo pipefail

# Read version settings from version.json
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
VERSION_FILE="$ROOT_DIR/version.json"

CURRENT_VERSION=$(python3 -c "import json; print(json.load(open('$VERSION_FILE'))['version'])")
PRERELEASE=$(python3 -c "import json; print(json.load(open('$VERSION_FILE')).get('prerelease', ''))")
BUMP=$(python3 -c "import json; print(json.load(open('$VERSION_FILE')).get('bump', 'minor'))")

IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

case "$BUMP" in
  major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
  minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
  patch) PATCH=$((PATCH + 1)) ;;
  *) echo "Invalid bump type: $BUMP"; exit 1 ;;
esac

NEW_VERSION="$MAJOR.$MINOR.$PATCH"

if [ -n "$PRERELEASE" ]; then
  TAG="v${NEW_VERSION}_${PRERELEASE}"
else
  TAG="v${NEW_VERSION}"
fi

# Update version.json with the new version
python3 -c "
import json
with open('$VERSION_FILE', 'r') as f:
    data = json.load(f)
data['version'] = '$NEW_VERSION'
with open('$VERSION_FILE', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"

echo "Bumped version: $CURRENT_VERSION -> $NEW_VERSION"
echo "Tag: $TAG"

git add "$VERSION_FILE"
git commit -m "Release $TAG"
git tag "$TAG"
echo ""
echo "Run 'git push origin main --tags' to publish."
