# 開発者は、ポータルを配備するとき、APIを単一の入口で提供できる

判定　合格

対象コミット　`e21e4aff8342a5da99913ad71bfae714b8979534`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/e21e4aff8342a5da99913ad71bfae714b8979534/docs/requirements/items/%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E3%83%9D%E3%83%BC%E3%82%BF%E3%83%AB%E3%82%92%E9%85%8D%E5%82%99%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%82%92%E5%8D%98%E4%B8%80%E3%81%AE%E5%85%A5%E5%8F%A3%E3%81%A7%E6%8F%90%E4%BE%9B%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　非公開S3、呼び出しの認可、キャッシュと配信の設定が設計どおりである（0.254 秒）　`packages/infra/tests/test_stack.py::test_access_boundaries`
  - AWS::EC2::NatGateway　期待 0 件 / 実測 0 件
- 成功　常時稼働の構成を置かず、Lambdaのメモリ・タイムアウトとログ保存期間を制限する。（0.238 秒）　`packages/infra/tests/test_cost.py::test_cost_drivers_are_bounded`
- 成功　署名が有効な同じ利用者トークンで、正規入口の本人照会は成功し、直接の本人照会は403になる。（入口ヘッダーがない場合は403）（0.871 秒）　`packages/backend/tests/test_auth.py::test_portal_origin_with_valid_access_token[missing]`
- 成功　署名が有効な同じ利用者トークンで、正規入口の本人照会は成功し、直接の本人照会は403になる。（入口ヘッダーが一致しない場合は403）（0.191 秒）　`packages/backend/tests/test_auth.py::test_portal_origin_with_valid_access_token[incorrect]`
- 成功　権限を毎回照合し、取消後は同じトークンでも拒否する（0.225 秒）　`packages/backend/tests/test_gateway_event.py::test_gateway_authorizer_rechecks_each_invocation`

[テスト実行記録（JUnit XML）](%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E3%83%9D%E3%83%BC%E3%82%BF%E3%83%AB%E3%82%92%E9%85%8D%E5%82%99%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%82%92%E5%8D%98%E4%B8%80%E3%81%AE%E5%85%A5%E5%8F%A3%E3%81%A7%E6%8F%90%E4%BE%9B%E3%81%A7%E3%81%8D%E3%82%8B.xml)
