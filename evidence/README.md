# 要件別の検証証跡

[最新の検証結果](https://github.com/tsuji-tomonori/tsugite-api/blob/evidence/evidence/report.md)を開くと、マージされたPRで確認した要件とその判定を読める。[保存履歴](https://github.com/tsuji-tomonori/tsugite-api/commits/evidence/)では、各コミットから当時の証跡、対応する `main` のマージコミット（`Source-merge`）、元のVerify実行をたどれる。

PRが `main` にマージされるたびに、CIがそのPRの検証対象コミットと一致する `requirement-evidence` を、同じリポジトリの `evidence` ブランチの `evidence/` に保存する。保存処理に失敗した場合は、Actionsの「Publish requirement evidence」を `main` で再実行すると、未保存のマージから順に再開する。PRのレビュー中は、Verifyの成果物 `requirement-evidence` を展開して `report.md` を開ける。

一覧から要件名を選ぶと、要件ごとのMarkdownに、実行したテスト名、条件と期待結果、成否、実行時間、画面画像と実測値を表示する。各ページ末尾のJUnit XMLで、その要件に対応するテストの実行記録を確認できる。テスト用の識別子を含む監査・アクセスログの原文（`trace_sample`、`access_sample`）はVerify成果物で参照する。インフラの要求には合成テンプレートに対するアサーションの結果を表示する。

要件を追加するときは、`docs/requirements/items` の該当ファイルの「決めた方針」にある「受入テスト」に、実際に挙動を確認する pytest 関数を指定する。画面を操作するケースには、そのケース自身が撮影して JUnit に登録する PNG のファイル名も指定する。

```md
### 受入テスト

- 受入テスト `tests/e2e/browser/test_portal.py::test_large_catalog` / `phone.png`
```

1つの要求に複数のテストを指定すると、対象となった全ケースを照合する。1つの操作シナリオで複数の要求を検証するときは、それぞれの要求に対応する画面を指定する。テストの失敗とエラーは「不合格」、実行予定のケースのスキップ・未実行・指定画像の欠落は「検証未完了」と記録する。どちらもCIを失敗させる。

要件ファイルが変わったPRでは全件を実行する。ほかのPRでは既存の差分CIの計画に従い、実行していない層を「対象外」、一部の層だけを検証した要求を「部分実行」と記録する。同じディレクトリの `requirements.xml` には、要求ごとに1つのJUnitケースを出力する。部分実行と対象外の要求には `skipped` が付く。

ローカルでは `task test` と `task test:aws` で同じ変更の結果を取得してから、`python -m tools.testing.requirement_evidence` で全要求を照合できる。成功・失敗はコマンドの終了コードで判定できる。

Verifyで生成した各要件ページには「検証時点の要件原本」へのリンクがある。テスト実行時の受入条件と変更理由を確認するには、該当ページから同じコミットの原本を開く。
