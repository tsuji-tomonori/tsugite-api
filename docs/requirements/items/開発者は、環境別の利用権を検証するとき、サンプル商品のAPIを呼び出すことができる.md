# **開発者**は、環境別の**利用権**を検証するとき、サンプル商品の**API**を呼び出すことができる

## 背景

サンプルを含む構成では環境別の接続先から商品を試せる。

## なぜ必要か

承認された環境と商品を使い、実際の入力と応答を確認するため。

## 決めた方針

検証・準本番・本番の接続先で商品ごとのベースパスを指定する。12商品が各5つの業務操作とGET /healthを提供する。公開用OpenAPIはFastAPIの定義と一致し、別商品の操作をその商品のパスでは呼び出せない。

### 受入テスト

- 受入テスト `packages/sample_api/tests/test_products.py::test_generated_product_contracts`
- 受入テスト `packages/sample_api/tests/test_products.py::test_each_product_operation_through_lambda`
- 受入テスト `tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream`

## 却下した方針

却下の記録なし。

### 変更履歴

- 2026-11-25 #27 の在庫サンプルを #58 の12商品・3環境の構成へ更新した。
