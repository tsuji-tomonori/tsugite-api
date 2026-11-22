import os
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect, sync_playwright

from tests.support.catalog import FORM, headers
from tests.support.catalog_journey import browser_evidence, navigate
from tests.support.portal_server import serve_portal


def test_provider_policy_console(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    """提供者が公開・自動承認・委任の条件を保存し、部署リーダーが個人申請を画面から却下する"""
    env = {**os.environ, "TSUGITE_DEMO": "1", "DATABASE_URL": "sqlite:///" + str(tmp_path / "policy.db")}
    with (
        serve_portal(env) as url,
        httpx.Client(base_url=url, trust_env=False) as api,
        sync_playwright() as pw,
    ):
        admin, provider, user = (headers(api, p) for p in ("admin", "provider", "consumer"))
        dept = "planning"
        api.put(
            "/api/workspace/units/" + dept, headers=admin, json={"kind": "department", "name": "企画部"}
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
        for subject, is_lead in (("consumer", False), (lead["subject"], True)):
            api.put(
                "/api/workspace/memberships",
                headers=admin,
                json={"subject": subject, "unit_id": dept, "leader": is_lead, "title": "担当"},
            ).raise_for_status()
        asset = api.post("/api/apis", headers=provider, json=FORM).raise_for_status().json()["id"]
        api.put(
            "/api/apis/" + asset + "/publication?published=true", headers=provider
        ).raise_for_status()
        browser = pw.chromium.launch(executable_path=os.getenv("CHROMIUM_PATH") or None)
        publisher, leader = (browser.new_page(viewport={"width": 1440, "height": 960}) for _ in range(2))
        with browser_evidence(request.node, "approval-policy", publisher, leader) as capture:
            publisher.goto(url)
            publisher.get_by_role("button", name="提供チーム", exact=True).click()
            navigate(publisher, "提供するAPI")
            publisher.get_by_role("link", name="在庫", exact=True).click()
            publisher.get_by_text("公開範囲と承認ルール", exact=True).click()
            publisher.get_by_label("カタログの公開範囲").select_option("restricted")
            for group in ("公開先部署", "判断を委任する部署のリーダー"):
                publisher.get_by_role("group", name=group, exact=True).get_by_role(
                    "checkbox", name="企画部"
                ).check()
            publisher.get_by_label("自動承認する役職", exact=False).fill("部長")
            publisher.get_by_role("button", name="公開・承認条件を保存").click()
            expect(publisher.get_by_text("公開範囲と承認ルールを保存しました")).to_be_visible()
            summary = publisher.get_by_text("公開範囲と承認ルール", exact=True)
            if summary.locator("..").get_attribute("open") is None:
                summary.click()
            capture(
                publisher,
                "policy",
                "提供者の公開条件。企画部に限定し、部長は自動承認、その他は企画部リーダーに委任",
            )
            request_data = {
                "personal": True,
                "project": "finance",
                "reason": "部内検証",
                "environment": "sandbox",
            }
            row = (
                api.post("/api/apis/" + asset + "/requests", headers=user, json=request_data)
                .raise_for_status()
                .json()
            )
            assert row["status"] == "pending"
            leader.goto(url)
            leader.get_by_text("追加したユーザーでログイン").click()
            leader.get_by_label("登録メールアドレス").fill("lead@example.org")
            leader.get_by_role("button", name="このユーザーでログイン").click()
            navigate(leader, "届いた申請")
            expect(leader.get_by_text("個人申請　申請者 consumer")).to_be_visible()
            leader.get_by_label("判断・取下げの理由").fill("対象環境を再確認してください")
            capture(leader, "delegate", "提供者から委任された企画部リーダーが、個人申請と利用目的を確認")
            leader.get_by_role("button", name="却下", exact=True).click()
            expect(leader.get_by_text("申請状態を更新しました")).to_be_visible()
            assert api.get(f"/api/invoke/{asset}/sandbox/finance/items", headers=user).status_code == 403
            api.put(
                "/api/workspace/memberships",
                headers=admin,
                json={"subject": "consumer", "unit_id": dept, "leader": False, "title": "部長"},
            ).raise_for_status()
            auto = api.post("/api/apis/" + asset + "/requests", headers=user, json=request_data)
            assert auto.raise_for_status().json()["status"] == "approved"
            consumer = browser.new_page()
            consumer.goto(url)
            consumer.get_by_role("button", name="利用チーム", exact=True).click()
            navigate(consumer, "自分の申請")
            expect(consumer.get_by_text("finance · 検証 · 利用中", exact=False)).to_be_visible()
            capture(consumer, "auto-approved", "役職の条件に一致して承認された利用申請")
        browser.close()
