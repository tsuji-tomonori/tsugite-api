# Tsugite API · 継手API

社内のAPIを一か所で探し、プロジェクト単位で利用を申請できるカタログです。[目的と要件](docs/requirements/README.md)

## 手元で試す

```sh
uv sync --locked
uv run python tools/manage.py demo
```

`http://127.0.0.1:8000` で「提供チーム」を選び、API名と用途を入力します。検証の接続先に `sample-sandbox` を選び、用意されたOpenAPIを使って公開できます。別のタブで「利用チーム」を選ぶと、申請、承認後の呼び出し、取消後の拒否を試せます。

## AWSで使う

Python CDKでCloudFront、非公開S3、API Gateway、Lambda、Cognito、Aurora DSQLを構築します。フロントはPuePyとPyScript、APIはFastAPI、DB変更はAlembicです。Pythonのブラウザ実行環境とCSSも同じ配信元に配置します。

CDKをブートストラップ済みのAWS環境で `uv run python tools/manage.py synth` が構成を合成し、`uv run python tools/manage.py deploy` が配備とDB移行を行います。初回は在庫照会Lambdaが検証用の接続先になります。提供者をCognitoの `own-supply`、利用者を `use-finance`、全体監査担当者を `audit` グループに追加してください。

独自の接続先は [設定例](examples/bindings.json) を編集し、`deploy --bindings ファイル名` で指定します。Lambdaは `kind` に `lambda`、`address` に関数ARNを指定します。HTTPSは必要に応じて `secret_arn` に接続用BearerトークンのSecrets Manager ARNを指定し、提供元でも呼び出しを制限します。委任された接続先の配下なら、提供チームが画面でベースパスと [OpenAPI](examples/stock.openapi.json) を登録できます。

システム間連携には、対象プロジェクトのCognitoアプリクライアントで `client_credentials` と `hub/invoke` スコープを使います。承認後、API詳細に表示されるURLへアクセストークンを付けて呼び出します。
