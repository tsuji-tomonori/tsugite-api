# **管理者**は、**API**のエラーを調べるとき、**運用ログ**から対象と復旧作業を確認できる

## 背景

**運用ログ**（処理の発生箇所、結果、対象、復旧作業を1件ずつJSONで記録したもの）をAPI、認可、チャットワーカー、推論モデル、DB移行、ポータル画面で使う。

## なぜ必要か

同じ503でも、一時的な通信障害と、片方のシステムにだけデータが残った状態では対応が異なる。

## 決めた方針

| level | 判定 | 例 |
| --- | --- | --- |
| INFO | 正常に処理した | カタログ取得 |
| WARN | 利用者が入力や権限を見直す必要がある | 入力不備、未認証、権限不足 |
| ERROR | サーバー・接続先・画面の処理で失敗した | DB接続失敗、予期しない描画例外 |
| CRITICAL | 運用担当者による復旧作業が必要と判明した | カタログの保存JSONの破損、Cognitoとポータル間の利用者削除の未完了 |

サーバーの各イベントはCloudWatch Logs、画面内で起きたイベントはブラウザーコンソールに出力する。UTCの発生日時は `at`、発生元は `source`、原因は `reason` を見る。APIの呼び出しは `request_id` で応答ヘッダーの `X-Request-ID` と照合する。画面からのアクセスでは `screen` に画面IDを記録する。

`method` と `route` は呼び出したAPI、`asset_id` はカタログの商品、`operation` は転送先の操作や画面内の処理を示す。`actor_id` は操作した利用者またはシステム、`target_subject_id` は操作対象として特定した利用者を示す。該当しない項目や特定できない項目は null とする。認証ヘッダー、クエリ文字列、リクエスト本文、例外の自由記述は記録しない。

CRITICAL の `operator_action` には対象、照合するデータ、修正または再実行する操作、復旧の確認方法を日本語で記載する。API呼び出し履歴のJSONLには発生時の分類を引き継ぐ。旧形式の履歴は保存済みのHTTPステータスから分類し、当時記録していない画面や作業は null とする。

利用者一覧を取得する際、外部名簿との通信や名簿サービスの障害で結果を確認できなければ503を返す。復旧後、管理者は同じページを再取得できる。招待先のアカウントを作成する前に名簿サービスが一時停止した場合も503を返し、復旧後に同じ利用者を招待できる。

### 受入テスト

- 受入テスト `packages/backend/tests/test_required_member_directory.py::test_directory_temporarily_unavailable`

- 受入テスト `packages/backend/tests/test_request_logs.py::test_http_log`
- 受入テスト `packages/backend/tests/test_request_logs.py::test_member_partial_deletion`
- 受入テスト `packages/frontend/tests/test_screen_logs.py::test_screen_error_context`

## 却下した方針

すべての5xxを一律にCRITICALとする案では、担当者による復旧が必要なものを識別できない。
