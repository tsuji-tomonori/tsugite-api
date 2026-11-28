# **提供者**は、**利用者**の実行範囲を制限するとき、**API操作**を指定できる

## 背景

同じAPIでも参照と更新で許可する利用者が異なる。

## なぜ必要か

商品単位の承認より細かく、利用者ごとの操作を制御するため。

## 決めた方針

提供者が利用者ごとにメソッドとパスを選ぶ。全解除で全操作を停止し、個別設定を解除すれば承認済みの範囲を継承する。

> Quint credentials.operationsTest — 利用者と認証情報の両方が許可した操作だけを実行する。
> 実装検証 test_person_operation_console test_subscriber_operation_policy_is_scoped_and_resettable — 個別設定の全解除と承認済み範囲の継承を確認する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_operation_console.py::test_person_operation_console` / `selected.png`
- 受入テスト `packages/backend/tests/test_operation_policy.py::test_subscriber_operation_policy_is_scoped_and_resettable`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_operation_policy`

## 却下した方針

本人を識別できない共有キーで個別の制限を回避する方法は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
