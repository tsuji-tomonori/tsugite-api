# 通知・利用上限・操作履歴とユーザー管理を、ポータルの利用手順と各APIの公開契約から検証する。
import asyncio
from unittest.mock import AsyncMock

import pytest
from test_components import render
from test_required_people_support import Module, Record, content, member, person, row_with


def target() -> Record:
    return {
        "asset_id": "inventory",
        "name": "在庫照会",
        "project": "stock",
        "project_label": "在庫管理",
        "id": "inventory/stock/sandbox",
        "environment": "sandbox",
    }


def test_recipient_reads_notice(portal_module: Module) -> None:
    """受信者は通知の件名と本文を確認し、未読の通知だけを既読にできる。"""
    ui = portal_module("runtime.portal_ui")
    notices = portal_module("components.notifications")
    item = {"project": "stock", "sender": "運用窓口", "at": "2026-04-07T03:08:09Z"}
    ui.ctx.update(
        me=member(),
        notice_offset=0,
        targets=[],
        notices={
            "unread": 1,
            "items": [
                dict(item, id="new", title="利用再開", body="出庫処理を再開しました", unread=True),
                dict(item, id="old", title="事前告知", body="定期点検の予定", unread=False),
            ],
        },
    )
    dom = render(notices.notices_view)[1]
    unread = row_with(dom, "利用再開")
    read = row_with(dom, "事前告知")
    assert "出庫処理を再開しました" in content(unread)
    assert "未読" in content(unread) and "既読" in content(read)
    assert any("既読" in content(el) for el in unread.getElementsByTagName("button"))
    assert all("既読" not in content(el) for el in read.getElementsByTagName("button"))


@pytest.mark.parametrize(
    ("admin", "provider", "expected"),
    [
        pytest.param(
            True,
            False,
            "全プロジェクト",
            id="admin",
            marks=pytest.mark.case_detail("管理者は全体または指定した所属先を選べる"),
        ),
        pytest.param(
            False,
            True,
            "在庫照会",
            id="provider",
            marks=pytest.mark.case_detail("提供者は申請元を宛先に選べる"),
        ),
    ],
)
def test_sender_audiences(portal_module: Module, admin: bool, provider: bool, expected: str) -> None:
    """通知送信フォームは送信者の役割に合う宛先と件名・本文の入力欄を表示する。"""
    notices = portal_module("components.notifications")
    dom = render(
        notices.notice_form, member(admin=admin, provider=provider), [("target", "在庫照会・在庫管理")]
    )[1]
    assert any(expected in content(o) for o in dom.getElementsByTagName("option"))
    assert dom.getElementsByTagName("textarea")
    assert any("送信" in content(node) for node in dom.getElementsByTagName("button"))


def test_alert_rule_table(portal_module: Module) -> None:
    """利用上限の表には対象API・環境・プロジェクトと通知のみか停止つきかを表示する。"""
    ui = portal_module("runtime.portal_ui")
    alerts = portal_module("components.alerts")
    ui.ctx.update(
        targets=[target()],
        rules=[
            dict(target(), minutes=15, threshold=37, calls=21, stop=False, enabled=True),
            dict(target(), name="配送照会", minutes=60, threshold=71, calls=69, stop=True, enabled=True),
        ],
    )
    dom = render(alerts.alerts_view)[1]
    notify_only = content(row_with(dom, "在庫照会"))
    stopping = content(row_with(dom, "配送照会"))
    for text in ("stock", "検証", "15分", "37件", "21件", "通知"):
        assert text in notify_only
    assert "停止" not in notify_only
    for text in ("60分", "71件", "69件", "停止"):
        assert text in stopping


