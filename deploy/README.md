# GitHub Actions から AWS に配備する

GitHub Actions の `Verify / test` は、main 宛ての PR の作成・更新・再開時に実行します。設計書とテストレポートは PR の `contracts-and-test-results` から取得できます。

`Deploy to AWS` は、main の更新時に GitHub API でマージ済み PR とコミットを照合します。一致したコミットが main の先頭にある場合に、配布物をビルドして CDK で配備し、スタックのカスタムリソースでDBを移行します。

## 初回設定

1. 配備先の AWS アカウントとリージョンで CDK の `CDKToolkit` が利用できることを確認します。初回は AWS 管理者が既定の qualifier `hnb659fds` でブートストラップします。CloudFormation 実行ロールの権限は、ブートストラップ時に選んだ実行ポリシーで決まります。継手APIのリソースを作成・更新できる実行ポリシーを使用してください。
2. 同じアカウント・リージョンで、[CloudFormation テンプレート](aws/github-actions-oidc.yml) から IAM ロールを作成します。すでに AWS IAM に `token.actions.githubusercontent.com` が登録されている場合は、クライアントIDに `sts.amazonaws.com` があることを確認し、`CreateGitHubOidcProvider=false` を指定します。
3. GitHub の **Settings → Environments** に `main` を作成します。**Deployment branches and tags** で **Selected branches and tags** を選び、種類 **Branch** の `main` を追加します。**Environment variables** に `AWS_REGION` と `AWS_DEPLOY_ROLE_ARN` を登録します。前者は CloudFormation を配備したリージョン、後者はスタックの出力 `GitHubDeployRoleArn` です。
4. 対象 PR の `test` が成功したら main にマージします。**Actions → Deploy to AWS** でマージ判定と配備の結果を確認します。

リポジトリのルートで実行する例です。リージョンと `create_provider` は配備先に合わせて指定します。

```bash
region=ap-northeast-1
create_provider=true

aws cloudformation deploy \
  --region "$region" \
  --stack-name tsugite-github-actions-oidc \
  --template-file deploy/aws/github-actions-oidc.yml \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides "CreateGitHubOidcProvider=$create_provider"

aws cloudformation describe-stacks \
  --region "$region" \
  --stack-name tsugite-github-actions-oidc \
  --query "Stacks[0].Outputs[?OutputKey=='GitHubDeployRoleArn'].OutputValue | [0]" \
  --output text
```

## 既存の OIDC スタックを更新する

Environment を参照するワークフローをマージする前に、AWS の `tsugite-github-actions-oidc` スタックをこのテンプレートで更新します。CloudFormation の更新画面では既存の `CreateGitHubOidcProvider` の値を引き継ぎます。更新完了後に PR をマージします。

GitHub Job に Environment を設定すると、OIDC トークンの `sub` は Environment 名を含みます。IAM はこの `sub` と `ref` の両方を照合し、継手API リポジトリの `main` ブランチから `main` Environment を使うジョブに短期認証情報を発行します。作成する IAM ロールは、同一アカウント・リージョンの CDK 配備ロールと S3 アセット公開ロールを引き受けます。OIDC プロバイダーはアカウント内の他のリポジトリでも共有するため、削除時は保持します。

## 初回ログイン用の管理者を作成する

1. `TsugiteApi` の配備後、AWS 管理者が下記のコマンドで既存の OIDC スタックを更新します。`BootstrapAdminUserPoolId` に指定したプールだけを CD ロールで操作できます。既存の OIDC プロバイダー設定は引き継ぎます。
2. GitHub の **Settings → Environments → main → Environment secrets** に `BOOTSTRAP_ADMIN_EMAIL` を登録します。値は初回ログインを担当する本人のメールアドレスです。
3. **Actions → Create initial administrator → Run workflow** でブランチ `main` を選んで実行します。`invite` で Cognito が招待メールを送信し、`grant` でそのユーザーを `admin` グループに追加します。
4. 両ジョブの成功後、ポータルの **社内アカウントでログイン** を開きます。ユーザー名 `initial-admin` とメールの仮パスワードで入り、新しいパスワードと認証アプリの MFA を設定します。

```bash
region=ap-northeast-1
pool=$(aws cloudformation describe-stacks --region "$region" --stack-name TsugiteApi \
  --query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue | [0]" --output text) &&
aws cloudformation deploy --region "$region" --stack-name tsugite-github-actions-oidc \
  --template-file deploy/aws/github-actions-oidc.yml --capabilities CAPABILITY_IAM \
  --parameter-overrides "BootstrapAdminUserPoolId=$pool"
```

