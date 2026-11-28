# リーダーは、担当する部署やプロジェクトの利用を制御するとき、APIの利用を停止または再開できる

判定　合格

対象コミット　`9919f32a7df54974bb16798cc94c6a6111468218`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/9919f32a7df54974bb16798cc94c6a6111468218/docs/requirements/items/%E3%83%AA%E3%83%BC%E3%83%80%E3%83%BC%E3%81%AF%E3%80%81%E6%8B%85%E5%BD%93%E3%81%99%E3%82%8B%E9%83%A8%E7%BD%B2%E3%82%84%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88%E3%81%AE%E5%88%A9%E7%94%A8%E3%82%92%E5%88%B6%E5%BE%A1%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%81%AE%E5%88%A9%E7%94%A8%E3%82%92%E5%81%9C%E6%AD%A2%E3%81%BE%E3%81%9F%E3%81%AF%E5%86%8D%E9%96%8B%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　管理者が組織階層と兼務を設定し、リーダーがキー・利用状況・停止と再開を操作する（11.360 秒）　`tests/e2e/browser/test_workspace_console.py::test_workspace_key_console`
  - ![上位部署の利用停止が配下の経理部に反映された状態](../screenshots/workspace/stopped.png)
- 成功　本人、別人、共有キーとマシンの権利を区別し、停止・失効を即時反映する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_entitlement_policy[entitlement.principalTest]`
- 成功　本人、別人、共有キーとマシンの権利を区別し、停止・失効を即時反映する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_entitlement_policy[entitlement.stopTest]`
- 成功　担当リーダーが部署を停止すると配下の呼び出しも止まり、再開後は同じ認証情報で利用を続けられる。（0.213 秒）　`packages/backend/tests/test_required_usage_settings.py::test_project_pause_and_resume_preserves_active_key`

[テスト実行記録（JUnit XML）](%E3%83%AA%E3%83%BC%E3%83%80%E3%83%BC%E3%81%AF%E3%80%81%E6%8B%85%E5%BD%93%E3%81%99%E3%82%8B%E9%83%A8%E7%BD%B2%E3%82%84%E3%83%97%E3%83%AD%E3%82%B8%E3%82%A7%E3%82%AF%E3%83%88%E3%81%AE%E5%88%A9%E7%94%A8%E3%82%92%E5%88%B6%E5%BE%A1%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%81%AE%E5%88%A9%E7%94%A8%E3%82%92%E5%81%9C%E6%AD%A2%E3%81%BE%E3%81%9F%E3%81%AF%E5%86%8D%E9%96%8B%E3%81%A7%E3%81%8D%E3%82%8B.xml)
