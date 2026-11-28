# **利用者**は、**プロジェクト**で認証情報を使い分けるとき、**APIキー**を発行できる

## 背景

**APIキー**（プロジェクトの利用権に基づき、対象APIや利用者を限定して発行するキー）には**共有キー**（同じプロジェクトのメンバーが共用するキー）と**本人限定キー**（発行対象者の資格と組み合わせて使うキー）がある。

## なぜ必要か

同じプロジェクトでも用途や利用者ごとに呼び出せる範囲を分けるため。

## 決めた方針

プロジェクトごとに複数発行できる。対象は承認済みAPI全体または指定APIとし、本人の利用権は本人限定キーで使う。従来キーの有効期間も最長60分とする。

> Quint entitlement.principalTest — 本人に限定した権利は別人・共有キー・システムから使えない。
> 実装検証 test_workspace_key_console test_scoped_keys_reach_https test_legacy_credential_inventory_and_independent_revocation — 旧キーの利用範囲や独立した失効を発行・呼び出しで確認する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_workspace_console.py::test_workspace_key_console` / `keys.png`
- 受入テスト `tests/e2e/aws/test_scoped_keys.py::test_scoped_keys_reach_https`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_entitlement_policy`
- 受入テスト `packages/backend/tests/test_required_credentials.py::test_legacy_credential_inventory_and_independent_revocation`

## 却下した方針

本人への承認を共有キーでプロジェクト全体に広げる方法は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
