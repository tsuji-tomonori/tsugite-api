import json
import os
import re
from collections.abc import Callable, Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect, sync_playwright

from tests.support.catalog import FORM, approved, headers
from tests.support.catalog_journey import browser_evidence, navigate
from tests.support.portal_server import serve_portal

PortalSession = tuple[httpx.Client, Page, Callable[[Page | Locator, str, str], None]]


@pytest.fixture
def portal_session(tmp_path: Path, request: pytest.FixtureRequest) -> Iterator[PortalSession]:
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": f"sqlite:///{tmp_path / 'portal.db'}"}
    with (
        serve_portal(env) as url,
        httpx.Client(base_url=url, trust_env=False) as api,
        sync_playwright() as pw,
    ):
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        page = browser.new_page()
        with browser_evidence(request.node, request.node.name, page, page) as capture:
            yield api, page, capture
        browser.close()


def open_portal(api: httpx.Client, page: Page, role: str) -> None:
    page.goto(str(api.base_url))
    page.get_by_role("button", name=role, exact=True).click()
    expect(page.get_by_role("button", name="ナビゲーション", exact=True)).to_be_visible()


def publish(
    api: httpx.Client, owner: dict[str, str], form: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    product = api.post("/api/apis", headers=owner, json=form).raise_for_status().json()
    url = "/api/apis/" + product["id"]
    return url, api.put(url + "/publication?published=true", headers=owner).raise_for_status().json()


def test_withdraw_pending(portal_session: PortalSession) -> None:
    """利用者が承認待ちの申請を取り下げると画面に反映され、同じ環境に再申請できる。"""
    api, page, capture = portal_session
    owner, user = (headers(api, role) for role in ("provider", "consumer"))
    url, _ = publish(api, owner, FORM)
    data = {"environment": "sandbox", "project": "finance", "reason": "利用検討"}
    assert (
        api.post(url + "/requests", headers=user, json=data).raise_for_status().json()["status"]
        == "pending"
    )
    open_portal(api, page, "利用チーム")
    navigate(page, "自分の申請")
    page.get_by_label("判断・取下げの理由").fill("利用計画変更")
    page.get_by_role("button", name="申請を取り下げる").click()
    expect(page.get_by_text(re.compile("finance · 検証 · 取下げ済み"))).to_be_visible()
    capture(page, "withdrawn", "利用者が取り下げた検証環境の申請")
    assert (
        api.post(url + "/requests", headers=user, json=data).raise_for_status().json()["status"]
        == "pending"
    )


def test_release_history(portal_session: PortalSession) -> None:
    """利用者が商品画面で旧版と新版の版番号、追加された操作と提供者の説明を確認できる。"""
    api, page, capture = portal_session
    owner = headers(api, "provider")
    url, first = publish(api, owner, FORM)
    update = deepcopy(FORM)
    update["spec"]["info"]["version"] = "2.0"
    update["spec"]["paths"]["/health"] = deepcopy(update["spec"]["paths"]["/items"])
    api.put(
        url,
        headers=owner,
        params={"revision": first["revision"]},
        json={**update, "release_note": "稼働状況を追加"},
    ).raise_for_status()
    api.put(url + "/publication?published=true", headers=owner).raise_for_status()
    open_portal(api, page, "利用チーム")
    navigate(page, "APIカタログ")
    page.get_by_role("link", name="在庫", exact=True).click()
    history = page.locator("details").filter(has=page.locator("summary", has_text="公開版の変更履歴"))
    history.locator("summary").click()
    for expected in ("第1版 · API 1.0", "第2版 · API 2.0", "追加　GET /health", "稼働状況を追加"):
        expect(history).to_contain_text(expected)
    capture(page, "versions", "公開版ごとの仕様と追加された操作")


def test_ordered_review(portal_session: PortalSession) -> None:
    """部署リーダーの判断が済むまで提供者は承認できず、最終承認後に呼び出しが成功する。"""
    api, page, capture = portal_session
    admin, owner, user = (headers(api, role) for role in ("admin", "provider", "consumer"))
    api.put(
        "/api/workspace/units/review", headers=admin, json={"name": "審査部", "kind": "department"}
    ).raise_for_status()
    lead = (
        api.post(
            "/api/members",
            headers=admin,
            json={"email": "lead@example.org", "role": "consumer", "project": "finance"},
        )
        .raise_for_status()
        .json()
    )
    for subject, leader in (("consumer", False), (lead["subject"], True)):
        api.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"subject": subject, "unit_id": "review", "leader": leader},
        ).raise_for_status()
    url, asset = publish(
        api,
        owner,
        {**FORM, "offers": {"sandbox": {"route": "custom", "steps": ["unit/review", "provider"]}}},
    )
    row = (
        api.post(
            url + "/requests",
            headers=user,
            json={"environment": "sandbox", "project": "finance", "reason": "棚卸"},
        )
        .raise_for_status()
        .json()
    )
    endpoint = "/api/requests/" + row["id"]

    def decide(actor: dict[str, str], revision: int) -> httpx.Response:
        return api.post(
            endpoint,
            headers=actor,
            json={"action": "approve", "reason": "確認済み", "revision": revision},
        )

    assert decide(owner, row["revision"]).status_code == 403
    path = f"/api/invoke/{asset['id']}/sandbox/finance/items"
    assert api.get(path, headers=user).status_code == 403
    row = decide(headers(api, "lead@example.org"), row["revision"]).raise_for_status().json()
    assert row["stage"] == "provider" and row["status"] == "pending"
    assert api.get(path, headers=user).status_code == 403
    open_portal(api, page, "提供チーム")
    navigate(page, "届いた申請")
    page.get_by_label("判断・取下げの理由").fill("本番前確認")
    page.get_by_role("button", name="承認", exact=True).click()
    expect(page.get_by_text("申請状態を更新しました")).to_be_visible()
    assert api.get(path, headers=user).status_code == 200
    capture(page, "approved", "部署リーダーに続いて提供者が最終承認した申請")


