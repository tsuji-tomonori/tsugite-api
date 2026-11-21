# Tsugite API · 継手API

社内のAPIを一か所で探し、プロジェクト単位で利用を申請できるカタログです。[目的と要件](docs/requirements/README.md)

## 手元で試す

```sh
# uvをインストール済みの端末で最初に1回
uv tool install go-task-bin==3.54.0
task setup
task demo
```

`http://127.0.0.1:8000` で「提供チーム」を選び、API名と用途を入力します。検証の接続先に `sample-sandbox` を選び、用意されたOpenAPIを使って公開できます。別のタブで「利用チーム」を選ぶと、申請、承認後の呼び出し、取消後の拒否を試せます。

## 開発構成と実装設計書

各cloneの最初に `task setup` を実行してください。Python 3.14とワークスペース全体の依存関係を `uv.lock` から同期し、Gitのpre-commitフックを有効にします。フックはステージ済みのテキストを対象にUTF-8（BOMなし）、LF、ファイル末尾の改行1つを確認し、main・masterへの直接コミットを止めます。CIでもテキスト規約を検証します。

| 配置 | 内容 | 実行例 |
| --- | --- | --- |
| `packages/frontend` | PuePy画面と単体テスト | `task test:frontend` |
| `packages/backend` | FastAPIルーター、認証、業務処理とテスト | `task test:backend` |
| `packages/database` | SQLAlchemyモデル、接続、Alembic移行とテスト | `task test:database` |
| `packages/infra` | AWS CDKとテンプレートのテスト | `task build` → `task test:infra` |
| `tests/e2e` | ブラウザー操作とAWS Emulatorを使う横断テスト | `task test:e2e`、`task test:aws` |
| `tools` | ビルド、設計書生成、監査、テストレポート | `task test:tools` |

親の `pyproject.toml` にPythonの対象範囲、共通のバージョン制約、検査設定を置きます。各メンバーの `pyproject.toml` に直接依存を書き、ルートの単一ロックファイルを共有します。依存の追加には `task deps:add -- --package tsugite-backend パッケージ名`、各種コマンドの一覧には `task --list` を使います。

`task docs` は実行中のデータベースやAWS資格情報を使わず、[API別の実装設計書](docs/generated/README.md)、[SQL・AWS操作のCRUD一覧](docs/generated/crud.md)、[入出力スキーマ](docs/generated/schemas.md)を更新します。設計を変えるときはルーターの引数・応答モデル・依存関数を修正します。CRUD表には条件分岐を含む到達可能な操作と根拠のソース行が載ります。転送先の利用者定義APIの項目は、登録時のOpenAPIで決まります。

CIはPRで設計書を生成して成果物に含めます。既定ブランチの検証が通ると、生成結果に差分がある場合だけ `docs/generated/` を自動コミットします。

## ポータルで操作手順を調べる

ログイン後、画面上部または左メニューの［使い方ガイド］を開きます。「読み取りだけ許可したい」のように入力すると、手順本文のキーワードと操作目的の言い換えを組み合わせて候補を表示します。役割を選ぶと該当する手順に絞れます。各手順にはデモの画面画像、操作後の確認方法、操作画面への入口があります。

## APIキーを発行して呼び出す

左メニューの「APIキー」でプロジェクトを選び、「発行条件を確認」を押します。「認証方式と利用条件」で名前、対象API・操作、有効期間、更新開始までの分数を選んで発行します。

|方式|使い方|
|---|---|
|短期Bearer|発行画面のアクセストークンをコピーすると、そのまま承認済みAPIを呼べます。|
|アプリ認証|アプリのサーバーからクライアントID・シークレットとログインした利用者のCognitoアクセストークンを提示します。利用者とアプリの両方に許可された操作を実行できます。|
|システム認証|プロジェクトの管理権限を持つメンバーが発行します。バッチなどがクライアントID・シークレットで、必要なときに短期トークンを取得できます。|

呼び出し先は `/api/invoke/{API識別子}/{環境}/{プロジェクト}/{操作パス}` です。3方式とも `Authorization: Bearer <アクセストークン>` を送ります。ログイン中は、API詳細の「API Docs」でも認証情報と環境を選んで実行できます。

