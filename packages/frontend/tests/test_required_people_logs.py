# 個人・監査担当のアクセスログと詳細の照合を、表示要件とログAPIの契約に基づいて検証する。

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_components import render
from test_required_people_support import Module, Record, content, member, row_with


def log_record(*, status: int = 200, error_code: str | None = None) -> Record:
    return {
        "at": "2026-04-07T03:08:09.000Z",
        "started_at": "2026-04-07T03:08:08.875Z",
        "responded_at": "2026-04-07T03:08:09.000Z",
        "request_id": "trace-441",
        "actor": "operator-77",
        "key_id": "key-stock",
        "owner": "supply",
        "project": "finance",
        "asset_id": "inventory",
        "environment": "sandbox",
        "method": "GET",
        "operation": "/items",
        "status": status,
        "duration_ms": 125,
        "error_code": error_code,
    }


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        pytest.param(
            200,
            None,
            id="ok",
            marks=pytest.mark.case_detail("正常な記録に開始・応答時刻とHTTP 200を示す"),
        ),
        pytest.param(
            503,
            "upstream_unavailable",
            id="service",
            marks=pytest.mark.case_detail("接続先が利用できなかった記録にHTTP 503と理由を示す"),
        ),
    ],
)
def test_access_log_detail(portal_module: Module, status: int, reason: str | None) -> None:
    """ログの詳細は共通のリクエストIDと主体・対象、時刻、処理時間、結果を確認できる。"""
    display = portal_module("content.access_log_display")
    fields = display.detail_fields(log_record(status=status, error_code=reason))
    text = " ".join(f"{name} {value}" for name, value in fields)
    for expected in (
        "trace-441",
        "operator-77",
        "key-stock",
        "supply",
        "finance",
        "inventory",
        str(status),
        "03:08:08",
        "03:08:09",
        "125",
    ):
        assert expected in text
    if reason:
        assert reason in text


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        pytest.param(
            "処理時間は？",
            "125",
            id="duration",
            marks=pytest.mark.case_detail("処理時間を聞くと選んだ呼び出しのミリ秒数がわかる"),
        ),
        pytest.param(
            "誰が呼び出しましたか？",
            "operator-77",
            id="actor",
            marks=pytest.mark.case_detail("実行者を聞くと選んだ呼び出しの主体がわかる"),
        ),
    ],
)
def test_question_about_selected_log(portal_module: Module, question: str, expected: str) -> None:
    """詳細画面で選択中の実行について質問すると、その記録に基づく答えを読める。"""
    display = portal_module("content.access_log_display")
    answer = display.answer_log_question(log_record(), question)
    assert expected in answer


@pytest.mark.parametrize(
    ("audit", "unit"),
    [
        pytest.param(
            False,
            "",
            id="personal",
            marks=pytest.mark.case_detail("本人のアクセスログから対象リクエストの詳細へ進める"),
        ),
        pytest.param(
            True,
            "dept",
            id="audit",
            marks=pytest.mark.case_detail("部署リーダーの監査範囲を保って対象リクエストの詳細へ進める"),
        ),
    ],
)
def test_detail_links_preserve_audit_scope(portal_module: Module, audit: bool, unit: str) -> None:
    """一覧から詳細への経路はリクエストIDと個人・監査の範囲を保つ。"""
    logs = portal_module("actions.logs")
    personal = logs.detail_path("trace-441")
    path = logs.detail_path("trace-441", unit, audit=audit)
    assert "trace-441" in path
    if audit:
        assert path != personal
        assert unit in path
    else:
        assert path == personal


