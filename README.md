# Tsugite API · 継手API

社内のAPIを一か所で探し、プロジェクト単位で利用を申請できるカタログです。[目的と要件](docs/requirements/README.md)

## 手元で試す

```sh
uv sync --locked
uv run python tools/manage.py demo
```

`http://127.0.0.1:8000` で「提供チーム」を選び、API名と用途を入力します。検証の接続先に `sample-sandbox` を選び、用意されたOpenAPIを使って公開できます。別のタブで「利用チーム」を選ぶと、申請、承認後の呼び出し、取消後の拒否を試せます。

## コミット前の設定

クローンごとに最初の1回、リポジトリのルートで実行します。

```sh
git config --local core.hooksPath .githooks
git config --local commit.template .gitmessage.txt
```

`git commit` の編集画面にテンプレートが表示されます。件名は [Conventional Commits](https://www.conventionalcommits.org/ja/v1.0.0/) の形式で書きます。たとえば `git commit -m "fix(api): 利用申請のエラー表示を修正"` とします。件名の形式が違う場合は、ローカルの `commit-msg` フックがコミットを中止します。

マージコミットを作る場合は `git merge -m "chore: 機能ブランチを統合" <ブランチ名>` のように件名を指定します。変更を取り消す場合は `git revert --no-commit <コミット>` の後、`git commit -m "revert: 利用申請の変更を取り消す"` のようにコミットします。

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

## 商品としてAPIを公開する

「提供するAPI」→「APIを登録」で、基本版（検証）、準本番、本番から出品する環境と接続先を選びます。OpenAPI 3.0 / 3.1のJSON（内部参照のみ、500KB以内）を選ぶと、API名と説明を仕様から取り込めます。「保存して公開」で商品画面に全操作を掲載します。限定公開にする場合は下書きを保存し、公開範囲を設定してから公開します。

環境ごとの「利用・承認条件」では、利用説明、同意が必要な規約、申請項目と承認順を指定します。例えば、本番に「テスト実施ID」を必須項目として追加し、「受理する値」に発行済みIDを1行ずつ登録すると、一致した申請だけが承認フローに進みます。自動承認でも規約と入力条件を確認します。IDの照合元は提供者が登録した値です。

「所属部署が承認 → 提供者が承認」を選ぶと、申請者の所属部署またはその上位部署のリーダーに届き、承認後に提供者に届きます。「承認者と順番を指定」では、特定部署を含む段階を順番に追加できます。最後の承認で、申請した商品・環境に利用権が発生します。既存商品の「商品共通の承認ルール」はこれまでどおり利用できます。

商品画面の「API操作一覧」から各操作に移動し、承認済みの環境とキーで実行できます。「公開版の変更履歴」にはAPI版、OpenAPI仕様版、操作やモデルの差分、提供者の変更説明が残ります。AWSでは正規化したJSONを非公開のバージョニング有効S3バケットに保存し、ポータルの表示と実行にはDB側の検証済み定義を使用します。

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

[ポータルの画面仕様と業務フロー](docs/design/portal.md)。デモ起動中に別の端末で `uv run python tools/seed_marketplace.py --editions 20` を実行すると、在庫・配送・為替・店舗・発注・営業日の6種類を20拠点分、計120件公開できます。同じ名前の出品は再利用します。デモでの実行結果は接続情報の折り返しです。業務ごとの応答はHTTPS接続のE2Eで確認します。
