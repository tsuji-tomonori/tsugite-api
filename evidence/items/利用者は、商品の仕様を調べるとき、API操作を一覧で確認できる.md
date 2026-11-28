# 利用者は、商品の仕様を調べるとき、API操作を一覧で確認できる

判定　合格

対象コミット　`9919f32a7df54974bb16798cc94c6a6111468218`

[検証した要件と変更履歴](https://github.com/tsuji-tomonori/tsugite-api/blob/9919f32a7df54974bb16798cc94c6a6111468218/docs/requirements/items/%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AF%E3%80%81%E5%95%86%E5%93%81%E3%81%AE%E4%BB%95%E6%A7%98%E3%82%92%E8%AA%BF%E3%81%B9%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E6%93%8D%E4%BD%9C%E3%82%92%E4%B8%80%E8%A6%A7%E3%81%A7%E7%A2%BA%E8%AA%8D%E3%81%A7%E3%81%8D%E3%82%8B.md)

## 実行したテストと証跡

- 成功　商品を公開し、利用者が商品詳細から利用申請できる（6.736 秒）　`tests/e2e/browser/test_product_publication.py::test_publish_and_apply_from_product_page`
  - ![選んだ操作の入力と応答仕様](../screenshots/publication/operations.png)
- 成功　API Docsは各操作の入力・成功応答・エラーとモデルを仕様どおり表示し、承認先で試行できる。（0.005 秒）　`packages/frontend/tests/test_required_product_views.py::test_docs_match_openapi_operations`

[テスト実行記録（JUnit XML）](%E5%88%A9%E7%94%A8%E8%80%85%E3%81%AF%E3%80%81%E5%95%86%E5%93%81%E3%81%AE%E4%BB%95%E6%A7%98%E3%82%92%E8%AA%BF%E3%81%B9%E3%82%8B%E3%81%A8%E3%81%8D%E3%80%81API%E6%93%8D%E4%BD%9C%E3%82%92%E4%B8%80%E8%A6%A7%E3%81%A7%E7%A2%BA%E8%AA%8D%E3%81%A7%E3%81%8D%E3%82%8B.xml)
