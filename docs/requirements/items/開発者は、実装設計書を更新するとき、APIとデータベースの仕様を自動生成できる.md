# **開発者**は、**実装設計書**を更新するとき、**API**とデータベースの仕様を自動生成できる

## 背景

**開発者**（継手APIの実装・文書・検証を保守する人）が参照する設計は、実装変更に追随する必要がある。

## なぜ必要か

APIの入出力やデータ操作と設計書の食い違いを減らすため。

## 決めた方針

**実装設計書**（APIごとの入力・応答、データ定義、CRUDをまとめた文書）はOpenAPI、モデル、ソースの構文解析から生成する。和名は定義元で記述し、テーブルとAWSサービスのCRUD表を分ける。

### 受入テスト

- 受入テスト `packages/tools/tests/test_design.py::test_all_routes_inputs_outputs_and_cleanup`
- 受入テスト `packages/tools/tests/test_design.py::test_crud_matrices_cover_all_routes_and_match_per_api_evidence`

## 却下した方針

文書用の対応表を別に保守する方法や、正規表現でコードを解析する方法は採用しない。

### 変更履歴

- 2026-11-25 開発ツールとアーキテクチャテストをパッケージ構成に合わせて移設したため、受入テストの参照先を更新した。
