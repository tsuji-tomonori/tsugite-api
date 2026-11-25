# Tsugite API · 継手API

社内のAPIを一か所で探し、プロジェクト全員または本人を対象に利用を申請できるカタログです。[目的と要件](docs/requirements/README.md)

## 手元で試す

```sh
# uvをインストール済みの端末で最初に1回
uv tool install go-task-bin==3.54.0
task setup
task demo
```

`http://127.0.0.1:8000` で「提供チーム」を選び、API名と用途を入力します。検証の接続先に `sample-sandbox` を選び、用意されたOpenAPIを使って公開できます。別のタブで「利用チーム」を選ぶと、申請、承認後の呼び出し、取消後の拒否を試せます。

## ファイルの配置

| ディレクトリ | 置くもの |
| --- | --- |
| `deploy/config/` | 画面ビルドと CDK が共有する HTTP 設定 |
| `docs/examples/` | 配備時の接続先の記入例、デモの商品データ、出品用 OpenAPI の例 |
| `tests/support/` | 全テスト共通の補助コードと pytest プラグイン |
| `packages/tools/packaging/` | フロントと Lambda の配布物を作るスクリプト |
| `packages/tools/operations/` | 起動・配備コマンドと初回管理者の登録 |
| `packages/tools/demo/` | デモ商品の投入 |
| `packages/tools/design/` | 設計書・要件一覧の生成 |
| `packages/tools/ci/` | CI の実行対象の選択、カバレッジ・テキスト・インフラの検査 |
| `packages/tools/testing/` | AWS Emulator、Git フック、ミューテーションテストの実行とテストレポートの生成 |
| `packages/tools/tests/` | 開発ツール自体の単体テスト |
| `packages/tools/vendor/` | 同梱する外部ツールとライセンス |

## 開発完了の判定

[分野別の完了の定義](docs/generated/dev-rules/definition-of-done.md)で、変更時の検査、行カバレッジの基準、個々のテストが確かめる内容を確認できます。各PRの Verify は、そのコミットの定義と対象ブランチの有効なルールで文書を再生成し、成果物 `definition-of-done` に保存します。エージェントとモデルは、各パッケージの `pyproject.toml` の `[tool.tsugite.verify]` と `tests/` から完了の定義に掲載されます。Verifyは差分に該当するパッケージを並列ジョブで検証します。手元ではGitHub CLIにログインして `task docs:quality` を実行すると掲載版を更新できます。

## コミットとプッシュの前に

`task setup` で、このクローンの Git フックとコミットテンプレートを有効にします。コミットの件名は `fix(api): 利用申請の入力エラーを修正` のように書きます。マージ時にも件名を指定できます（例 `git merge -m "chore: 作業ブランチを統合" <ブランチ名>`）。