発行の標準設定は有効60分、45分後から更新です。提供者・部署・プロジェクトの上限が適用されます。アプリ・システムからの取得手順、利用者別権限、従来キーの移行は[認証情報と実行権限](docs/design/portal.md#認証情報と実行権限)にまとめています。

## AWSで使う

Python CDKでCloudFront、非公開S3、API Gateway、Lambda、Cognito、Aurora DSQLを構築します。フロントはPuePyとPyScript、APIはFastAPI、DB変更はAlembicです。Pythonのブラウザ実行環境とCSSも同じ配信元に配置します。

CDKをブートストラップ済みのAWS環境で `task synth` が構成を合成し、`task deploy` が配備とDB移行を行います。初回は在庫照会Lambdaが検証用の接続先になります。提供者をCognitoの `own-supply`、利用者を `use-finance`、全体監査担当者を `audit` グループに追加してください。

独自の接続先は [設定例](examples/bindings.json) を編集し、`task deploy -- --bindings ファイル名` で指定します。Lambdaは `kind` に `lambda`、`address` に関数ARNを指定します。HTTPSは必要に応じて `secret_arn` に接続用BearerトークンのSecrets Manager ARNを指定し、提供元でも呼び出しを制限します。委任された接続先の配下なら、提供チームが画面でベースパスと [OpenAPI](examples/stock.openapi.json) を登録できます。

システム間連携には、対象プロジェクトのCognitoアプリクライアントで `client_credentials` と `hub/invoke` スコープを使います。承認後、API詳細に表示されるURLへアクセストークンを付けて呼び出します。

## E2Eテスト

`task synth` でテストに使う配布物とCDKテンプレートを作ります。ブラウザーとAWSの検証は次の手順で再現できます。

```sh
task browser:install
task test
# Linux x86_64でAWS Emulator 1.0.555を導入して実行
task emulator:install
task test:aws
```

ブラウザーでは、OpenAPIファイルの登録、仕様の検索、申請、却下、再申請、承認、掲載の取り下げ、権限取消と監査履歴を確認します。AWS側ではテスト専用のエミュレーターを起動し、CDKテンプレートから対象リソースを構築します。Cognitoのトークンを持つ提供者と利用者が別々のブラウザー画面を操作し、承認された利用者に在庫照会Lambdaの商品コードが表示されるところまで検証します。HTTPSの接続先にはSecrets Managerから取得したトークンが届き、権限取消後はリクエストが届かないことも確かめます。終了時に環境を破棄します。[AWS Emulatorのインストール方法](https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-linux.html)

この版では、CloudFormationが `AWS::DSQL::Cluster` を受け付けません。DSQLはSDKでクラスターが稼働するところまで、業務データの読み書きはSQLiteで検証します。利用者にはエミュレーターのCognitoがパスワード認証で発行したトークンを使います。システム連携にはテスト用の署名鍵を使い、権限の承認前、別プロジェクト・別環境、取消後の呼び出しが拒否されることを確認します。Cognitoのホスト型ログイン、MFA、OAuthのトークン発行、CloudFront経由の全経路はこのE2Eの対象外です。


## CDKの構成と検証レポート

データベース・移行、API実行、ゲートウェイ、画面配信、認証、接続先設定を個別のコンストラクトで管理します。スタックとタグ対応リソースには `Application=TsugiteAPI`、`ManagedBy=AWS-CDK`、所属を示す `Component` を設定します。CloudFormationでタグを指定できない型には、同じ情報をテンプレートの `Metadata.Tsugite` に記録します。

GitHub Actions の **Verify** から成果物 **contracts-and-test-results** 内の `test-report.html` または `test-report.pdf` を開くと、ケースごとの期待結果、成否、実行時間、実際の画面とタグ一覧を確認できます。手元では通常のテストに `--junitxml=artifacts/junit.xml`、エミュレーターのテストに `--junitxml=artifacts/aws-emulator.xml` を付けて実行し、`task report` で同じレポートを作れます。

[ポータルの画面仕様と業務フロー](docs/design/portal.md)。デモ起動中に別の端末で `task seed -- --editions 20` を実行すると、在庫・配送・為替・店舗・発注・営業日の6種類を20拠点分、計120件公開できます。同じ名前の出品は再利用します。デモでの実行結果は接続情報の折り返しです。業務ごとの応答はHTTPS接続のE2Eで確認します。
