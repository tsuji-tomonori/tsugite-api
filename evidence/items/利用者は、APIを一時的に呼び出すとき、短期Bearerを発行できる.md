# 利用者は、APIを一時的に呼び出すとき、短期Bearerを発行できる

判定　合格

対象コミット　`6ea13b6727fccc012bd33ea31a29b99858f4967b`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/6ea13b6727fccc012bd33ea31a29b99858f4967b/docs/requirements/items/%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AF%E3%80%81API%E3%82%92%E4%B8%80%E6%99%82%E7%9A%84%E3%81%AB%E5%91%BC%E3%81%B3%E5%87%BA%E3%81%99%E3%81%A8%E3%81%8D%E3%80%81%E7%9F%AD%E6%9C%9FBearer%E3%82%92%E7%99%BA%E8%A1%8C%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　ブラウザーで3方式を発行し、実時計で1分後に更新、シークレット変更・失効まで確認する（67.461 秒）　`tests/e2e/browser/test_credentials_console.py::test_credentials_console`
  - ![短期Bearer・アプリ・システム認証の一覧と対象操作、更新条件](../screenshots/credentials/credentials.png)
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.lifetimeTest]`
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.operationsTest]`
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.000 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.rotatedTest]`
- 成功　認証方式に応じた手順で期限付きトークンを発行し、利用後は対象の認証情報だけを失効させる。（本人の短期Bearerで承認済みAPI全体を呼べる）（0.879 秒）　`packages/backend/tests/test_required_credentials.py::test_issue_use_and_retire_credentials[bearer-all]`
- 成功　認証方式に応じた手順で期限付きトークンを発行し、利用後は対象の認証情報だけを失効させる。（共有の短期Bearerを指定のAPIで利用できる）（0.324 秒）　`packages/backend/tests/test_required_credentials.py::test_issue_use_and_retire_credentials[bearer-project]`
- 成功　認証方式に応じた手順で期限付きトークンを発行し、利用後は対象の認証情報だけを失効させる。（アプリと本人の資格で指定のAPIを利用できる）（0.328 秒）　`packages/backend/tests/test_required_credentials.py::test_issue_use_and_retire_credentials[app-personal]`
- 成功　認証方式に応じた手順で期限付きトークンを発行し、利用後は対象の認証情報だけを失効させる。（共有アプリで指定したメンバーが承認済み操作を利用できる）（0.434 秒）　`packages/backend/tests/test_required_credentials.py::test_issue_use_and_retire_credentials[app-for-members]`
- 成功　認証方式に応じた手順で期限付きトークンを発行し、利用後は対象の認証情報だけを失効させる。（プロジェクトのリーダーがシステム認証を発行し、利用者のログインなしで交換できる）（0.381 秒）　`packages/backend/tests/test_required_credentials.py::test_issue_use_and_retire_credentials[system-project]`

[テスト実行記録（JUnit XML）](%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AF%E3%80%81API%E3%82%92%E4%B8%80%E6%99%82%E7%9A%84%E3%81%AB%E5%91%BC%E3%81%B3%E5%87%BA%E3%81%99%E3%81%A8%E3%81%8D%E3%80%81%E7%9F%AD%E6%9C%9FBearer%E3%82%92%E7%99%BA%E8%A1%8C%E3%81%A7%E3%81%8D%E3%82%8B.xml)
