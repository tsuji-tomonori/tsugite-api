# チャットの推論モデルと配備

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

`task test:model` は判定・生成ハンドラー、重みの取得と検証をテストします。`task test:architecture` は取得元の版とパッケージ間の依存方向を検査します。
