---
name: verify-tsugite-tests
description: 継手APIで単体テスト、E2E、CDKテストを追加・変更・実行する際に、対象テストとミューテーションテストで検証する。
---

# 継手APIのテストを検証する

1. テスト関数の先頭に、確認する条件と期待結果が伝わる日本語の1行docstringを書く。パラメーターごとの違いは、既存のテストIDを保ち、各 pytest.param に pytest.mark.case_detail("日本語の説明") を指定する。
2. 影響範囲に応じて task test:agent、task test:model、task test:backend、task test:frontend、task test:infra を実行する。利用者の導線を変更した場合は task test:e2e、AWSサービス連携に影響する場合は task test:aws も実行する。
3. 通常のテストが通ったら、ローカルで task test:mutation を実行する。対象層だけを実行する場合は task test:mutation -- --layer frontend のように指定する。今の変更を代表するミューテーションが登録されていなければ、一時コピーに対する変異と対象テストを packages/tools/testing/mutation_test.py に追加する。
4. 変更前の実装で成功し、変異した実装で対象テストが期待する理由で失敗することを確認する。生き残った変異は、既存動作と等価か、テストのアサーションが足りないかを確認する。収集エラー、実行環境のエラーやタイムアウトは検出に数えない。
5. テスト結果には実行した層、変異の検出数、確認できなかった項目を記録する。ミューテーションテストはローカル検証として扱う。
