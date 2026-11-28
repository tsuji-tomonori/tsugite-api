# **利用者**は、**URL**を直接指定するとき、利用できる**APIキー**を選択して呼び出すことができる

## 背景

APIクライアントの「URLを直接指定」で、利用者は接続先の認証用ヘッダーを手入力していた。

## なぜ必要か

発行済みのAPIキーを選んで呼び出せるようにし、秘密値の転記を省く。

## 決めた方針

利用者は本人の有効な個人キーや利用可能な共有キーを名前とプロジェクトで選べる。従来方式では本人のログイントークンとキーIDを使い、短期Bearer・アプリ・システム認証では選択した認証情報を短期トークンに交換する。送信時の利用権と失効状態はゲートウェイが検査する。

> 実装検証 test_manual_key_eligibility test_openapi_key_console — 本人が選べる候補と、キーの選択から応答・失効後の拒否までを確認する。

キーは初期状態では未選択とする。選択中は本人が開いているポータルの呼び出しURLにだけ認証を付ける。外部URLや手入力した認証ヘッダーとの重複は送信前に知らせる。

> 実装検証 test_manual_key_checks_destination_before_exchange — ブラウザーの送信先とヘッダーの検査を確認する。

### 受入テスト

- 受入テスト `packages/frontend/tests/test_api_client.py::test_manual_key_eligibility`
- 受入テスト `packages/frontend/tests/test_api_client.py::test_manual_key_checks_destination_before_exchange`
- 受入テスト `packages/frontend/tests/test_api_client.py::test_manual_legacy_key_uses_id`
- 受入テスト `tests/e2e/browser/test_api_docs.py::test_openapi_key_console` / `console-url-key.png`

## 却下した方針

任意の外部URLへのポータル認証情報の送信。

### 変更履歴

- 2026-11-28 認証ヘッダーの手入力を省けるよう、URL直接指定でのキー選択を追加した。
