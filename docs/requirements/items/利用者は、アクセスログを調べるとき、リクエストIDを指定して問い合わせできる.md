# **利用者**は、**アクセスログ**を調べるとき、リクエストIDを指定して**問い合わせ**できる

## 背景

同じAPIを繰り返し呼び出すと、操作名だけでは調査する呼び出しを特定できない。

## なぜ必要か

利用者と運営担当者が同じ呼び出しを確認するため。

## 決めた方針

アクセスログを20件ずつ表で表示する。行を選ぶと、その1件の開始・応答時刻、処理時間、結果、エラーコード、各識別子を確認できる。詳細からチャットで記録について質問でき、問い合わせを送信するとリクエストIDを本文に含める。

> 実装検証 test_access_log_detail_and_support test_access_log_detail — ページングと、選んだリクエストIDが問い合わせに引き継がれることを画面で確認する。

### 受入テスト

- 受入テスト `tests/e2e/browser/test_requirement_flows.py::test_access_log_detail_and_support` / `log-detail.png`
- 受入テスト `packages/frontend/tests/test_required_people_logs.py::test_access_log_detail`

## 却下した方針

利用者が問い合わせのたびにリクエストIDを転記する方式は、取り違えが起きるため採用しない。

### 変更履歴

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。