def test_admin_stops_target_after_denial(portal_session: PortalSession) -> None:
    """拒否を記録した対象APIを管理者が一時停止し、許可済みの呼び出しだけを対象別に止められる。"""
    api, page, capture = portal_session
    owner, user = (headers(api, role) for role in ("provider", "consumer"))
    asset, url, path = approved(api, owner, user)
    assert api.put(url + "/suspension?suspended=true", headers=owner).status_code == 403
    _, _, other_path = approved(api, owner, user)
    assert api.get(path, headers=user).status_code == 200
    assert api.get(other_path, headers=user).status_code == 200
    denied = api.get(path.replace("/sandbox/", "/production/"), headers=user)
    assert denied.status_code == 403
    logs = (
        api.get("/api/access-logs", headers=headers(api, "admin"), params={"asset_id": asset})
        .raise_for_status()
        .json()
    )
    assert any(
        row["request_id"] == denied.headers["x-request-id"] and row["status"] == 403 for row in logs
    )
    open_portal(api, page, "管理者")
    navigate(page, "アクセスログ")
    row = page.locator(".audit-row").filter(has_text=denied.headers["x-request-id"])
    row.get_by_role("button", name="対象APIを開く").click()
    stop = page.get_by_role("button", name=re.compile(r"API.*一時停止|全アクセス.*停止"))
    expect(stop).to_be_visible()
    page.on("dialog", lambda dialog: dialog.accept())
    stop.click()
    expect(page.get_by_role("button", name=re.compile("再開"))).to_be_visible()
    assert api.get(path, headers=user).status_code == 403
    assert api.get(other_path, headers=user).status_code == 200
    capture(page, "suspended", "拒否を検知した対象APIの一時停止")
    page.get_by_role("button", name="APIへのアクセスを再開").click()
    expect(stop).to_be_visible()
    assert api.get(path, headers=user).status_code == 200


def test_auditor_cross_checks_exports(portal_session: PortalSession) -> None:
    """監査担当が他の利用者のアクセスと業務監査を同じIDで照合し、両方の記録を保存できる。"""
    api, page, capture = portal_session
    owner, user = (headers(api, role) for role in ("provider", "consumer"))
    _, _, path = approved(api, owner, user)
    trace = api.get(path, headers=user).raise_for_status().headers["x-request-id"]
    open_portal(api, page, "監査担当")
    navigate(page, "アクセスログ")
    page.get_by_label("照合するリクエストID").fill(trace)
    page.get_by_role("button", name="IDで検索").click()
    row = page.locator(".audit-row").filter(has_text=trace)
    expect(row).to_contain_text("consumer")
    expect(row).to_contain_text("200")
    with page.expect_download() as access_file:
        page.get_by_role("button", name="アクセスログをダウンロード").click()
    access = [
        json.loads(line) for line in access_file.value.path().read_text(encoding="utf-8").splitlines()
    ]
    assert [(r["request_id"], r["actor"], r["status"]) for r in access] == [(trace, "consumer", 200)]
    capture(page, "access-export", "監査担当が保存したアクセス記録")
    row.get_by_role("button", name="対応する業務監査").click()
    expect(page.get_by_label("リクエストID", exact=True)).to_have_value(trace)
    with page.expect_download() as audit_file:
        page.get_by_role("button", name="業務監査をダウンロード").click()
    audit = [
        json.loads(line) for line in audit_file.value.path().read_text(encoding="utf-8").splitlines()
    ]
    assert {r["request_id"] for r in audit} == {trace}
    assert {r["action"] for r in audit} == {"invoke.start", "invoke.end"}
    capture(page, "trace-audit", "同じ実行の開始と終了を照合した監査担当の画面")


def test_provider_shortens_token_lifetime(portal_session: PortalSession) -> None:
    """提供者が商品ごとのトークンの上限を短縮すると、利用者による上限超過の発行を拒否する。"""
    api, page, capture = portal_session
    owner, user = (headers(api, role) for role in ("provider", "consumer"))
    asset, _, _ = approved(api, owner, user)
    open_portal(api, page, "提供チーム")
    navigate(page, "提供するAPI")
    page.get_by_role("link", name="在庫", exact=True).click()
    page.get_by_role("button", name="アクセストークンの上限を設定").click()
    page.get_by_label("この範囲の上限（分）").fill("5")
    page.get_by_role("button", name="有効期限の上限を保存").click()
    expect(page.get_by_text("有効期限の上限を保存しました")).to_be_visible()
    data = {
        "name": "棚卸",
        "mode": "bearer",
        "kind": "personal",
        "project": "finance",
        "api_ids": [asset],
        "ttl_minutes": 6,
        "refresh_minutes": 2,
    }
    assert api.post("/api/credentials", headers=user, json=data).status_code == 422
    assert api.post("/api/credentials", headers=user, json={**data, "ttl_minutes": 5}).is_success
    capture(page, "api-limit", "提供者が商品に設定した有効期限の上限")
