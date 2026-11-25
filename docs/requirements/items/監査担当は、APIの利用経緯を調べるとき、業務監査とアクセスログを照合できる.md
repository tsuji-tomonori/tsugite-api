# **監査担当**は、**API**の利用経緯を調べるとき、**業務監査**と**アクセスログ**を照合できる

## 背景

**監査担当**（全プロジェクトの記録を照合する役割）は、公開・申請・判断と実行の記録を横断して調査する。

## なぜ必要か

誰がいつどの商品をどの権限で呼び出したかを再現するため。

## 決めた方針

**業務監査**（公開・利用申請・判断などの業務操作の記録）と**アクセスログ**（呼び出しの開始・終了・拒否を含む実行記録）を**リクエストID**（同じ呼び出しに関する記録を照合する識別子）で結ぶ。提供元、主体、プロジェクト、環境、判断理由を追跡する。

> 実装検証 test_approved_calls_reach_upstream — 同じリクエストIDに属する実際のログと業務監査を突き合わせる。

管理者と監査担当は、監査履歴で全体の呼び出しを確認できる。公開・申請・承認は業務操作履歴から照合する。

> Quint audit.auditLogTest — 監査画面は役割と呼び出し時点の帰属を照合する。
> 実装検証 test_auditor_cross_checks_exports — 同じリクエストIDに属する実際のログと業務監査を突き合わせる。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_requirement_flows.py::test_auditor_cross_checks_exports` / `trace-audit.png`
- 受入テスト `tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream`
- 受入テスト `packages/backend/tests/test_org_access.py::test_access_log_scopes`
- 受入テスト `packages/backend/tests/test_quint_governance.py::test_log_history`

## 却下した方針

別々の記録に照合できない識別子を付ける方法は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
