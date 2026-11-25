# 開発者は、環境別の利用権を検証するとき、サンプル商品のAPIを呼び出すことができる

判定　合格

対象コミット　`413280ee0b9fbeb2f02c47a6a1a2080583707787`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/413280ee0b9fbeb2f02c47a6a1a2080583707787/docs/requirements/items/%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E7%92%B0%E5%A2%83%E5%88%A5%E3%81%AE%E5%88%A9%E7%94%A8%E6%A8%A9%E3%82%92%E6%A4%9C%E8%A8%BC%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81%E3%82%B5%E3%83%B3%E3%83%97%E3%83%AB%E5%95%86%E5%93%81%E3%81%AEAPI%E3%82%92%E5%91%BC%E3%81%B3%E5%87%BA%E3%81%99%E3%81%93%E3%81%A8%E3%81%8C%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　全商品の出品仕様がFastAPIと一致し、再生成した各YAMLを同じ内容で公開できる。（0.262 秒）　`packages/sample_api/tests/test_products.py::test_generated_product_contracts`
- 成功　12商品で5つの業務操作とヘルスチェックを実行し、商品境界とLambda応答を照合する。（0.069 秒）　`packages/sample_api/tests/test_products.py::test_each_product_operation_through_lambda`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（検証環境の在庫を照会する）（1.828 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[cognito-lambda-staging]`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（本番環境の在庫を照会する）（1.813 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[cognito-lambda-production]`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（利用者がLambdaへ接続する）（1.759 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[cognito-lambda]`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（システムがLambdaへ接続する）（1.807 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[machine-lambda]`
- 成功　承認した呼び出しを接続先へ転送し、権限取消後は遮断する（利用者がHTTPS先へ接続する）（2.072 秒）　`tests/e2e/aws/test_portal.py::test_approved_calls_reach_upstream[cognito-https]`

[テスト実行記録（JUnit XML）](%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E7%92%B0%E5%A2%83%E5%88%A5%E3%81%AE%E5%88%A9%E7%94%A8%E6%A8%A9%E3%82%92%E6%A4%9C%E8%A8%BC%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81%E3%82%B5%E3%83%B3%E3%83%97%E3%83%AB%E5%95%86%E5%93%81%E3%81%AEAPI%E3%82%92%E5%91%BC%E3%81%B3%E5%87%BA%E3%81%99%E3%81%93%E3%81%A8%E3%81%8C%E3%81%A7%E3%81%8D%E3%82%8B.xml)
