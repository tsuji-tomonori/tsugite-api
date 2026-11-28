# **開発者**は、**ポータル**を**配備**するとき、**API**を単一の入口で提供できる

## 背景

ポータルはAWS内で画面・認証・API・データベースを運用する。

## なぜ必要か

アクセスの入口を集約し、利用の少ない時間帯に常時稼働の費用を増やさないため。

## 決めた方針

CloudFrontを入口とし、非公開S3、API Gateway、Lambda、Cognito、Aurora DSQLを利用する。従量課金を基本とし、NATゲートウェイを必要としない構成にする。

> 実装検証 test_access_boundaries test_cost_drivers_are_bounded test_portal_origin_with_valid_access_token test_gateway_authorizer_rechecks_each_invocation — CloudFrontとオリジンの制限は合成テンプレートと実ハンドラーで確認する。

### 受入テスト

- 受入テスト `packages/infra/tests/test_stack.py::test_access_boundaries`
- 受入テスト `packages/infra/tests/test_cost.py::test_cost_drivers_are_bounded`
- 受入テスト `packages/backend/tests/test_auth.py::test_portal_origin_with_valid_access_token`
- 受入テスト `packages/backend/tests/test_gateway_event.py::test_gateway_authorizer_rechecks_each_invocation`

配備後は、同じスタックのヘルスチェックが CloudFront 経由で 200、API Gateway 直アクセスで入口拒否の 403 になることを Deploy to AWS で確認する。さらに `tests/e2e/deployed/test_portal.py::test_authenticated_origin_boundary` は、MFA後の同じアクセストークンで `GET /api/me` を呼び、CloudFront の 200 と専用利用者の本人情報、API Gateway の入口拒否の 403 を照合する。

## 却下した方針

外部SaaSや常時稼働するNATゲートウェイを前提とする構成は採用しない。

### 変更履歴

- 2026-11-25 有効な利用者認証情報があっても配信元を確認することを保証するため、正規経路と直アクセスを比較する検証を追加した。

- 2026-11-26 方針ごとの検証先と観測する結果を明記した。

- 2026-11-28 単一入口の保証を、配備先で正規の利用者トークンを使った本人照会でも検証する。
