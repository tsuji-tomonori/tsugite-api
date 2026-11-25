# **提供者**は、**API**を出品するとき、**下書き**を登録できる

## 背景

**提供者**（自チームのAPIを出品して利用条件を決める人）は、接続先と仕様を用意する。

## なぜ必要か

接続情報と操作仕様を確認してから社内に公開するため。

## 決めた方針

**API**（社内で呼び出せる業務機能のインターフェース）を登録する。**下書き**（提供者だけが確認できる公開前の掲載内容）には環境別の接続先と**OpenAPI**（HTTP APIの操作・入力・応答を記述する仕様）を保存する。

提供チームは委任された環境別の接続先を選ぶ。Lambdaには呼び出し情報を渡し、HTTPSでは必要に応じてSecrets Managerの接続先用Bearerを使う。

提供チームが委任された接続先を環境ごとに選ぶ。Lambdaには呼び出し情報を渡し、HTTPSでは必要に応じてSecrets Managerに登録した接続先用のBearerトークンを付ける。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_portal.py::test_user_flow` / `draft.png`
- 受入テスト `packages/backend/tests/test_integrations.py::test_lambda_adapter`
- 受入テスト `packages/backend/tests/test_integrations.py::test_https_adapter`
- 受入テスト `packages/backend/tests/test_integrations.py::test_lambda_adapter`
- 受入テスト `packages/backend/tests/test_integrations.py::test_https_adapter`

## 却下した方針

入力途中の商品をカタログに掲載する方法は採用しない。

### 変更履歴

- 2026-11-25 53cf6ef で検証している環境別接続先の受入条件を追加した。

### 変更履歴

- 2026-11-25 53cf6ef の接続先別の転送条件を補った。
