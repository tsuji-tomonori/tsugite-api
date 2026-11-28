# 提供者は、利用者の実行範囲を制限するとき、API操作を指定できる

判定　合格

対象コミット　`3f236ef119c9f98eded43090ae3f5e98464527df`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/3f236ef119c9f98eded43090ae3f5e98464527df/docs/requirements/items/%E6%8F%90%E4%BE%9B%E8%80%85%E3%81%AF%E3%80%81%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AE%E5%AE%9F%E8%A1%8C%E7%AF%84%E5%9B%B2%E3%82%92%E5%88%B6%E9%99%90%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E6%93%8D%E4%BD%9C%E3%82%92%E6%8C%87%E5%AE%9A%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　提供者が利用者の操作を選び、送料1,400円のHTTPS応答と権限変更直後の転送停止を照合する（13.246 秒）　`tests/e2e/browser/test_operation_console.py::test_person_operation_console`
  - ![提供者が利用者の見積参照・計算を許可し、削除を除外した操作権限](../screenshots/operation-permissions/selected.png)
- 成功　提供者は購読者に仕様内の操作を設定でき、解除すると個別設定が一覧から消える。（0.346 秒）　`packages/backend/tests/test_operation_policy.py::test_subscriber_operation_policy_is_scoped_and_resettable`
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.lifetimeTest]`
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.operationsTest]`
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.rotatedTest]`

[テスト実行記録（JUnit XML）](%E6%8F%90%E4%BE%9B%E8%80%85%E3%81%AF%E3%80%81%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AE%E5%AE%9F%E8%A1%8C%E7%AF%84%E5%9B%B2%E3%82%92%E5%88%B6%E9%99%90%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E6%93%8D%E4%BD%9C%E3%82%92%E6%8C%87%E5%AE%9A%E3%81%A7%E3%81%8D%E3%82%8B.xml)
