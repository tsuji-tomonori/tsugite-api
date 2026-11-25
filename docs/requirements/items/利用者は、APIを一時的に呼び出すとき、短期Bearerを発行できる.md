# **利用者**は、**API**を一時的に呼び出すとき、**短期Bearer**を発行できる

## 背景

**短期Bearer**（ログイン中の利用者がすぐ使えるアクセストークンを得る認証方式）は手動の検証にも使う。

## なぜ必要か

利用のたびに長期間有効な資格を配布せずに済むようにするため。

## 決めた方針

ポータルで有効期間と更新開始時刻を選ぶ。API Docsでも必要な時点で取得する。

> Quint credentials.lifetimeTest — 実行時点の最短の上限に達した瞬間から拒否する。
> 実装検証 test_credentials_console test_issue_use_and_retire_credentials — 発行画面で指定した更新時刻を実際のトークンの応答と照合する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_credentials_console.py::test_credentials_console` / `credentials.png`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_operation_policy`
- 受入テスト `packages/backend/tests/test_required_credentials.py::test_issue_use_and_retire_credentials`

## 却下した方針

短期の呼び出し用に無期限のBearerを配る方法は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
