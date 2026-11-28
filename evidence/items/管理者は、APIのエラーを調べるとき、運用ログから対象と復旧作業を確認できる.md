# 管理者は、APIのエラーを調べるとき、運用ログから対象と復旧作業を確認できる

判定　合格

対象コミット　`cafe7d7be06185bc160edd3c9dd530ec2fde6d97`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/cafe7d7be06185bc160edd3c9dd530ec2fde6d97/docs/requirements/items/%E7%AE%A1%E7%90%86%E8%80%85%E3%81%AF%E3%80%81API%E3%81%AE%E3%82%A8%E3%83%A9%E3%83%BC%E3%82%92%E8%AA%BF%E3%81%B9%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81%E9%81%8B%E7%94%A8%E3%83%AD%E3%82%B0%E3%81%8B%E3%82%89%E5%AF%BE%E8%B1%A1%E3%81%A8%E5%BE%A9%E6%97%A7%E4%BD%9C%E6%A5%AD%E3%82%92%E7%A2%BA%E8%AA%8D%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　外部名簿が一時的に利用できなければ一覧APIはサービス障害を返し、復旧後に同じページを読める。（0.106 秒）　`packages/backend/tests/test_required_member_directory.py::test_directory_temporarily_unavailable`
- 成功　HTTPの結果と原因から重要度を決め、対象APIと画面を安全に記録する。（正常に応答した呼び出しを記録する）（0.003 秒）　`packages/backend/tests/test_request_logs.py::test_http_log[0-200-INFO]`
- 成功　HTTPの結果と原因から重要度を決め、対象APIと画面を安全に記録する。（権限不足の呼び出しを利用者起因に分類する）（0.003 秒）　`packages/backend/tests/test_request_logs.py::test_http_log[1-403-WARN]`
- 成功　HTTPの結果と原因から重要度を決め、対象APIと画面を安全に記録する。（未処理例外をサーバー障害に分類する）（0.002 秒）　`packages/backend/tests/test_request_logs.py::test_http_log[2-500-ERROR]`
- 成功　HTTPの結果と原因から重要度を決め、対象APIと画面を安全に記録する。（保存仕様が壊れたときにデータ修正の手順を残す）（0.002 秒）　`packages/backend/tests/test_request_logs.py::test_http_log[3-503-CRITICAL]`
- 成功　HTTPの結果と原因から重要度を決め、対象APIと画面を安全に記録する。（入力値の型が違うときに利用者起因に分類する）（0.002 秒）　`packages/backend/tests/test_request_logs.py::test_http_log[bad-422-WARN]`
- 成功　ポータル停止後のCognito障害では、操作した管理者と対象利用者を分けて復旧方法を記録する。（0.003 秒）　`packages/backend/tests/test_request_logs.py::test_member_partial_deletion`
- 成功　画面内の入力不備と不具合を区別し、商品と本人の識別子だけを残す。（0.002 秒）　`packages/frontend/tests/test_screen_logs.py::test_screen_error_context`

[テスト実行記録（JUnit XML）](%E7%AE%A1%E7%90%86%E8%80%85%E3%81%AF%E3%80%81API%E3%81%AE%E3%82%A8%E3%83%A9%E3%83%BC%E3%82%92%E8%AA%BF%E3%81%B9%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81%E9%81%8B%E7%94%A8%E3%83%AD%E3%82%B0%E3%81%8B%E3%82%89%E5%AF%BE%E8%B1%A1%E3%81%A8%E5%BE%A9%E6%97%A7%E4%BD%9C%E6%A5%AD%E3%82%92%E7%A2%BA%E8%AA%8D%E3%81%A7%E3%81%8D%E3%82%8B.xml)