def test_access_log_table_initial_disclosure(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """アクセスログ一覧の検索条件は閉じた状態で、結果表には記録と詳細へのリンクを表示する。"""

    ui = portal_module("runtime.portal_ui")
    logs = portal_module("components.logs")
    ui.ctx.update(me=member())
    service = portal_module("apis.activity")
    actions = portal_module("actions.logs")
    org = portal_module("apis.organization")
    monkeypatch.setattr(org, "workspace", AsyncMock(return_value={"units": [], "leads": []}))
    monkeypatch.setattr(service, "dimensions", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "logs", AsyncMock(return_value=[log_record()]))
    asyncio.run(actions.load_logs("access-logs"))
    dom = render(logs.logs_view)[1]
    conditions = next(el for el in dom.getElementsByTagName("details") if "検索条件" in content(el))
    assert not conditions.hasAttribute("open")
    selected = row_with(dom, "trace-441")
    assert "200" in content(selected)
    assert any("trace-441" in a.getAttribute("href") for a in selected.getElementsByTagName("a"))


def test_open_log_detail_and_support(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """詳細で応答と実行者を確認し、選んだリクエストIDを付けて問い合わせを始められる。"""

    ui = portal_module("runtime.portal_ui")
    logs = portal_module("components.logs")
    paths = portal_module("actions.logs")
    js = portal_module("js")
    ui.ctx.update(me=member())
    api = portal_module("apis.activity")
    monkeypatch.setattr(api, "log_detail", AsyncMock(return_value=log_record()))
    path = paths.detail_path("trace-441")
    monkeypatch.setattr(js.window, "location", SimpleNamespace(hash=f"#/{path}"), raising=False)
    asyncio.run(paths.load_detail(path))
    dom = render(logs.detail_view)[1]
    for label in ("trace-441", "operator-77", "200", "125", "問い合わせ"):
        assert label in content(dom)


@pytest.mark.parametrize(
    ("scope", "auditor"),
    [
        pytest.param(
            "personal",
            False,
            id="own",
            marks=pytest.mark.case_detail("本人の一覧を20件で区切り次ページに進める"),
        ),
        pytest.param(
            "audit",
            True,
            id="audit",
            marks=pytest.mark.case_detail("監査範囲を保ったまま20件目から先の記録を取得する"),
        ),
    ],
)
def test_log_pagination_scope(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, scope: str, auditor: bool
) -> None:
    """本人と監査担当のログは20件ずつ表示し、次ページにも同じ閲覧範囲を適用する。"""

    ui = portal_module("runtime.portal_ui")
    api = portal_module("apis.activity")
    org = portal_module("apis.organization")
    actions = portal_module("actions.logs")
    views = portal_module("components.logs")
    ui.ctx.update(me=dict(member(), auditor=auditor), log_offset=0)
    rows = [dict(log_record(), request_id=f"log-{i:02}") for i in range(22)]

    def get_rows(params: Record) -> list[Record]:
        assert params["scope"] == scope
        start = int(params["offset"])
        return rows[start : start + int(params["limit"])]

    monkeypatch.setattr(api, "logs", AsyncMock(side_effect=get_rows))
    monkeypatch.setattr(api, "dimensions", AsyncMock(return_value=[]))
    monkeypatch.setattr(org, "workspace", AsyncMock(return_value={"units": [], "leads": []}))
    page = "audit-logs" if auditor else "access-logs"
    asyncio.run(actions.load_logs(page))
    first = render(views.logs_view, scope)[1]
    first_text = content(first)
    assert "log-00" in first_text and "log-19" in first_text and "log-20" not in first_text
    asyncio.run(actions.log_page(20))
    second = render(views.logs_view, scope)[1]
    assert "log-20" in content(second) and "log-00" not in content(second)


def test_audit_filter_and_download(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """業務監査で指定したリクエストIDと操作を一覧取得とJSON Lines保存の両方に使用する。"""

    actions = portal_module("actions.audit")
    page = portal_module("pages.operation_history.data")
    api = portal_module("apis.activity")
    ui = portal_module("runtime.portal_ui")
    conditions = {"audit-id": "trace-441", "audit-action": "approve"}
    row = dict(log_record(), action="approve", detail="審査済み")
    get = AsyncMock(return_value=[row])
    monkeypatch.setattr(api, "audit", get)
    monkeypatch.setattr(actions, "value", conditions.__getitem__)
    monkeypatch.setattr(actions, "load", lambda: page.load_audit("operation-history"))
    ui.ctx.update(me=dict(member(), auditor=True), audit_offset=20)
    asyncio.run(actions.audit_filter())
    assert get.await_args is not None
    params = get.await_args.args[0]
    assert (
        params["request_id"] == "trace-441"
        and params["action"] == "approve"
        and int(params["offset"]) == 0
    )
    saved: list[tuple[list[str], str]] = []

    class Parts(list[str]):
        """ブラウザーの配列に文字列を追加する。"""

        def push(self, value: str) -> None:
            self.append(value)

    monkeypatch.setattr(
        actions, "save_blob", lambda blob, name: saved.append((blob, name)), raising=False
    )
    js = portal_module("js")
    monkeypatch.setattr(js, "Array", SimpleNamespace(new=Parts), raising=False)
    monkeypatch.setattr(js, "Blob", SimpleNamespace(new=lambda parts, *_: parts), raising=False)
    monkeypatch.setattr(js.window, "Array", js.Array, raising=False)
    monkeypatch.setattr(js.window, "Blob", js.Blob, raising=False)
    asyncio.run(actions.download_audit())
    assert saved and saved[0][1].endswith(".jsonl")
    assert get.await_args.args[0]["request_id"] == "trace-441"
    assert json.loads("".join(saved[0][0]))["request_id"] == "trace-441"


def test_department_audit_detail_scope(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """部署リーダーが監査履歴の行を開くと、部署と監査範囲を付けて照会し、詳細に対象リクエストを表示する。"""
    ui = portal_module("runtime.portal_ui")
    actions = portal_module("actions.logs")
    views = portal_module("components.logs")
    service = portal_module("apis.activity")
    current = dict(member(), leads=["dept-operations"])
    ui.ctx.update(me=current)
    request = AsyncMock(return_value=log_record(status=503, error_code="UPSTREAM_UNAVAILABLE"))
    monkeypatch.setattr(service, "log_detail", request)
    path = actions.detail_path("trace-441", "dept-operations", audit=True)
    monkeypatch.setattr(
        portal_module("js").window, "location", SimpleNamespace(hash="#/" + path), raising=False
    )
    asyncio.run(actions.load_detail(path))
    request.assert_awaited_once_with("trace-441", "dept-operations", "audit")
    dom = render(views.detail_view)[1]
    for label in ("trace-441", "UPSTREAM_UNAVAILABLE", "503", "operator-77"):
        assert label in content(dom)
