#!/usr/bin/env bash
# 使い捨てクローンとローカルの bare リモートで Git の入口から検査する。
set -euo pipefail
root=$(git rev-parse --show-toplevel)
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-$root/.venv}"
git clone --quiet --local "$root" "$tmp/work"
cd "$tmp/work"
git config --local core.hooksPath .githooks
git config --local user.name 'Hook test'
git config --local user.email 'hook-test@example.invalid'
git switch -qc hook-check
git init --quiet --bare "$tmp/remote.git"
git remote add fixture "$tmp/remote.git"

reject() {
    local reason=$1
    shift
    if "$@" >"$tmp/log" 2>&1; then
        echo "拒否されるはずの操作が成功しました。" >&2
        exit 1
    fi
    grep -Fq "$reason" "$tmp/log" || { echo "想定したフックが拒否しませんでした: $reason" >&2; exit 1; }
    if grep -Fq "$token" "$tmp/log"; then
        echo "検査ログに検出値が出力されました。" >&2
        exit 1
    fi
}

# ダミーの検出値を実行時に組み立て、空白・日本語・パス指定用の記号を含む名前を使う。
token=$(printf 'ghp_%036d' 0)
path='資格情報 [1].txt'
printf '%s\n' "$token" >"$path"
git add -- "$path"
printf 'clean\n' >"$path"
reject '機密情報' git commit -qm 'test: ステージ済みの値を検査'
git add -- "$path"
printf '%s\n' "$token" >"$path"
git commit -qm 'test: 未ステージの値は対象外'
git restore -- "$path"
reject '機密情報' git commit --allow-empty -qm 'test: 本文を検査' -m "$token"
reject 'Conventional Commits' git commit --allow-empty -qm '形式が違う件名'

# 作成と fast-forward は成功し、別名のブランチからの巻き戻し・削除は失敗する。
git push -q fixture HEAD:refs/heads/main
git commit --allow-empty -qm 'test: main を早送り'
git push -q fixture HEAD:refs/heads/main
tip=$(git rev-parse HEAD)
reject 'main の履歴' git push --force fixture HEAD~1:refs/heads/main
reject 'main の履歴' git push "--force-with-lease=refs/heads/main:$tip" fixture HEAD~1:refs/heads/main
reject 'main の削除' git push fixture :refs/heads/main
test "$(git --git-dir="$tmp/remote.git" rev-parse refs/heads/main)" = "$tip"
git push -q fixture HEAD:refs/heads/topic
git push -q --force fixture HEAD~1:refs/heads/topic
echo 'Git フックのコミット・プッシュ検査に成功しました。'