@pytest.mark.parametrize(
    ("action", "stop", "enabled"),
    [
        pytest.param(
            "notify",
            False,
            True,
            id="notify",
            marks=pytest.mark.case_detail("通知のみのルールを保存する"),
        ),
        pytest.param(
            "stop",
            True,
            True,
            id="stop",
            marks=pytest.mark.case_detail("到達後は利用を止めるルールを保存する"),
        ),
        pytest.param(
            "off", False, False, id="off", marks=pytest.mark.case_detail("指定したルールを無効にする")
        ),
    ],
)
def test_save_alert(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, action: str, stop: bool, enabled: bool
) -> None:
    """利用上限を保存すると選択したAPI・環境・プロジェクトの件数、期間と動作を送る。"""
    actions = portal_module("actions.alerts")
    activity = portal_module("apis.activity")
    ui = portal_module("runtime.portal_ui")
    ui.ctx.update(targets=[target()], me=member(admin=True))
    values = {
        "alert-target": "inventory/stock/sandbox",
        "alert-action": action,
        "alert-minutes": "15",
        "alert-threshold": "37",
    }
    monkeypatch.setattr(actions, "value", values.__getitem__)
    submit = AsyncMock(return_value={"id": "rule"})
    monkeypatch.setattr(activity, "save_alert", submit)
    monkeypatch.setattr(actions, "load", AsyncMock())
    asyncio.run(actions.save_alert())
    assert submit.await_args is not None
    body = submit.await_args.args[0]
    assert body == {
        "asset_id": "inventory",
        "project": "stock",
        "environment": "sandbox",
        "minutes": 15,
        "threshold": 37,
        "stop": stop,
        "enabled": enabled,
    }


def test_audit_row_contains_correlation(portal_module: Module) -> None:
    """監査担当は業務操作の対象と判断理由、記録日時、リクエストIDを同じ行で照合できる。"""
    ui = portal_module("runtime.portal_ui")
    audit = portal_module("components.audit")
    ui.ctx.update(
        audit_id="",
        audit_action="",
        audit_offset=0,
        rows=[
            {
                "action": "approve",
                "at": "2026-04-07T03:08:09Z",
                "actor": "owner-22",
                "project": "stock",
                "owner": "supply",
                "asset_id": "inventory",
                "environment": "production",
                "detail": "確認済み",
                "request_id": "trace-441",
                "target_subject": None,
            },
        ],
    )
    dom = render(audit.audit_view)[1]
    row = content(row_with(dom, "trace-441"))
    for text in ("2026-04-07", "承認", "owner-22", "stock", "supply", "inventory", "本番", "確認済み"):
        assert text in row
    assert any("ダウンロード" in content(button) for button in dom.getElementsByTagName("button"))


def test_member_directory_and_invitation(portal_module: Module) -> None:
    """管理者は登録済み利用者の名前・役割を確認し、氏名と表示名を添えて招待できる。"""
    ui = portal_module("runtime.portal_ui")
    view = portal_module("components.members")
    registered = dict(
        person("u-2", "hayashi", "mail@example.test", "林明", "棚卸窓口"),
        role="consumer",
        project="stock",
        deleted=False,
    )
    ui.ctx.update(
        me=member(admin=True), members={"items": [registered], "next": "", "projects": ["stock"]}
    )
    dom = render(view.members_view)[1]
    row = content(row_with(dom, "mail@example.test"))
    for text in ("hayashi", "林明", "棚卸窓口", "利用者"):
        assert text in row
    ids = {el.getAttribute("id") for el in dom.getElementsByTagName("input")}
    assert {"member-email", "member-full-name", "member-display-name"} <= ids


