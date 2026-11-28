# **利用者**は、**API操作**を試すとき、**API Docs**から呼び出しできる

## 背景

**API Docs**（商品に登録されたOpenAPIの操作を閲覧・実行する画面）には環境と認証情報の選択肢がある。

## なぜ必要か

仕様と実際の応答を同じ画面で照合するため。

## 決めた方針

許可された環境・キー・操作を選び、応答コード、本文、リクエストIDを確認できるようにする。承認済みの利用権があり、使える認証情報がまだない場合は、操作の実行時にその商品専用の個人認証情報を発行する。API Docsでは既存または発行した認証情報を使ってOAuthトークン交換を行い、短期トークンで呼び出す。サーバー側でも同じ利用権を検証し、利用者のログイントークンだけでの転送は拒否する。

> Quint entitlement.principalTest — 本人に限定した権利は別人・共有キー・システムから使えない。
> 実装検証 test_trial_uses_approved_environments_and_reuses_personal_credential — 実際の画面・トークン交換のエラー形式・利用申請への導線を確認する。

操作の仕様と実行欄を横に並べ、狭い画面では縦に並べる。OpenAPI原本はJSONでダウンロードできる。利用申請は専用画面で行う。入力欄には必須・任意を示し、送信中は実行中の文言を表示し、その右にボタンの文字と同じ色の砂時計を添える。実行後はURLと本文を反映したcurlコマンドをコピーできる。認証トークンはシェル変数で参照する。

> 実装検証 test_api_docs_runs_and_copies_curl — 実際の画面・トークン交換のエラー形式・利用申請への導線を確認する。

リクエスト本文、レスポンス、データモデルの各スキーマを整形したJSONで表示する。ライト・ダークの両テーマでキー、文字列、数値、真偽値、nullを色分けし、コピー時も元の字下げと内容を保つ。

> 実装検証 test_schema_block_preserves_json_tokens — 表示した文字列と色分けの単位を照合する。

トークン交換で未対応の方式を指定した場合はHTTP 400と `unsupported_grant_type`、トークン種別が不正な場合はHTTP 400と `invalid_request` を返す。利用者は応答の `error_description` で入力のどこを見直すか確認できる。

> 実装検証 test_oauth_exchange_form_accepts_only_documented_token_types — 実際の画面・トークン交換のエラー形式・利用申請への導線を確認する。

### 受入テスト

- 受入テスト `packages/frontend/tests/test_components.py::test_schema_block_preserves_json_tokens`
- 受入テスト `tests/e2e/browser/test_api_docs.py::test_openapi_key_console` / `specification.png`

- 受入テスト `packages/backend/tests/test_required_credentials.py::test_oauth_exchange_form_accepts_only_documented_token_types`

- 受入テスト `packages/frontend/tests/test_required_product_trial.py::test_api_docs_runs_and_copies_curl`

- 受入テスト `tests/e2e/browser/test_api_docs.py::test_openapi_key_console` / `busy-hourglass.png`
- 受入テスト `tests/e2e/browser/test_api_docs.py::test_openapi_key_console` / `response.png`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_entitlement_policy`
- 受入テスト `packages/frontend/tests/test_api_client.py::test_trial_uses_approved_environments_and_reuses_personal_credential`

## 却下した方針

画面での操作選択だけで認可を完了する方法は採用しない。

### 変更履歴

- 2026-11-25 OAuth交換に失敗した際の入力修正に必要な応答と、操作実行の受入テストを明記した。

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。

- 2026-11-28 APIカタログでスキーマの項目名と値を読み分けられるようにした。
- 2026-11-28 ライト・ダーク両方の配色に合わせるため、待機中の砂時計をボタンの文字と同じ色の線画に統一した。
