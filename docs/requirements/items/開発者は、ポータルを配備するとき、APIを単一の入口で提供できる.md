# **開発者**は、**ポータル**を**配備**するとき、**API**を単一の入口で提供できる

## 背景

ポータルはAWS内で画面・認証・API・データベースを運用する。

## なぜ必要か

アクセスの入口を集約し、利用の少ない時間帯に常時稼働の費用を増やさないため。

## 決めた方針

CloudFrontを入口とし、非公開S3、API Gateway、Lambda、Cognito、Aurora DSQLを利用する。従量課金を基本とし、NATゲートウェイを必要としない構成にする。

### 受入テスト

- 受入テスト `packages/infra/tests/test_stack.py::test_access_boundaries`
- 受入テスト `packages/infra/tests/test_cost.py::test_cost_drivers_are_bounded`

## 却下した方針

外部SaaSや常時稼働するNATゲートウェイを前提とする構成は採用しない。
