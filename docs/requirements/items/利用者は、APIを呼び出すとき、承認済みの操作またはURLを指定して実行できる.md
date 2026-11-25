# **利用者**は、**API**を呼び出すとき、承認済みの操作または**URL**を指定して実行できる

## 背景

利用申請を承認された後、利用者は対象のプロジェクトと環境でAPIの応答を確認する。接続先の**URL**（呼び出すリソースの場所を示す文字列）が分かる場合は直接指定できる。

## なぜ必要か

OpenAPIの操作と本人の認証情報を使うことで、URLの組み立てやトークンの転記を省ける。

## 決めた方針

「APIクライアント」で承認済みの商品を選ぶと、その時点のOpenAPIから操作と入力欄を表示する。実行時にゲートウェイが本人・環境・操作の権限を確認する。URLを直接指定する場合はブラウザーから送信し、接続先用に入力したヘッダーを使う。

> Quint grants.scopeTest credentials.operationsTest — 商品・環境・プロジェクトが異なる呼び出しは転送しない。
> 実装検証 test_openapi_key_console — ブラウザーの直接送信時に使用するヘッダーとリダイレクトの扱いを確認する。

URL直接指定ではポータルの資格情報を自動送信せず、リダイレクトを拒否する。応答のHTTPステータスと本文を表示する。

> 実装検証 test_manual_request_uses_only_entered_headers — ブラウザーの直接送信時に使用するヘッダーとリダイレクトの扱いを確認する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_api_docs.py::test_openapi_key_console` / `console-oauth.png`
- 受入テスト `tests/e2e/browser/test_api_docs.py::test_openapi_key_console` / `console-url.png`
- 受入テスト `packages/frontend/tests/test_api_client.py::test_manual_request_uses_only_entered_headers`
- 受入テスト `packages/backend/tests/test_quint_grants.py::test_grant_history`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_operation_policy`
- 受入テスト `packages/frontend/tests/test_required_product_views.py::test_console_shows_approved_operations_and_manual_url`

## 却下した方針

入力した任意のURLにポータルのトークンを自動送信すると、利用者の認証情報が別のサービスに渡ってしまう。

### 変更履歴

- 2026-11-25 #34 の直接送信で使う資格情報の範囲を明記した。

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
