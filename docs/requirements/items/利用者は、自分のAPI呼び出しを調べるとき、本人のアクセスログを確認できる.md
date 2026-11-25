# **利用者**は、自分の**API**呼び出しを調べるとき、本人の**アクセスログ**を確認できる

## 背景

同じプロジェクトの複数の人が同じ商品を呼び出す。

## なぜ必要か

本人が失敗した呼び出しを特定できるようにするため。

## 決めた方針

「アクセスログ」の一覧・詳細・ダウンロードはログインした本人の呼び出しに限定する。管理者がこの画面を開いた場合も本人の範囲を適用する。

> Quint audit.personalLogTest — 本人画面は管理権限があっても本人の記録だけを返す。
> 実装検証 test_access_log_scopes test_access_log_detail_and_support — 本人スコープが一覧・詳細・ダウンロードすべてに効くことを確認する。

### 受入テスト

- 受入テスト `packages/backend/tests/test_org_access.py::test_access_log_scopes`
- 受入テスト `tests/e2e/browser/test_requirement_flows.py::test_access_log_detail_and_support` / `log-list.png`
- 受入テスト `packages/backend/tests/test_quint_governance.py::test_log_history`

## 却下した方針

却下の記録なし。

### 変更履歴

- 2026-11-25 #39・#46 で分かれた本人用と監査用の閲覧範囲を利用者側からも追跡できるようにした。

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
