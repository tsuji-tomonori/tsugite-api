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

## E2Eテスト

`uv run python tools/manage.py synth` でテストに使う配布物とCDKテンプレートを作ります。ブラウザーとAWSの検証は次の手順で再現できます。

```sh
uv run playwright install chromium --only-shell
uv run pytest -q
# AWS Emulator 1.0.555 をインストールして実行
uv run python tools/emulator_e2e.py
```

ブラウザーでは、OpenAPIファイルの登録、仕様の検索、申請、却下、再申請、承認、掲載の取り下げ、権限取消と監査履歴を確認します。AWS側ではテスト専用のエミュレーターを起動し、CDKテンプレートから対象リソースを構築します。Cognitoのトークンを持つ提供者と利用者が別々のブラウザー画面を操作し、承認された利用者に在庫照会Lambdaの商品コードが表示されるところまで検証します。HTTPSの接続先にはSecrets Managerから取得したトークンが届き、権限取消後はリクエストが届かないことも確かめます。終了時に環境を破棄します。[AWS Emulatorのインストール方法](https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-linux.html)

この版では、CloudFormationが `AWS::DSQL::Cluster` を受け付けません。DSQLはSDKでクラスターが稼働するところまで、業務データの読み書きはSQLiteで検証します。利用者にはエミュレーターのCognitoがパスワード認証で発行したトークンを使います。システム連携にはテスト用の署名鍵を使い、権限の承認前、別プロジェクト・別環境、取消後の呼び出しが拒否されることを確認します。Cognitoのホスト型ログイン、MFA、OAuthのトークン発行、CloudFront経由の全経路はこのE2Eの対象外です。


## CDKの構成と検証レポート

データベース・移行、API実行、ゲートウェイ、画面配信、認証、接続先設定を個別のコンストラクトで管理します。スタックとタグ対応リソースには `Application=TsugiteAPI`、`ManagedBy=AWS-CDK`、所属を示す `Component` を設定します。CloudFormationでタグを指定できない型には、同じ情報をテンプレートの `Metadata.Tsugite` に記録します。

GitHub Actions の **Verify** から成果物 **contracts-and-test-results** 内の `test-report.html` または `test-report.pdf` を開くと、ケースごとの期待結果、成否、実行時間、実際の画面とタグ一覧を確認できます。手元では通常のテストに `--junitxml=artifacts/junit.xml`、エミュレーターのテストに `--junitxml=artifacts/aws-emulator.xml` を付けて実行し、`uv run python tools/test_report.py --pdf` で同じレポートを作れます。
