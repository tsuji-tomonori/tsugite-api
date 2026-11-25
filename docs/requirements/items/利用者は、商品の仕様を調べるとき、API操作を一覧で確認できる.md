# **利用者**は、**商品**の仕様を調べるとき、**API操作**を一覧で確認できる

## 背景

**API操作**（OpenAPIのHTTPメソッドとパスの組み合わせ）には、操作ごとに異なる入力と応答がある。

## なぜ必要か

操作数が多い商品でも必要な呼び出し方法をすぐに確認するため。

## 決めた方針

商品画面に操作の一覧を表示する。操作名を選ぶと、その行で入力と応答の仕様を確認できる。

> 実装検証 test_publish_and_apply_from_product_page test_docs_match_openapi_operations — OpenAPIの項目を正しく表示できるかは実際の画面で確認する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_product_publication.py::test_publish_and_apply_from_product_page` / `operations.png`
- 受入テスト `packages/frontend/tests/test_required_product_views.py::test_docs_match_openapi_operations`

## 却下した方針

商品を代表する1操作だけを表示する方法は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
