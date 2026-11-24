#!/usr/bin/env bash
# main に取り込まれた各 PR の Verify 成果物を evidence ブランチに保存する。
set -euo pipefail

archive=$(mktemp -d)
if git show-ref --verify --quiet refs/remotes/origin/evidence; then
  git worktree add --detach "$archive" refs/remotes/origin/evidence
  previous=$(git -C "$archive" log -1 --format='%(trailers:key=Source-merge,valueonly)')
  git rev-parse --verify "${previous}^{commit}" >/dev/null
  if git merge-base --is-ancestor "$GITHUB_SHA" "$previous"; then
    echo "この版は保存済みです。"
    exit 0
  fi
  git merge-base --is-ancestor "$previous" "$GITHUB_SHA"
else
  git worktree add --detach "$archive" "$GITHUB_SHA"
  git -C "$archive" switch --orphan evidence
  first=$(git log --first-parent --diff-filter=A --format=%H "$GITHUB_SHA" -- .github/workflows/evidence.yml)
  previous=$(git rev-parse "${first}^1")
fi

# 後続ジョブが先に動いた場合や再実行時も、未保存のマージを古い順に処理する。
merges=$(git rev-list --reverse --first-parent --merges "$previous..$GITHUB_SHA")
for merge in $merges; do
  head=$(git rev-parse "${merge}^2")
  run=$(gh run list --repo "$GITHUB_REPOSITORY" --workflow check.yml --commit "$head" \
    --event pull_request --status success --limit 1 --json databaseId --jq '.[0].databaseId // empty')
  if [[ -z "$run" ]]; then
    echo "::error::Verify の成功記録が見つかりません ($head)"
    exit 1
  fi

  snapshot=$(mktemp -d)
  gh run download "$run" --repo "$GITHUB_REPOSITORY" --name requirement-evidence --dir "$snapshot"
  grep -Fxq "対象コミット　\`$head\`" "$snapshot/report.md"
  test -s "$snapshot/requirements.xml"
  test -d "$snapshot/items"

  # 対象外となった要件の旧画像などが今回の証跡に混ざらないよう、毎回入れ替える。
  rm -rf -- "$archive/evidence"
  mv "$snapshot" "$archive/evidence"
  git -C "$archive" add -A -- evidence
  git -C "$archive" -c user.name='github-actions[bot]' \
    -c user.email='41898282+github-actions[bot]@users.noreply.github.com' \
    commit -m "docs: 要件別の検証証跡を保存 (${merge:0:12})" \
    -m "$GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$run" \
    -m "Source-merge: $merge"
  git -C "$archive" push origin HEAD:refs/heads/evidence
done
