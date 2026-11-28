# 開発者は、実装設計書を更新するとき、APIとデータベースの仕様を自動生成できる

判定　合格

対象コミット　`a1c36dda25271d6347542fbd6c6232aaed33dc29`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/a1c36dda25271d6347542fbd6c6232aaed33dc29/docs/requirements/items/%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E5%AE%9F%E8%A3%85%E8%A8%AD%E8%A8%88%E6%9B%B8%E3%82%92%E6%9B%B4%E6%96%B0%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%81%A8%E3%83%87%E3%83%BC%E3%82%BF%E3%83%99%E3%83%BC%E3%82%B9%E3%81%AE%E4%BB%95%E6%A7%98%E3%82%92%E8%87%AA%E5%8B%95%E7%94%9F%E6%88%90%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　全APIの入出力を出力し、再生成時に不要な文書を取り除く（1.117 秒）　`packages/tools/tests/test_design.py::test_all_routes_inputs_outputs_and_cleanup`
- 成功　CRUD表の全APIを個別設計書の根拠と照合できる（0.462 秒）　`packages/tools/tests/test_design.py::test_crud_matrices_cover_all_routes_and_match_per_api_evidence`

[テスト実行記録（JUnit XML）](%E9%96%8B%E7%99%BA%E8%80%85%E3%81%AF%E3%80%81%E5%AE%9F%E8%A3%85%E8%A8%AD%E8%A8%88%E6%9B%B8%E3%82%92%E6%9B%B4%E6%96%B0%E3%81%99%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E3%81%A8%E3%83%87%E3%83%BC%E3%82%BF%E3%83%99%E3%83%BC%E3%82%B9%E3%81%AE%E4%BB%95%E6%A7%98%E3%82%92%E8%87%AA%E5%8B%95%E7%94%9F%E6%88%90%E3%81%A7%E3%81%8D%E3%82%8B.xml)
