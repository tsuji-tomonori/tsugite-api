"""MFAログイン後のカタログ表示と、同じアクセストークンによるCloudFront経由の本人照会・直接アクセス拒否を検証する。"""

import os
import time

import httpx
import pytest
from playwright.sync_api import sync_playwright

from tests.e2e.deployed.account import gateway_origin, is_test_consumer, portal_origin, totp


def test_public_cloudfront_api() -> None:
    """実配信経路でヘルスとログイン設定を取得でき、未ログインの本人情報取得は拒否される。"""
    origin = portal_origin(os.environ["E2E_PORTAL_URL"])
    with httpx.Client(base_url=origin, timeout=45) as client:
        health = client.get("/api/health")
        assert health.headers.get("x-amz-cf-id")
        assert health.status_code == 200 and health.json() == {"status": "ok"}
        config = client.get("/api/config")
        assert config.status_code == 200 and config.json()["demo"] is False
        assert client.get("/api/me").status_code == 401


@pytest.fixture(scope="module")
def signed_in_consumer():
    """専用利用者として一度だけMFAログインし、画面と本人情報の応答を共有する。"""
    origin = portal_origin(os.environ["E2E_PORTAL_URL"])
    subject = os.environ["E2E_SUBJECT"]
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        page.set_default_timeout(60_000)
        print("CloudFront のログイン画面を開く", flush=True)
        page.goto(origin)
        assert page.url == origin + "/"
        page.get_by_label("ユーザー名", exact=True).fill(os.environ["E2E_USERNAME"])
        page.get_by_label("パスワード", exact=True).fill(os.environ["E2E_PASSWORD"])
        page.get_by_role("button", name="ログイン", exact=True).click()
        print("パスワード送信後の MFA チャレンジを確認", flush=True)
        page.get_by_role("heading", name="本人確認", exact=True).wait_for()
        # 再実行や並列ジョブで同じコードを使わず、有効期限まで余裕を持って入力する。
        time.sleep(30 - time.time() % 30 + 1)
        code = totp(os.environ["E2E_TOTP_SEED"], int(time.time()))
        page.get_by_label("確認コード", exact=True).fill(code)
        print("MFA を送信して本人情報を照合", flush=True)
        with page.expect_response(origin + "/api/me") as me:
            page.get_by_role("button", name="確認してログイン", exact=True).click()
        assert me.value.status == 200 and is_test_consumer(me.value.json(), subject)
        assert me.value.header_value("x-amz-cf-id")
        try:
            yield page, me.value
        finally:
            browser.close()


def test_consumer_login_and_catalog(signed_in_consumer) -> None:
    """MFAでログインした専用利用者がカタログを開くと、取得した件数が画面に表示される。"""
    page, _ = signed_in_consumer
    origin = portal_origin(os.environ["E2E_PORTAL_URL"])
    print("カタログを開いて取得結果の表示を確認", flush=True)
    with page.expect_response(origin + "/api/catalog-page?*") as catalog:
        page.get_by_role("navigation", name="ポータル").get_by_role(
            "button", name="APIカタログ", exact=True
        ).click()
    assert catalog.value.status == 200
    data = catalog.value.json()
    assert isinstance(data["items"], list)
    page.get_by_role("heading", name=f"API一覧（{data['total']}件）", exact=True).wait_for()


def test_authenticated_origin_boundary(signed_in_consumer) -> None:
    """同じBearerで本人情報を取得すると、CloudFrontは本人を返し、API Gatewayは入口で拒否する。"""
    _, me = signed_in_consumer
    gateway = gateway_origin(os.environ["E2E_GATEWAY_ENDPOINT"])
    authorization = me.request.header_value("authorization")
    if (
        not authorization
        or not authorization.startswith("Bearer ")
        or not authorization.removeprefix("Bearer ").strip()
    ):
        pytest.fail("本人情報のリクエストにアクセストークンがありません", pytrace=False)

    # Cookieやオリジン検証用ヘッダーを引き継がず、両経路に同じBearerだけを送る。
    headers = {"Authorization": authorization}
    with httpx.Client(timeout=45, follow_redirects=False, headers=headers) as client:
        public = client.get(me.url)
        assert public.status_code == 200 and public.headers.get("x-amz-cf-id")
        assert is_test_consumer(public.json(), os.environ["E2E_SUBJECT"])
        direct = client.get(gateway + "/api/me")
        assert direct.status_code == 403
        if direct.json() != {"detail": "入口を確認してください"}:
            pytest.fail("403の理由が入口拒否と一致しません", pytrace=False)
