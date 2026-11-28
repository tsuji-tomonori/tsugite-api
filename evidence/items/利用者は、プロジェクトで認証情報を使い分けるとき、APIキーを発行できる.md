# 利用者は、プロジェクトで認証情報を使い分けるとき、APIキーを発行できる

判定　合格

対象コミット　`fd4d5eb6fc4dd6e00ea5cd44a6a40c2fa7fc077a`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/fd4d5eb6fc4dd6e00ea5cd44a6a40c2fa7fc077a/docs/requirements/items/%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AF%E3%80%81%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88%E3%81%A7%E8%AA%8D%E8%A8%BC%E6%83%85%E5%A0%B1%E3%82%92%E4%BD%BF%E3%81%84%E5%88%86%E3%81%91%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%82%AD%E3%83%BC%E3%82%92%E7%99%BA%E8%A1%8C%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　管理者が組織階層と兼務を設定し、リーダーがキー・利用状況・停止と再開を操作する（13.811 秒）　`tests/e2e/browser/test_workspace_console.py::test_workspace_key_console`
  - ![同じプロジェクトの本人専用キーと共有キー。範囲と状態を確認](../screenshots/workspace/keys.png)
- 成功　EmulatorのCognitoと共有・本人キーでHTTPS接続先を呼び、別人・範囲外・失効を拒否する（2.769 秒）　`tests/e2e/aws/test_scoped_keys.py::test_scoped_keys_reach_https`
- 成功　本人、別人、共有キーとマシンの権利を区別し、停止・失効を即時反映する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_entitlement_policy[entitlement.principalTest]`
- 成功　本人、別人、共有キーとマシンの権利を区別し、停止・失効を即時反映する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_entitlement_policy[entitlement.stopTest]`
- 成功　従来キーを複数発行し、一つを失効させても同じプロジェクトの別のキーで利用を続けられる。（共有キーでプロジェクトの承認済みAPI全体を選べる）（0.272 秒）　`packages/backend/tests/test_required_credentials.py::test_legacy_credential_inventory_and_independent_revocation[all-approved]`
- 成功　従来キーを複数発行し、一つを失効させても同じプロジェクトの別のキーで利用を続けられる。（本人限定キーで指定したAPIを選べる）（0.229 秒）　`packages/backend/tests/test_required_credentials.py::test_legacy_credential_inventory_and_independent_revocation[specific-api]`

[テスト実行記録（JUnit XML）](%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AF%E3%80%81%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88%E3%81%A7%E8%AA%8D%E8%A8%BC%E6%83%85%E5%A0%B1%E3%82%92%E4%BD%BF%E3%81%84%E5%88%86%E3%81%91%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%82%AD%E3%83%BC%E3%82%92%E7%99%BA%E8%A1%8C%E3%81%A7%E3%81%8D%E3%82%8B.xml)