管理者が登録済みなら、再実行しても招待は送られません。`grant` だけが失敗した場合は同じ実行の **Re-run failed jobs** を選ぶと、元の招待のユーザー識別子を照合して再開します。管理者が空で同名ユーザーがすでにいる場合は招待を停止します。AWS 管理者が Cognito と元の実行履歴で作成元を確認してください。

## CloudFront 経由の実環境 E2E

`Deploy to AWS` は配備が成功すると `CloudFront portal E2E` を呼び出します。配備をスキップしたコミットでは実行しません。**Actions → CloudFront portal E2E → Run workflow → main** から、再配備せずに同じ確認を実行できます。

| 確認 | 合格条件 |
| --- | --- |
| 公開 API | 配信 URL の `/api/health` が CloudFront の応答ヘッダー付きで稼働中を返し、`/api/config` でデモが無効、未ログインの `/api/me` が 401 |
| 利用者ログイン | 新規ブラウザーでポータルにアクセスし、パスワード入力後に「本人確認」が表示され、時間ベースの6桁コード送信後に `/api/me` が専用利用者の識別子と一般利用者権限を返す |
| カタログ | ログインした画面から「APIカタログ」を開き、一覧 API が 200 を返し、ブラウザーが応答の件数を表示する。公開商品が0件でも検証可能 |

### 初回設定

1. ポータルの管理者が、検証用プロジェクトの「利用者」として専用メールアドレスを招待します。管理者・監査担当・提供者・リーダー権限を持たないアカウントを使います。
2. GitHub の **Settings → Environments** に `cloudfront-e2e` を作成し、**Deployment branches and tags → Selected branches and tags** で Branch の `main` だけを許可します。
3. 招待された利用者としてポータルで初回パスワードを変更し、認証アプリ登録画面に表示される「設定キー」を下表の Secret に登録します。同じキーを認証アプリに登録して6桁コードで初回ログインを完了します。
4. 次の値をすべて同じ Environment に登録します。パスワードと設定キーの両方を扱える実行者は、この専用利用者としてログインできます。Environment の変更権限と main のワークフロー変更権限を管理してください。

| 種別 | 名前 | 値 |
| --- | --- | --- |
| Variable | `E2E_PORTAL_URL` | 対象スタック `TsugiteApi` の出力 `PortalUrl` |
| Variable | `E2E_SUBJECT` | 対象ユーザープールで専用利用者の属性に表示される `sub` |
| Secret | `E2E_USERNAME` | 招待時のユーザー名 |
| Secret | `E2E_PASSWORD` | 初回変更後のパスワード |
| Secret | `E2E_TOTP_SEED` | 初回登録した認証アプリの設定キー。毎回の6桁コードは実行時に生成 |

Actions の各ステップとログイン処理の進捗行で失敗箇所を確認できます。認証ステップの出力は段階名と合否に限定し、トレース・スクリーンショット・ブラウザーのセッションは保存しません。パスワード変更・認証アプリ再登録時は該当 Secret を更新します。設定不足や検証失敗はジョブの失敗となり、すでに配備したスタックは自動でロールバックされません。

## リビジョン 007 の適用後にロールバックが止まった場合

対象は東京リージョンの `TsugiteApi` スタックです。2026年11月22日の配備ではモデル関数の作成が失敗し、旧移行関数が適用済みの `007` を読み取れず、`Schema` のロールバックが停止しました。

1. 配備先アカウントでスタックの状態とイベントを確認します。以下の手順は、現在も `UPDATE_ROLLBACK_FAILED` で、ロールバック中の `Schema` の理由が `Can't locate revision identified by '007'` の場合に使います。ポータルの配布がキャンセルされた場合は、ロールバック再開時に再試行されます。
2. 接続権限のある運用者が DSQL で `SELECT version_num FROM alembic_version` を実行し、`007` と移行で追加した `inquiries` テーブルの存在を確認します。修正版の配布物に `v007_inquiries.py` が含まれていることを確認します。
3. DB と適用履歴を保持し、論理 ID `Schema` だけをスキップしてロールバックを再開します。

   ```bash
   aws cloudformation continue-update-rollback --region ap-northeast-1 \
     --stack-name TsugiteApi --resources-to-skip Schema
   ```

4. `UPDATE_ROLLBACK_COMPLETE` を確認して修正版を配備します。スキップしたリソースは次の更新で整合させる必要があります。`Schema` が `UPDATE_COMPLETE`、スタックが `UPDATE_COMPLETE` になったこと、チャットでモデルの応答が得られることを確認します。
