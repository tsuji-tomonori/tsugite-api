# **リーダー**は、担当する**部署**や**プロジェクト**の利用を制御するとき、**API**の利用を停止または再開できる

## 背景

組織やプロジェクトを単位に利用を一時停止する必要がある。

## なぜ必要か

対象組織に属する利用をまとめて制御し、必要な時点で再開するため。

## 決めた方針

担当部署・プロジェクトに対して停止・再開できるようにする。

> Quint entitlement.stopTest — 有効な利用権でも停止・公開範囲外・キー失効時は拒否する。
> 実装検証 test_workspace_key_console test_project_pause_and_resume_preserves_active_key — 担当範囲の停止・再開を実際の所属と照合する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_workspace_console.py::test_workspace_key_console` / `stopped.png`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_entitlement_policy`
- 受入テスト `packages/backend/tests/test_required_usage_settings.py::test_project_pause_and_resume_preserves_active_key`

## 却下した方針

担当外の部署・プロジェクトまで変更する方法は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
