# 継手APIのチャット

ログイン後のホームで公開APIを検索し、使い方ガイドに沿って操作を案内します。運営への問い合わせは入力欄を開いて送信します。管理者は問い合わせ一覧で回答し、依頼者は同じ画面で確認できます。問い合わせ本文と回答は Aurora DSQL に保存します。

## 質問から回答まで

1. FastAPI の Lambda が利用者を認証し、チャット処理用 Lambda を非同期に起動します。DynamoDB の従量課金テーブルに一時結果を置き、ブラウザーは受付番号で状態を確認します。利用者本人にだけ結果を返し、表示時に商品の公開範囲とガイドの対象ロールを再確認します。
2. Ruri が商品検索、ガイド、対象外の日本語例文と質問を比較します。検索クエリのモデルは許可された検索先と短い検索語を JSON で返します。元の質問と生成した検索語の関連を確かめ、元の質問でも検索します。
3. 商品は既存の語句・業務概念の検索にモデルの類似度検索を加え、順位を統合して最大3件表示します。埋め込みの対象は1回の検索で先頭240件までです。ガイドも語句と意味で検索し、生成モデルが出典と操作手順を選びます。表示する手順と商品情報はポータルに登録された原文を使います。
4. 問い合わせの送信は利用者のボタン操作で行います。送信内容はモデルに渡らず、チャットから実行できるモデル操作は読み取り専用の検索と回答箇所の選択です。

## モデルと配備

| 役割 | モデル | 量子化 | ライセンス |
| --- | --- | --- | --- |
| 日本語の判定と検索埋め込み | [Ruri v3 30m](https://huggingface.co/cl-nagoya/ruri-v3-30m) の [ONNX 配布版](https://huggingface.co/onnx-community/ruri-v3-30m-ONNX) | INT8、約37 MB | Apache-2.0 |
| 検索先とクエリの生成 | [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) | Q3_K_M、約432 MB | Apache-2.0 |
| 日本語回答の出典・手順選択 | [Qwen2.5-0.5B-Instruct-Ja-SFT](https://huggingface.co/jaeyong2/Qwen2.5-0.5B-Instruct-Ja-SFT) の [GGUF 配布版](https://huggingface.co/tensorblock/Qwen2.5-0.5B-Instruct-Ja-SFT-GGUF) | Q2_K、約339 MB | Apache-2.0 |

モデルごとに Python 3.14 の ZIP 版 Lambda Event Function を用意します。埋め込みは ONNX Runtime、生成はローカルで起動する CPU 版 llama.cpp を使用します。生成の温度とシードを固定し、JSON スキーマで出力を制限します。API とチャット処理はそれぞれ Python 3.15 の ZIP として動作します。

チャット処理は API・認可・DB 移行と同じ Python 3.15 用の依存 Layer を参照します。判定モデルは Python 3.14 用の `decision-model` Layer（ONNX Runtime、NumPy、Tokenizers、AWS SDK）、検索語生成と回答生成は `model-sdk` Layer（AWS SDK）を参照します。これらの外部パッケージの版と wheel のハッシュはルートの `uv.lock` に記録します。モデルの重みは S3 から読み込み、固定コミットからビルドした `llama-server` は生成用の関数 ZIP に含めます。

GitHub にはソース、取得元、版、チェックサムを置きます。配備時には既定の CDK ブートストラップ用 S3 の `tsugite-chat-models/` にモデル重みをアップロードします。既存の同一版を再利用します。モデルの Lambda は最初の呼び出し時に担当モデルを `/tmp` に取得し、ウォーム実行時にモデルと埋め込みを再利用します。3モデルは Apache-2.0 で、再配布時にはライセンスや通知を添える条件があります。

ローカルのデモでは既存の語句・概念検索と登録済みの手順でチャットを試せます。量子化モデルの精度、コールドスタート時間、スループットの計測には AWS 上のモデル Lambda を使用します。


## 開発時の検証

`task test:agent` は検索・ジョブ・モデルの単体テストと、チャットAPIで質問を受け付けてから回答を取得する結合テストを実行します。結合テストではSQLiteの実データを使い、DynamoDBとLambda呼び出しをテスト用に置き換えます。`task test:architecture` で依存方向とモデルの固定バージョンを、`task test:mutation -- --layer agent --layer models` で代表的な不具合をテストが検出できることを確認します。