コミット前に、ステージ済みのテキストとコミットメッセージを git-secrets で検査します。対象は AWS アクセスキー ID・シークレットアクセスキーの代入、GitHub トークン、PEM 秘密鍵の開始行です。検出時は該当箇所を取り除き、ファイルを再度ステージしてください。検査ルールは `.githooks/secrets.config` にあります。同梱の [git-secrets](https://github.com/awslabs/git-secrets/tree/7d6b970cbd3c216353cb22b383b70c150140662e) を使うため、個別インストールは不要です。

プッシュ先が `main` のときは、リモートの先端を含む更新だけを許可します。履歴を書き換える `--force`・`--force-with-lease` と `main` の削除を拒否します。先端を手元で確認できない場合は、対象リモートを fetch してから再実行してください。

## 開発構成と実装設計書

各cloneの最初に `task setup` を実行してください。Python 3.14とワークスペース全体の依存関係を `uv.lock` から同期し、Gitのpre-commitフックを有効にします。フックはステージ済みのテキストを対象にUTF-8（BOMなし）、LF、ファイル末尾の改行1つを確認し、main・masterへの直接コミットを止めます。CIでもテキスト規約を検証します。

| 配置 | 内容 | 実行例 |
| --- | --- | --- |
| `packages/frontend` | PuePy画面と単体テスト | `task test:frontend` |
| `packages/backend` | FastAPIルーター、認証、業務処理とテスト | `task test:backend` |
| [`packages/agent`](packages/agent/README.md) | チャットジョブの受付・検索・回答 | `task test:agent` |
| [`packages/model`](packages/model/README.md) | モデルの判定・推論・重み取得 | `task test:model` |
| `packages/database` | SQLAlchemyモデル、接続、Alembic移行とテスト | `task test:database` |
| `packages/infra` | AWS CDKとテンプレートのテスト | `task test:infra` |
| [`tests/architecture`](tests/architecture/README.md) | 全層の依存・文書規則と検査器のテスト | `task test:architecture` |
| `tests/e2e` | ブラウザー操作とAWS Emulatorを使う横断テスト | `task test:e2e`、`task test:aws` |
| `packages/tools` | ビルド、設計書生成、監査、テストレポート | `task test:tools` |

親の `pyproject.toml` にPythonの対象範囲、共通のバージョン制約、検査設定を置きます。各メンバーの `pyproject.toml` に直接依存を書き、ルートの単一ロックファイルを共有します。依存の追加には `task deps:add -- --package tsugite-backend パッケージ名`、各種コマンドの一覧には `task --list` を使います。

テストケースの条件と期待結果は、日本語1行のdocstringに記載します。パラメーター別の補足は `pytest.param` の `pytest.mark.case_detail` で記載します。アーキテクチャテストがE2Eを含むソースを検査し、実行レポートにも同じ説明を表示します。

通常のテストが成功したら、ローカルで `task test:mutation` を実行します。代表的な変異を一時ディレクトリで試し、対象のテストが失敗するか確認します。対象層は `task test:mutation -- --layer frontend` のように指定できます。

CDKのスナップショットは標準構成の論理ID、リソース型と出力を比較します。意図したインフラ変更で差分が出たら、合成したテンプレートで内容を確認して `packages/infra/tests/cloudformation_snapshot.json` を更新します。CDK Nagは既存指摘を `cdk_nag_baseline.json` で照合し、新規指摘をテスト失敗として報告します。詳細は `task audit` が出力する `artifacts/cdk-nag.csv` で確認できます。

[自動生成ドキュメントの目次](docs/generated/README.md)から、API・DB・インフラ・開発ルールの各資料を参照できます。

`task docs:api` は実行中のデータベースやAWS資格情報を使わず、[API別の実装設計書](docs/generated/apis/README.md)、[SQL・AWS操作のCRUD一覧](docs/generated/db/crud.md)、[入出力スキーマ](docs/generated/db/schemas.md)、[テーブル・レコード・カラム定義](docs/generated/db/database.md)を更新します。設計を変えるときはルーターの引数・応答モデル・依存関数を修正します。CRUD表はAPIを行に、SQLテーブルとAWSサービスをそれぞれ別の表の列に並べます。各セルで操作の種類を、API詳細で条件分岐を含む操作の根拠となるソース行を確認できます。転送先の利用者定義APIの項目は、登録時のOpenAPIで決まります。

API操作はルートデコレーター、引数・モデル・項目・列挙値はそれぞれの宣言の直前に `#: 和名` を書きます。DBモデルのクラスには同じ形式でテーブル名を書き、docstringの1段落目にレコード名、2段落目に1行が表す内容を書きます。AWS SDK呼び出しの直前には `#: サービスの和名 / 操作の和名` を書きます。`task docs` はPythonの構文木とコメントトークンをFastAPI・SQLAlchemyの定義と照合し、設計書とデモ環境のOpenAPIに和名を反映します。

[インフラ設計書](docs/generated/infra/README.md)には、CDKコンポーネントごとのリソース一覧とパラメーターシートがあります。`task docs:infra` はCDKを合成し、`packages/infra/cdk.out/TsugiteApi.template.json` から各表を更新します。接続先を指定する場合は `task docs:infra -- --bindings <ファイル>` を使います。既に合成したテンプレートから表だけを更新するときは `task docs:infra:render` を実行します。

ログイン後のホームでは日本語で公開APIを探し、操作手順を確認し、運営に問い合わせできます。モデルの構成と配備方法は[推論モデルと配備](packages/model/README.md)を参照してください。

CIはPRで設計書を生成して成果物に含めます。既定ブランチの検証が通ると、生成結果に差分がある場合だけ `docs/generated/` を自動コミットします。

## ポータルで操作手順を調べる

ログイン後、画面上部または左メニューの［使い方ガイド］を開きます。「読み取りだけ許可したい」のように入力すると、手順本文のキーワードと操作目的の言い換えを組み合わせて候補を表示します。役割を選ぶと該当する手順に絞れます。各手順には表示モードに連動する閲覧専用の画面例、操作後の確認方法、操作画面への入口があります。

## APIキーを発行して呼び出す

左メニューの「APIキー」でプロジェクトを選び、「発行条件を確認」を押します。「認証方式と利用条件」で名前、対象API・操作、有効期間、更新開始までの分数を選んで発行します。

|方式|使い方|
|---|---|
|短期Bearer|発行画面のアクセストークンをコピーすると、そのまま承認済みAPIを呼べます。|
|アプリ認証|アプリのサーバーからクライアントID・シークレットとログインした利用者のCognitoアクセストークンを提示します。利用者とアプリの両方に許可された操作を実行できます。|
|システム認証|プロジェクトの管理権限を持つメンバーが発行します。バッチなどがクライアントID・シークレットで、必要なときに短期トークンを取得できます。|

呼び出し先は `/api/invoke/{API識別名}/{環境}/{プロジェクト}/{操作パス}` です。例えば `/api/invoke/stock-lookup/sandbox/finance/items` です。提供者は登録時に、半角小文字の英字で始まる一意な識別名を指定します。数字とハイフンも使えます。識別名は設定後に変わりません。既存の商品には編集画面から追加でき、従来のUUID付きURLも利用できます。

3方式とも `Authorization: Bearer <アクセストークン>` を送ります。ログイン中は、API詳細の「API Docs」でも認証情報と環境を選んで実行できます。

発行の標準設定は有効60分、45分後から更新です。提供者・部署・プロジェクトの上限が適用されます。アプリ・システムからの取得手順、利用者別権限、従来キーの移行は[認証情報と実行権限](docs/design/portal.md#認証情報と実行権限)にまとめています。

## 商品としてAPIを公開する

「提供するAPI」→「APIを登録」で、基本版（検証）、準本番、本番から出品する環境と接続先を選びます。OpenAPI 3.0 / 3.1のJSON（内部参照のみ、500KB以内）を選ぶと、API名と説明を仕様から取り込めます。「保存して公開」で商品画面に全操作を掲載します。限定公開にする場合は下書きを保存し、公開範囲を設定してから公開します。

環境ごとの「利用・承認条件」では、利用説明、同意が必要な規約、申請項目と承認順を指定します。例えば、本番に「テスト実施ID」を必須項目として追加し、「受理する値」に発行済みIDを1行ずつ登録すると、一致した申請だけが承認フローに進みます。自動承認でも規約と入力条件を確認します。IDの照合元は提供者が登録した値です。

「所属部署が承認 → 提供者が承認」を選ぶと、申請者の所属部署またはその上位部署のリーダーに届き、承認後に提供者に届きます。「承認者と順番を指定」では、特定部署を含む段階を順番に追加できます。最後の承認で、申請した商品・環境に利用権が発生します。既存商品の「商品共通の承認ルール」はこれまでどおり利用できます。

商品画面の「API操作一覧」で操作を開くと、パラメータを入力して承認済みの環境で呼び出せます。使える認証情報がまだない場合は、初回の実行時にその商品専用の個人認証情報を発行します。API Docsは本人のログイン情報と選択した認証情報を使って短期トークンを取得します。「公開版の変更履歴」を開くと、API版、OpenAPI仕様版、操作やモデルの差分、提供者の変更説明を表で確認できます。AWSでは正規化したJSONを非公開のバージョニング有効S3バケットに保存し、ポータルの表示と実行にはDB側の検証済み定義を使用します。

## AWSで使う

main へのマージを起点に自動配備するには、[GitHub Actions の初回設定](deploy/README.md)を行います。

Python CDKでCloudFront、非公開S3、API Gateway、Lambda、Cognito、Aurora DSQLを構築します。フロントはPuePyとPyScript、APIはFastAPI、DB変更はAlembicです。Pythonのブラウザ実行環境とCSSも同じ配信元に配置します。

CDKをブートストラップ済みのAWS環境で `task synth` が構成を合成し、`task deploy` が配備とDB移行を行います。サンプルを含めると、検証・準本番・本番に12商品を扱うLambdaをそれぞれ配備します。提供者をCognitoの `own-supply`、利用者を `use-finance`、全体監査担当者を `audit` グループに追加してください。

独自の接続先は [設定例](docs/examples/bindings.json) を編集し、`task deploy -- --bindings ファイル名` で指定します。Lambdaは `kind` に `lambda`、`address` に関数ARNを指定します。HTTPSは必要に応じて `secret_arn` に接続用BearerトークンのSecrets Manager ARNを指定し、提供元でも呼び出しを制限します。委任された接続先の配下なら、提供チームが画面でベースパスと [OpenAPI](docs/examples/stock.openapi.json) を登録できます。

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

配備テストは、合成したテンプレートから DB 移行 Lambda をエミュレーターに作成し、本番と同じ配布 ZIP が登録されたことを SHA-256 で照合します。エミュレーターの Python 実行環境ではネイティブ拡張を読み込めないため、同じ ZIP を展開した CPython 環境で、一時 PostgreSQL（`pg_config`、`initdb`、`pg_ctl` が必要）に Aurora DSQL 方言で接続し、移行ハンドラーの新規実行と再実行を検証します。Aurora DSQL が拒否する `public` スキーマへの直接の権限変更をテストでも拒否し、実行ロールが引き継いだ `USAGE` とテーブル権限を確認します。実 AWS の DSQL 接続、IAM 認証、CloudFormation カスタムリソースのコールバックは本番デプロイで確認します。


## CDKの構成と検証レポート

データベース・移行、API実行、ゲートウェイ、画面配信、認証、接続先設定を個別のコンストラクトで管理します。スタックとタグ対応リソースには `Application=TsugiteAPI`、`ManagedBy=AWS-CDK`、所属を示す `Component` を設定します。CloudFormationでタグを指定できない型には、同じ情報をテンプレートの `Metadata.Tsugite` に記録します。

GitHub Actions の **Verify** から成果物 **contracts-and-test-results** 内の `test-report.html` または `test-report.pdf` を開くと、ケースごとの期待結果、成否、実行時間、実際の画面とタグ一覧を確認できます。手元では通常のテストに `--junitxml=artifacts/junit.xml`、エミュレーターのテストに `--junitxml=artifacts/aws-emulator.xml` を付けて実行し、`task report` で同じレポートを作れます。

[ポータルの画面仕様と業務フロー](docs/design/portal.md)。デモ起動中に別の端末で `task seed` を実行すると、SQLiteの見本データを持つ12商品が公開されます。`task seed -- --editions 20` では20拠点分の240件を作成します。過去に同じデモ商品を登録した環境で再実行すると、旧仕様を新版に更新して再公開します。仕様を変更した商品の既存の利用権はポータルの規則に従い再申請が必要です。

[商品別のOpenAPI YAML](docs/generated/sample-api/) は `task docs:samples` で再生成できます。各商品の5つの業務操作と `GET /health` を掲載しています。商品ごとの実装は [packages/sample_api](packages/sample_api/src/sample_api/products/) にあります。AWSの標準構成では環境別の既存の接続先（例：`stock-sandbox`）を選び、ベースパスを `/<商品slug>` に設定します。画面はJSON入力なので、例えば配送追跡は次のコマンドで同じ定義をJSONにして登録します。

```bash
uv run --locked --all-packages python -c 'import json; from sample_api.products.parcel_tracking import app; print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))' > parcel-tracking.json
```

旧在庫APIの `/items` と `/items/{sku}` は引き続きベースパスなしで呼べます。サンプルのデータはLambdaの実行環境内に保持し、発注は入力数量で結果を試算します。
