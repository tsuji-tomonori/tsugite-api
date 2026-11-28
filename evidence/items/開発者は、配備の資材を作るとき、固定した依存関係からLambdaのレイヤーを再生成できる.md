# 開発者は、配備の資材を作るとき、固定した依存関係からLambdaのレイヤーを再生成できる

判定　合格

対象コミット　`6ea13b6727fccc012bd33ea31a29b99858f4967b`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/6ea13b6727fccc012bd33ea31a29b99858f4967b/docs/requirements/items/%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E9%85%8D%E5%82%99%E3%81%AE%E8%B3%87%E6%9D%90%E3%82%92%E4%BD%9C%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81%E5%9B%BA%E5%AE%9A%E3%81%97%E3%81%9F%E4%BE%9D%E5%AD%98%E9%96%A2%E4%BF%82%E3%81%8B%E3%82%89Lambda%E3%81%AE%E3%83%AC%E3%82%A4%E3%83%A4%E3%83%BC%E3%82%92%E5%86%8D%E7%94%9F%E6%88%90%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　同じ依存を別の場所で同期してもLayerが一致し、依存を更新したときだけ内容が変わる。（0.213 秒）　`packages/tools/tests/test_lambda_layer.py::test_layer_rebuild_is_reproducible`
- 成功　ロジック変更で関数だけが更新され、依存変更で共有Layerだけが更新される。（1.054 秒）　`packages/infra/tests/test_cdk_regression.py::test_backend_layer_changes_only_with_dependencies`

[テスト実行記録（JUnit XML）](%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E9%85%8D%E5%82%99%E3%81%AE%E8%B3%87%E6%9D%90%E3%82%92%E4%BD%9C%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81%E5%9B%BA%E5%AE%9A%E3%81%97%E3%81%9F%E4%BE%9D%E5%AD%98%E9%96%A2%E4%BF%82%E3%81%8B%E3%82%89Lambda%E3%81%AE%E3%83%AC%E3%82%A4%E3%83%A4%E3%83%BC%E3%82%92%E5%86%8D%E7%94%9F%E6%88%90%E3%81%A7%E3%81%8D%E3%82%8B.xml)
