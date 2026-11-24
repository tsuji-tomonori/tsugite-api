# 開発者は、ポータルを配備するとき、APIを単一の入口で提供できる

判定　合格

対象コミット　`6f47997508f5b067db9632c3a425ced87ee8955a`

## 実行したテストと証跡

- 成功　非公開S3、呼び出しの認可、キャッシュと配信の設定が設計どおりである（0.277 秒）　`packages/infra/tests/test_stack.py::test_access_boundaries`
  - AWS::EC2::NatGateway　期待 0 件 / 実測 0 件
- 成功　常時稼働の構成を置かず、Lambdaのメモリ・タイムアウトとログ保存期間を制限する。（0.187 秒）　`packages/infra/tests/test_cost.py::test_cost_drivers_are_bounded`

[テスト実行記録（JUnit XML）](%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E3%83%9D%E3%83%BC%E3%82%BF%E3%83%AB%E3%82%92%E9%85%8D%E5%82%99%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%82%92%E5%8D%98%E4%B8%80%E3%81%AE%E5%85%A5%E5%8F%A3%E3%81%A7%E6%8F%90%E4%BE%9B%E3%81%A7%E3%81%8D%E3%82%8B.xml)
