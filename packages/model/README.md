# チャットの推論モデルと配備

| 役割 | モデル | 量子化 | ライセンス |
| --- | --- | --- | --- |
| 日本語の判定と検索埋め込み | [Ruri v3 30m](https://huggingface.co/cl-nagoya/ruri-v3-30m) の [ONNX 配布版](https://huggingface.co/onnx-community/ruri-v3-30m-ONNX) | INT8、約37 MB | Apache-2.0 |
| 検索先とクエリの生成 | [Qwen2.5-0.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) | Q3_K_M、約432 MB | Apache-2.0 |
| 日本語回答の出典・手順選択 | [Qwen2.5-0.5B-Instruct-Ja-SFT](https://huggingface.co/jaeyong2/Qwen2.5-0.5B-Instruct-Ja-SFT) の [GGUF 配布版](https://huggingface.co/tensorblock/Qwen2.5-0.5B-Instruct-Ja-SFT-GGUF) | Q2_K、約339 MB | Apache-2.0 |

モデルごとに Python 3.14 の ZIP 版 Lambda Event Function を用意します。埋め込みは ONNX Runtime、生成はローカルで起動する CPU 版 llama.cpp を使用します。生成の温度とシードを固定し、JSON スキーマで出力を制限します。API とチャット処理はそれぞれ Python 3.15 の ZIP として動作します。

チャット処理は API・認可・DB 移行と同じ Python 3.15 用の依存 Layer を参照します。判定モデルは Python 3.14 用の `decision-model` Layer（ONNX Runtime、NumPy、Tokenizers、AWS SDK）、検索語生成と回答生成は `model-sdk` Layer（AWS SDK）を参照します。これらの外部パッケージの版と wheel のハッシュはルートの `uv.lock` に記録します。固定コミットからビルドした `llama-server` は生成用の関数 ZIP に含めます。

判定用の重みとトークナイザーは合計 43,773,448 バイトです。ビルド時に固定版を取得し、両方の SHA-256 を検証して、依存 Layer とは独立した `decision-weights` Layer にライセンスとともに格納します。判定関数は初回の推論時に `/opt/models/decision/` から直接読み込み、同じ実行環境では推論セッションを再利用します。この関数にはモデル取得用の S3 権限はありません。

検索語生成用の重みは 432,041,824 バイト、回答生成用の重みは 338,607,296 バイトで、どちらも Lambda の ZIP 配備上限（関数本体と全 Layer の展開後合計 250 MiB）を超えます。この2件は配備時に CDK ブートストラップ用 S3 の `tsugite-chat-models/` に保存し、各実行環境の初回推論時に自分の重みを `/tmp` に取得して再利用します。ビルドでは関数ごとに本体と利用する全 Layer の展開後のサイズを合算し、上限に達したら配備を止めます。

ローカルのデモでは既存の語句・概念検索と登録済みの手順でチャットを試せます。量子化モデルの精度、コールドスタート時間、スループットの計測には AWS 上のモデル Lambda を使用します。

## 開発時の検証

`task test:model` は判定・生成ハンドラー、重みの取得と検証をテストします。`task test:architecture` は取得元の版とパッケージ間の依存方向を検査します。