@pytest.mark.parametrize(
    ("admin", "destination", "expected_project", "expected_asset"),
    [
        pytest.param(
            True,
            "stock",
            "stock",
            "",
            id="manager",
            marks=pytest.mark.case_detail("管理者が選択した所属先に件名と本文を配信する"),
        ),
        pytest.param(
            False,
            "inventory/stock/sandbox",
            "stock",
            "inventory",
            id="provider",
            marks=pytest.mark.case_detail("提供者は選んだAPIの申請元に案内を配信する"),
        ),
    ],
)
def test_send_notice_to_selected_audience(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    admin: bool,
    destination: str,
    expected_project: str,
    expected_asset: str,
) -> None:
    """通知送信時に件名・本文と選んだ配信対象をその役割で指定できる形にして送信する。"""
    actions = portal_module("actions.notifications")
    service = portal_module("apis.messages")
    ui = portal_module("runtime.portal_ui")
    ui.ctx.update(me=member(admin=admin, provider=not admin), targets=[target()])
    form = {
        "notify-project": destination,
        "notify-target": destination,
        "notify-title": "点検日",
        "notify-body": "日曜に点検します",
    }
    monkeypatch.setattr(actions, "value", form.__getitem__)
    send = AsyncMock(return_value={"id": "notice-1"})
    monkeypatch.setattr(service, "notice", send)
    monkeypatch.setattr(actions, "load", AsyncMock())
    asyncio.run(actions.send_notice())
    assert send.await_args is not None
    body = send.await_args.args[0]
    assert body["title"] == "点検日" and body["body"] == "日曜に点検します"
    assert body["project"] == expected_project and body.get("asset_id", "") == expected_asset


