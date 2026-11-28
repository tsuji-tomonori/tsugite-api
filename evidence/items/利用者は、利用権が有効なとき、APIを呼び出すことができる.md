# 利用者は、利用権が有効なとき、APIを呼び出すことができる

判定　合格

対象コミット　`5d20e41ce9a4f08afbccdf5c274e1ff2f859cc17`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/5d20e41ce9a4f08afbccdf5c274e1ff2f859cc17/docs/requirements/items/%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AF%E3%80%81%E5%88%A9%E7%94%A8%E6%A8%A9%E3%81%8C%E6%9C%89%E5%8A%B9%E3%81%AA%E3%81%A8%E3%81%8D%E3%80%81API%E3%82%92%E5%91%BC%E3%81%B3%E5%87%BA%E3%81%99%E3%81%93%E3%81%A8%E3%81%8C%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　デモの提供者と利用者が公開・申請・承認・実行・権限取消を画面で完了できる（10.580 秒）　`tests/e2e/browser/test_portal.py::test_user_flow`
  - ![SKUを指定し、API Docs内で短期認証を発行して得たHTTPステータスと応答本文](../screenshots/demo/06-invoked.png)
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（検証環境の在庫を照会する）（1.930 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[cognito-lambda-staging]`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（本番環境の在庫を照会する）（1.923 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[cognito-lambda-production]`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（利用者がLambdaへ接続する）（1.729 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[cognito-lambda]`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（システムがLambdaへ接続する）（1.784 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[machine-lambda]`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（利用者がHTTPS先へ接続する）（2.053 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[cognito-https]`
- 成功　利用権の操作列を再生し、取消や別環境では接続先への転送が起きない。（形式仕様の操作と期待状態を照合する。）（0.236 秒）　`packages/backend/tests/test_quint_grants.py::test_grant_history[grants.closedTest]`
- 成功　利用権の操作列を再生し、取消や別環境では接続先への転送が起きない。（形式仕様の操作と期待状態を照合する。）（0.311 秒）　`packages/backend/tests/test_quint_grants.py::test_grant_history[grants.lifecycleTest]`
- 成功　利用権の操作列を再生し、取消や別環境では接続先への転送が起きない。（形式仕様の操作と期待状態を照合する。）（0.321 秒）　`packages/backend/tests/test_quint_grants.py::test_grant_history[grants.reapplyTest]`
- 成功　利用権の操作列を再生し、取消や別環境では接続先への転送が起きない。（形式仕様の操作と期待状態を照合する。）（0.284 秒）　`packages/backend/tests/test_quint_grants.py::test_grant_history[grants.scopeTest]`
- 成功　限定公開における提供元・所属・直接属性の各条件を照合する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_audience_policy[audience.visibilityTest]`
- 成功　本人、別人、共有キーとマシンの権利を区別し、停止・失効を即時反映する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_entitlement_policy[entitlement.principalTest]`
- 成功　本人、別人、共有キーとマシンの権利を区別し、停止・失効を即時反映する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_entitlement_policy[entitlement.stopTest]`
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.001 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.lifetimeTest]`
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.000 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.operationsTest]`
- 成功　認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。（形式仕様の操作と期待状態を照合する。）（0.000 秒）　`packages/backend/tests/test_quint_policy.py::test_operation_policy[credentials.rotatedTest]`

[テスト実行記録（JUnit XML）](%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AF%E3%80%81%E5%88%A9%E7%94%A8%E6%A8%A9%E3%81%8C%E6%9C%89%E5%8A%B9%E3%81%AA%E3%81%A8%E3%81%8D%E3%80%81API%E3%82%92%E5%91%BC%E3%81%B3%E5%87%BA%E3%81%99%E3%81%93%E3%81%A8%E3%81%8C%E3%81%A7%E3%81%8D%E3%82%8B.xml)
