# **利用者**は、**利用権**が有効なとき、**API**を呼び出すことができる

## 背景

ポータルは人と外部システムの両方から呼び出される。

## なぜ必要か

公開したAPIを、許可したプロジェクト・本人・環境に限って提供するため。

## 決めた方針

呼び出し元を識別し、商品・環境・プロジェクト・操作と公開範囲を照合する。権限取消、別環境、別プロジェクトの場合は転送しない。

> Quint grants.lifecycleTest grants.scopeTest entitlement.principalTest credentials.operationsTest audience.visibilityTest — 承認、掲載停止、権限取消の区別を実際の転送回数で照合する。
> 実装検証 test_user_flow test_approved_calls_reach_upstream — 実行経路を通した実際の転送と拒否を検査する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_portal.py::test_user_flow` / `06-invoked.png`
- 受入テスト `tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream`
- 受入テスト `packages/backend/tests/test_quint_grants.py::test_grant_history`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_audience_policy`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_entitlement_policy`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_operation_policy`

## 却下した方針

認証に成功しただけで対象環境へ転送する方法は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