def test_read_and_change_notice_page(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """未読の通知を既読にすると通知一覧を再取得し、次ページの取得位置を更新できる。"""
    actions = portal_module("actions.notifications")
    service = portal_module("apis.messages")
    page = portal_module("pages.notifications.data")
    ui = portal_module("runtime.portal_ui")
    ui.ctx.update(me=member(), notice_offset=0)
    read = AsyncMock(return_value={})
    get = AsyncMock(return_value={"unread": 0, "items": []})
    monkeypatch.setattr(service, "read", read)
    monkeypatch.setattr(service, "notices", get)
    monkeypatch.setattr(actions, "load", lambda: page.load_notifications("notifications"))
    asyncio.run(actions.read_notice("notice-1"))
    read.assert_awaited_once_with("notice-1")
    asyncio.run(actions.more_notices(20))
    get.assert_awaited_with(20)
    assert ui.ctx["notices"]["unread"] == 0


def test_invite_and_show_members(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """管理者が招待を確定すると、指定した氏名・表示名・役割で登録し名簿を再取得する。"""
    actions = portal_module("actions.members")
    service = portal_module("apis.organization")
    page = portal_module("pages.members.data")
    ui = portal_module("runtime.portal_ui")
    ui.ctx.update(me=member(admin=True), member_cursor="")
    invited = person("u-2", "qa", "u2@example.test", "林明", "品質担当")
    form = {
        "member-email": "u2@example.test",
        "member-full-name": "林明",
        "member-display-name": "品質担当",
        "member-role": "consumer",
        "member-project": "stock",
    }
    monkeypatch.setattr(actions, "value", form.__getitem__)
    invite = AsyncMock(return_value=invited)
    monkeypatch.setattr(service, "add_member", invite)
    get = AsyncMock(
        return_value={
            "items": [dict(invited, role="consumer", project="stock")],
            "next": "",
            "projects": ["stock"],
        }
    )
    monkeypatch.setattr(service, "members", get)
    monkeypatch.setattr(actions, "load", lambda: page.load_members("members"))
    asyncio.run(actions.member_add())
    invite.assert_awaited_once_with(
        {
            "email": "u2@example.test",
            "full_name": "林明",
            "display_name": "品質担当",
            "role": "consumer",
            "project": "stock",
        }
    )
    dom = render(portal_module("components.members").members_view)[1]
    assert "品質担当" in content(row_with(dom, "u2@example.test"))


@pytest.mark.parametrize(
    "confirm",
    [
        pytest.param(
            True,
            id="remove",
            marks=pytest.mark.case_detail("在籍終了を確定すると選択した利用者を削除する"),
        ),
        pytest.param(
            False, id="cancel", marks=pytest.mark.case_detail("削除を取りやめると利用者を残す")
        ),
    ],
)
def test_confirm_member_removal(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, confirm: bool
) -> None:
    """管理者が確認した場合だけ、選択した対象者の在籍終了を反映する。"""
    actions = portal_module("actions.members")
    service = portal_module("apis.organization")
    monkeypatch.setattr(portal_module("js").window, "confirm", lambda _: confirm, raising=False)
    monkeypatch.setattr(actions, "load", AsyncMock())
    delete = AsyncMock(return_value={})
    monkeypatch.setattr(service, "remove_member", delete)
    asyncio.run(actions.member_remove(person("former", "suzuki", "former@example.test")))
    if confirm:
        delete.assert_awaited_once_with("former", "suzuki")
    else:
        delete.assert_not_awaited()


def test_identify_members_without_optional_names(portal_module: Module) -> None:
    """氏名のない利用者もログイン名とメールで識別でき、利用者・提供者の役割を確認できる。"""
    ui = portal_module("runtime.portal_ui")
    view = portal_module("components.members")
    active = dict(
        person("u-active", "suzuki", "new@example.test"), role="consumer", project="stock", deleted=False
    )
    removed = dict(
        person("retired", "yamada", "retired@example.test"),
        role="provider",
        project="stock",
        deleted=True,
    )
    ui.ctx.update(
        me=member(admin=True),
        members={"items": [active, removed], "next": "more", "projects": ["stock"]},
    )
    dom = render(view.members_view)[1]
    first = row_with(dom, "new@example.test")
    removed_row = row_with(dom, "retired@example.test")
    assert any("削除" in content(b) for b in first.getElementsByTagName("button"))
    assert "suzuki" in content(first) and "利用者" in content(first)
    assert "yamada" in content(removed_row) and "提供者" in content(removed_row)


def test_later_notification_page_offers_previous_page(portal_module: Module) -> None:
    """既読通知の後続ページには前の通知に戻る操作と各通知の状態が表示される。"""
    ui = portal_module("runtime.portal_ui")
    notices = portal_module("components.notifications")
    entries = [
        {
            "id": f"n{i}",
            "project": "stock",
            "sender": "運用窓口",
            "at": "2026-04-07T03:08:09Z",
            "title": f"事前案内{i}",
            "body": "点検予定",
            "unread": False,
        }
        for i in range(20)
    ]
    ui.ctx.update(me=member(), notice_offset=20, targets=[], notices={"unread": 0, "items": entries})
    dom = render(notices.notices_view)[1]
    assert "既読" in content(row_with(dom, "事前案内19"))
    assert any("新しい通知" in content(b) for b in dom.getElementsByTagName("button"))


def test_audit_history_paginates_filtered_records(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """業務監査の次ページではリクエストIDと操作の条件を保ち、対象の記録を表示する。"""
    actions = portal_module("actions.audit")
    page = portal_module("pages.operation_history.data")
    api = portal_module("apis.activity")
    views = portal_module("components.audit")
    ui = portal_module("runtime.portal_ui")
    record = {
        "action": "approve",
        "at": "2026-04-07T03:08:09Z",
        "actor": "owner",
        "project": "stock",
        "owner": "supply",
        "asset_id": "inv",
        "environment": "sandbox",
        "detail": "承認済み",
        "request_id": "trace-review",
    }
    ui.ctx.update(
        me=dict(member(), auditor=True), audit_offset=0, audit_id="trace-review", audit_action="approve"
    )
    request = AsyncMock(return_value=[record])
    monkeypatch.setattr(api, "audit", request)
    monkeypatch.setattr(actions, "load", lambda: page.load_audit("operation-history"))
    asyncio.run(actions.audit_page(20))
    assert request.await_args is not None
    params = request.await_args.args[0]
    assert (
        params["request_id"] == "trace-review"
        and params["action"] == "approve"
        and int(params["offset"]) == 20
    )
    dom = render(views.audit_view)[1]
    assert "承認済み" in content(row_with(dom, "trace-review"))
    assert any("新しい記録" in content(b) for b in dom.getElementsByTagName("button"))
