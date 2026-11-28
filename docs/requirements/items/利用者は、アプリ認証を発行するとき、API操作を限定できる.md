# **利用者**は、**アプリ認証**を発行するとき、**API操作**を限定できる

## 背景

同じ利用者が目的の異なる複数のアプリを使うことがある。

## なぜ必要か

一つのアプリに業務上不要な操作を持たせないため。

## 決めた方針

発行者がアプリごとに利用者・API・操作を選ぶ。実行できるのは申請、利用者別の許可、認証情報の範囲に共通する操作に限る。

> Quint credentials.operationsTest — 利用者と認証情報の両方が許可した操作だけを実行する。
> 実装検証 test_person_operation_console test_client_tokens_reach_https — 発行時に選べる操作と転送時の権限を照合する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_operation_console.py::test_person_operation_console` / `delegate.png`
- 受入テスト `tests/e2e/aws/test_credential_tokens.py::test_client_tokens_reach_https`
- 受入テスト `packages/backend/tests/test_quint_policy.py::test_operation_policy`

## 却下した方針

アプリの設定で発行者本人の利用権を広げる方法は採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
