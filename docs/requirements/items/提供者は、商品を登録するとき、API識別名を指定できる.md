# **提供者**は、**商品**を登録するとき、**API識別名**を指定できる

## 背景

**API識別名**（呼び出しURLで商品を特定する、設定後も変わらない名前）は、提供者が決める。

## なぜ必要か

利用者がURLから呼び出し対象を判断し、設定ファイルや手順書に記載できるようにする。

## 決めた方針

登録時に半角小文字の英字で始まる名前を指定する。数字とハイフンを含められ、全商品で一意とする。登録済みの商品にも初回に限り設定でき、従来のUUID付きURLと承認済みの利用権はそのまま使える。

> 実装検証 test_api_slug_is_unique_and_fixed test_existing_api_keeps_grants_when_named test_user_flow — 識別名の一意制約、使用文字、既存URLとの互換性をDB・HTTPで確認する。

### 受入テスト

- 受入テスト `packages/backend/tests/test_catalog.py::test_api_slug_is_unique_and_fixed`
- 受入テスト `packages/backend/tests/test_catalog.py::test_existing_api_keeps_grants_when_named`
- 受入テスト `tests/e2e/browser/test_portal.py::test_user_flow` / `06-invoked.png`

## 却下した方針

表示上の名称をURLに直接使うと、名称変更で呼び出し先が変わるため採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
