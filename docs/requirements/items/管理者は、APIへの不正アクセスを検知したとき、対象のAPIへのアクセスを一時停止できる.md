# **管理者**は、**API**への不正アクセスを検知したとき、対象の**API**へのアクセスを一時停止できる

## 背景

不正な呼び出しの疑いがある場合、個別の利用権取消だけでは対象API全体を保護できない。

## なぜ必要か

調査中に新たな呼び出しが接続先へ届くのを止めるため。

## 決めた方針

不正アクセスを検知し、対象APIに対する全アクセスを人の判断で一時停止できるようにする。

> Quint entitlement.stopTest — 有効な利用権でも停止・公開範囲外・キー失効時は拒否する。
> 実装検証 test_admin_stops_target_after_denial test_lifecycle — 管理者の一時停止後に既存の資格で転送が拒否されることを確認する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_requirement_flows.py::test_admin_stops_target_after_denial` / `suspended.png`
- 受入テスト `packages/backend/tests/test_catalog.py::test_lifecycle`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_entitlement_policy`

## 却下した方針

検知後に通知するだけで人が停止できない運用は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
