#!/usr/bin/env bash
# Construit une version de démonstration sans modifier les sources du dépôt.
set -euo pipefail
cd "$(dirname "$0")/.."
version="${1:?Usage: scripts/build-api-version.sh VERSION [IMAGE]}"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    printf 'Version attendue : MAJEURE.MINEURE.CORRECTIF\n' >&2
    exit 1
fi
image="${2:-nicolasbellina/taskflow-api:$version}"
context_dir="$(mktemp -d)"
trap 'rm -rf "$context_dir"' EXIT
cp api/Dockerfile api/.dockerignore api/package.json api/package-lock.json "$context_dir/"
cp -R api/src "$context_dir/src"
python3 - "$context_dir" "$version" <<'PY'
from pathlib import Path
import json, sys
root = Path(sys.argv[1])
version = sys.argv[2]
for name in ('package.json', 'package-lock.json'):
    path = root / name
    data = json.loads(path.read_text())
    data['version'] = version
    if name == 'package-lock.json':
        data['packages']['']['version'] = version
    path.write_text(json.dumps(data, indent=2) + '\n')
PY
docker build --progress=plain -t "$image" "$context_dir"
docker run --rm --entrypoint node "$image" \
    -p 'JSON.parse(require("fs").readFileSync("/app/package.json", "utf8")).version'
