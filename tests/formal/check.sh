#!/usr/bin/env bash
# 有限モデルの不変条件、全名前付き操作列と本番コードの観測結果を検証する。
set -euo pipefail
root=$(git rev-parse --show-toplevel)
cd "$root"
quint="$root/tests/formal/node_modules/.bin/quint"
out="$root/artifacts/formal"
mkdir -p "$out"
python3 tests/formal/document.py --quint "$quint" --check
python3 tests/formal/generate.py --quint "$quint"
for spec in "$root"/tests/formal/*.qnt; do
    model=$(basename "$spec" .qnt)
    mkdir -p "$out/$model"
    (cd "$out/$model" && "$quint" verify "$spec" --backend=tlc --invariant=safe) > "$out/$model.log" 2>&1 || {
        cat "$out/$model.log"
        exit 1
    }
done
FORMAL_COVERAGE_REPORT="$out/coverage.md" uv run --locked --package tsugite-backend --group dev python -m pytest -q tests/formal/test_policy_parser.py tests/architecture/core/test_formal_contracts.py packages/backend/tests/test_quint*.py --junitxml="$out/replay.xml"
