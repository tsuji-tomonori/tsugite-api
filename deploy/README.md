# GitHub Actions から AWS に配備する

GitHub Actions の `Verify / test` は、main 宛ての PR の作成・更新・再開時に実行します。設計書とテストレポートは PR の `contracts-and-test-results` から取得できます。

`Deploy to AWS` は、main の更新時に GitHub API でマージ済み PR とコミットを照合します。一致したコミットが main の先頭にある場合に、配布物をビルドして CDK で配備し、スタックのカスタムリソースでDBを移行します。

## 初回設定

1. 配備先の AWS アカウントとリージョンで CDK の `CDKToolkit` が利用できることを確認します。初回は AWS 管理者が既定の qualifier `hnb659fds` でブートストラップします。CloudFormation 実行ロールの権限は、ブートストラップ時に選んだ実行ポリシーで決まります。継手APIのリソースを作成・更新できる実行ポリシーを使用してください。
2. 同じアカウント・リージョンで、[CloudFormation テンプレート](../aws/github-actions-oidc.yml) から IAM ロールを作成します。すでに AWS IAM に `token.actions.githubusercontent.com` が登録されている場合は、クライアントIDに `sts.amazonaws.com` があることを確認し、`CreateGitHubOidcProvider=false` を指定します。
3. GitHub の **Settings → Secrets and variables → Actions → Variables** に、`AWS_REGION` と `AWS_DEPLOY_ROLE_ARN` を登録します。前者は CloudFormation を配備したリージョン、後者はスタックの出力 `GitHubDeployRoleArn` です。
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

GitHub の短期認証情報は、指定リポジトリの main を示す OIDC トークンだけに発行します。作成する IAM ロールは、同一アカウント・リージョンの CDK 配備ロールと S3 アセット公開ロールを引き受けます。OIDC プロバイダーはアカウント内の他のリポジトリでも共有するため、削除時は保持します。
