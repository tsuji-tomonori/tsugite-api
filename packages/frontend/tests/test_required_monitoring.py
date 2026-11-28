"""監視画面の期間・検索条件と業務履歴の保存を、画面とAPIの公開契約から検証する。"""

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from test_components import render
from test_required_people_support import Module, content, member, unit, workspace


@pytest.mark.parametrize(
    "chart",
    [
        pytest.param(
            True,
            id="metrics",
            marks=pytest.mark.case_detail("メトリクスでは集計条件と表示指標を適用する"),
        ),
        pytest.param(
            False,
            id="access-log",
            marks=pytest.mark.case_detail("アクセスログでは条件とリクエストIDを適用し先頭ページに戻る"),
        ),
    ],
)
def test_apply_monitoring_filters(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, chart: bool
) -> None:
    """指定したUTC期間・API・環境・プロジェクト・応答コードを適用し、該当データを再読込する。"""
    filters = portal_module("components.activity_filters")
    activity = portal_module("actions.activity")
    chosen = {
        "hours": "24",
        "minutes": "15",
        "measure": "errors",
        "unit": "finance",
        "asset": "在庫 API",
        "project": "north",
        "env": "production",
        "status": "503",
        "start": "2026-05-01T22:30:00Z",
        "end": "2026-05-02T01:00:00Z",
    }
    controls = {f"f-{key}": value for key, value in chosen.items()} | {"access-id": "trace-51"}
    controls.update(
        {
            "f-hours": "custom",
            "f-start-date": "2026-05-01",
            "f-start-time": "22:30",
            "f-end-date": "2026-05-02",
            "f-end-time": "01:00",
        }
    )
    monkeypatch.setattr(filters, "value", controls.__getitem__)
    refresh = AsyncMock()
    monkeypatch.setattr(filters, "load", refresh)
    filters.ctx["log_offset"] = 40
    asyncio.run(filters.apply_filters(chart))
    assert filters.ctx["filters"] == chosen
    assert activity.time_params() == {
        "start": chosen["start"],
        "end": chosen["end"],
        "asset_id": "在庫 API",
        "environment": "production",
        "project": "north",
        "status": "503",
        "unit": "finance",
    }
    if not chart:
        assert filters.ctx["access_id"] == "trace-51" and filters.ctx["log_offset"] == 0
    refresh.assert_awaited_once()


def test_relative_period_uses_utc(portal_module: Module) -> None:
    """開始と終了を直接選ばない場合、選択した時間数を直近のUTC期間に変換する。"""
    activity = portal_module("actions.activity")
    activity.ctx["filters"].update(hours="168", start="", end="")
    params = activity.time_params()
    start = datetime.fromisoformat(params["start"])
    end = datetime.fromisoformat(params["end"])
    assert start.utcoffset() == end.utcoffset() == timedelta(0)
    assert end - start == timedelta(days=7)


def test_metrics_page_loads_organization_filter_and_period(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """集計画面の読込は組織の選択肢を取得し、期間とプロジェクトを保持してAPIの実績を表示用に渡す。"""
    loader = portal_module("pages.metrics.data")
    reload_options = AsyncMock()
    monkeypatch.setattr(loader, "load_dimensions", reload_options)
    loader.ctx["filters"].update(project="north", unit="accounts", minutes="15")
    expected = {"minutes": 15, "points": [{"at": "2026-02-01T12:00:00Z", "calls": 9}]}
    api = AsyncMock(return_value=expected)
    monkeypatch.setattr(loader.activity_api, "metrics", api)
    asyncio.run(loader.load_metrics("/metrics"))
    assert api.await_args is not None
    params = api.await_args.args[0]
    assert params["unit"] == "accounts" and params["project"] == "north"
    assert str(params["minutes"]) == "15" and params["start"] and params["end"]
    assert loader.ctx["metrics"] == expected
    reload_options.assert_awaited_once()


@pytest.mark.parametrize(
    ("function", "args", "endpoint", "params"),
    [
        pytest.param(
            "metrics",
            ({"project": "在庫 1", "environment": "production", "minutes": "15"},),
            "/metrics",
            {"project": "在庫 1", "environment": "production", "minutes": "15"},
            id="metrics",
            marks=pytest.mark.case_detail("プロジェクト名と区間をメトリクスAPIに渡す"),
        ),
        pytest.param(
            "logs",
            ({"request_id": "A+B/C", "scope": "audit"},),
            "/access-logs",
            {"request_id": "A+B/C", "scope": "audit"},
            id="access",
            marks=pytest.mark.case_detail("特殊文字を含む識別子を監査範囲のログAPIに渡す"),
        ),
        pytest.param(
            "log_detail",
            ("A B", "north", "audit"),
            "/access-logs/detail",
            {"request_id": "A B", "unit": "north", "scope": "audit"},
            id="detail",
            marks=pytest.mark.case_detail("ログ詳細に対象組織と監査範囲を渡す"),
        ),
        pytest.param(
            "audit",
            ({"action": "approve", "request_id": "記録/1"},),
            "/audit",
            {"action": "approve", "request_id": "記録/1"},
            id="audit",
            marks=pytest.mark.case_detail("監査の操作名とリクエストIDを保持する"),
        ),
    ],
)
def test_monitoring_api_preserves_encoded_filter_values(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    function: str,
    args: tuple[Any, ...],
    endpoint: str,
    params: dict[str, str],
) -> None:
    """URLの構成で日本語と予約文字を失わず、業務画面が指定した絞り込みを渡す。"""
    api = portal_module("apis.activity")
    dispatch = AsyncMock()
    for method in ("api", "request_object", "request_rows"):
        monkeypatch.setattr(api.client, method, dispatch)
    asyncio.run(getattr(api, function)(*args))
    assert dispatch.await_args is not None
    address = urlsplit(dispatch.await_args.args[0])
    assert address.path == endpoint
    assert parse_qs(address.query) == {key: [value] for key, value in params.items()}


def test_saved_file_uses_requested_filename_and_releases_url(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch
) -> None:
    """監査ファイルの保存を開始すると指定名のリンクを開き、一時URLを解放する。"""
    download = portal_module("runtime.portal_download")
    blob = object()
    anchor = Mock()
    document = Mock()
    document.createElement.return_value = anchor
    url = Mock()
    url.createObjectURL.return_value = "blob:fixture-export"
    monkeypatch.setattr(download, "document", document)
    monkeypatch.setattr(download, "window", SimpleNamespace(URL=url))
    download.save_blob(blob, "業務監査.jsonl")
    url.createObjectURL.assert_called_once_with(blob)
    assert anchor.download == "業務監査.jsonl" and anchor.href == "blob:fixture-export"
    anchor.click.assert_called_once()
    url.revokeObjectURL.assert_called_once_with("blob:fixture-export")


@pytest.mark.parametrize(
    ("scope", "path"),
    [
        pytest.param(
            "metrics",
            "/metric-dimensions",
            id="metrics",
            marks=pytest.mark.case_detail("利用実績では集計の選択候補を取得する"),
        ),
        pytest.param(
            "personal",
            "/access-logs/dimensions",
            id="personal",
            marks=pytest.mark.case_detail("本人用のアクセスログ候補を取得する"),
        ),
        pytest.param(
            "audit",
            "/access-logs/dimensions",
            id="audit",
            marks=pytest.mark.case_detail("監査可能なアクセスログの候補を取得する"),
        ),
    ],
)
def test_available_monitoring_dimensions_follow_scope(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, scope: str, path: str
) -> None:
    """選択中の組織と閲覧範囲に合わせたAPIから絞り込み候補を取得する。"""
    mod = portal_module("actions.activity")
    me = member(admin=True)
    mod.ctx["me"] = me
    mod.ctx["filters"]["unit"] = "accounts"
    org = workspace([unit("accounts", "経理部")], admin=True, leads=["accounts"])
    candidates = [{"asset_id": "inventory", "project": "stock", "environment": "production"}]
    monkeypatch.setattr(mod.organization_api, "workspace", AsyncMock(return_value=org))
    dimensions = AsyncMock(return_value=candidates)
    monkeypatch.setattr(mod.activity_api, "dimensions", dimensions)
    asyncio.run(mod.load_dimensions(scope))
    assert dimensions.await_args is not None
    endpoint, args = dimensions.await_args.args
    assert endpoint == path
    assert args["unit"] == ("" if scope == "personal" else "accounts")
    if scope != "metrics":
        assert args["scope"] == scope
    assert mod.ctx["dims"] == candidates


@pytest.mark.parametrize(
    ("admin", "provider", "role", "show_inventory"),
    [
        pytest.param(
            False,
            False,
            "利用者",
            False,
            id="consumer",
            marks=pytest.mark.case_detail("一般利用者に利用履歴と契約数を表示する"),
        ),
        pytest.param(
            False,
            True,
            "利用者",
            True,
            id="provider",
            marks=pytest.mark.case_detail("提供者には管理対象のAPI件数も表示する"),
        ),
        pytest.param(
            True,
            False,
            "管理者",
            True,
            id="admin",
            marks=pytest.mark.case_detail("管理者のダッシュボードに管理対象件数を含める"),
        ),
    ],
)
def test_dashboard_renders_personal_history_and_role_counts(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    admin: bool,
    provider: bool,
    role: str,
    show_inventory: bool,
) -> None:
    """ダッシュボードに役割別の件数、直近の個人履歴、UTC時間帯の実績を表示する。"""
    from test_required_people_logs import log_record

    loader = portal_module("pages.dashboard.data")
    view = portal_module("components.dashboard")
    view.ctx["me"] = member(admin=admin, provider=provider)
    counts = {
        "calls": 35,
        "errors": 36,
        "pending": 33,
        "approved": 34,
        "inventory": 37,
        "published": 31,
        "unread": 32,
    }
    points = {"minutes": 60, "points": [{"at": "2026-02-01T10:00:00Z", "calls": 13}]}
    monkeypatch.setattr(loader.activity_api, "dashboard", AsyncMock(return_value=counts))
    monkeypatch.setattr(loader.activity_api, "hourly_metrics", AsyncMock(return_value=points))
    monkeypatch.setattr(loader.activity_api, "recent_logs", AsyncMock(return_value=[log_record()]))
    asyncio.run(loader.load_dashboard("/dashboard"))
    _, dom = render(view.dashboard_view)
    text = content(dom)
    assert role in text and "UTC" in text and "GET /items" in text
    assert all(str(counts[key]) in text for key in ["calls", "errors", "approved"])
    assert ("管理対象のAPI37" in text) == show_inventory


@pytest.mark.parametrize(
    ("filtered", "count", "offset"),
    [
        pytest.param(
            False,
            0,
            0,
            id="empty",
            marks=pytest.mark.case_detail("未絞り込みで記録がないときは空の結果を説明する"),
        ),
        pytest.param(
            True,
            1,
            0,
            id="last-page",
            marks=pytest.mark.case_detail("絞り込んだ1件を時刻・実行者・リクエストIDで照合できる"),
        ),
        pytest.param(
            True,
            50,
            50,
            id="middle-page",
            marks=pytest.mark.case_detail("記録が続く途中のページには新旧両方向の操作を表示する"),
        ),
    ],
)
def test_audit_result_table_shows_context_and_pagination(
    portal_module: Module, filtered: bool, count: int, offset: int
) -> None:
    """業務監査の一覧に検索条件・照合用の情報と、そのページで利用可能な移動を表示する。"""
    audit = portal_module("components.audit")
    rows = [
        {
            "at": "2026-01-11T11:09:00Z",
            "actor": "auditor",
            "action": "approve",
            "target_subject": "applicant",
            "owner": "finance",
            "project": "sales",
            "asset_id": "inventory",
            "environment": "production",
            "request_id": f"trace-{n}",
            "detail": "承認理由を確認済み",
        }
        for n in range(count)
    ]
    audit.ctx.update(
        audit_id="trace-0" if filtered else "", audit_action="", audit_offset=offset, rows=rows
    )
    _, dom = render(audit.audit_view)
    text = content(dom)
    assert ("絞り込み中" in text) == filtered
    assert ("新しい記録" in text) == bool(offset)
    assert ("以前の記録" in text) == (count == 50)
    if rows:
        assert all(
            value in text
            for value in (
                "UTC",
                "auditor",
                "finance",
                "sales",
                "inventory",
                "trace-0",
                "承認理由を確認済み",
            )
        )
    else:
        assert "一致する記録はありません" in text


def test_dashboard_retry_distinguishes_unavailable_summary_from_empty_personal_logs(
    portal_module: Module,
) -> None:
    """集計が未取得で本人の履歴が空の場合、件数の取得失敗と呼び出しがないことを別々に示す。"""
    view = portal_module("components.dashboard")
    view.ctx.update(me=member(), dashboard=None, home_metrics=None, recent_logs=[])
    _, dom = render(view.dashboard_view)
    text = content(dom)
    assert "件数を取得できません" in text and "メトリクスを取得できません" in text
    assert "直近24時間の呼び出しはありません" in text and "再読み込み" in text


@pytest.mark.parametrize(
    "pages",
    [
        pytest.param(
            1, id="single", marks=pytest.mark.case_detail("次の開始位置がなければ一度の取得で保存する")
        ),
        pytest.param(
            3,
            id="multiple",
            marks=pytest.mark.case_detail("各応答の開始位置で取得を継続し全ページを順番どおり保存する"),
        ),
    ],
)
def test_access_export_uses_cursor_and_preserves_current_filter(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, pages: int
) -> None:
    """アクセスログを表示中の期間・識別子で最後のページまで取得し、一つのJSON Linesに保存する。"""
    import json

    logs = portal_module("actions.logs")
    period = {"start": "2026-06-23T23:00:00Z", "end": "2026-06-24T00:10:00Z", "project": "north"}
    logs.ctx.update(access_id="request-監査", log_period=period)
    records = [{"request_id": "request-監査", "sequence": n} for n in range(pages)]
    cursor = [f"page-{i}" for i in range(1, pages)]
    responses = [
        SimpleNamespace(
            ok=True,
            js_response=SimpleNamespace(
                headers={"x-next-cursor": cursor[n]} if n < len(cursor) else {},
                blob=AsyncMock(return_value=json.dumps(record, ensure_ascii=False) + "\n"),
            ),
        )
        for n, record in enumerate(records)
    ]
    calls: list[dict[str, str]] = []

    async def download(query: dict[str, str]) -> SimpleNamespace:
        calls.append(query.copy())
        return responses[len(calls) - 1]

    monkeypatch.setattr(logs.activity_api, "download_chunk", download)
    parts: list[str] = []
    browser = SimpleNamespace(
        Array=SimpleNamespace(new=lambda: SimpleNamespace(push=parts.append)),
        Blob=SimpleNamespace(new=lambda _: "".join(parts)),
    )
    monkeypatch.setattr(logs, "window", browser)
    save = Mock()
    monkeypatch.setattr(logs, "save_blob", save)
    asyncio.run(logs.download_logs())
    assert [query.get("cursor", "") for query in calls] == ["", *cursor]
    assert all(
        query["request_id"] == "request-監査" and period.items() <= query.items() for query in calls
    )
    payload, filename = save.call_args.args
    assert filename.endswith(".jsonl") and [json.loads(line) for line in payload.splitlines()] == records


@pytest.mark.parametrize(
    ("page", "admin", "expected_scope"),
    [
        pytest.param(
            "logs",
            False,
            "personal",
            id="personal",
            marks=pytest.mark.case_detail("利用者の一覧は本人範囲で取得する"),
        ),
        pytest.param(
            "audit-logs",
            True,
            "audit",
            id="authorized",
            marks=pytest.mark.case_detail("管理者の監査一覧は監査範囲で取得する"),
        ),
        pytest.param(
            "audit-logs",
            False,
            None,
            id="outside-role",
            marks=pytest.mark.case_detail("監査権限のない利用者には監査一覧の照会を発行しない"),
        ),
    ],
)
def test_log_navigation_requests_only_current_scope(
    portal_module: Module,
    monkeypatch: pytest.MonkeyPatch,
    page: str,
    admin: bool,
    expected_scope: str | None,
) -> None:
    """個人・監査の一覧を切り替えたら以前の検索条件を解除し、閲覧可能な範囲だけを読み直す。"""
    logs = portal_module("actions.logs")
    logs.ctx.update(me=member(admin=admin), access_id="old-id", log_offset=60)
    monkeypatch.setattr(logs, "route", lambda: page)
    dimensions = AsyncMock()
    records = AsyncMock(return_value=[])
    monkeypatch.setattr(logs, "load_dimensions", dimensions)
    monkeypatch.setattr(logs.activity_api, "logs", records)
    asyncio.run(logs.load_logs(page))
    if expected_scope is None:
        records.assert_not_awaited()
        dimensions.assert_not_awaited()
    else:
        dimensions.assert_awaited_once_with(expected_scope)
        assert records.await_args is not None
        params = records.await_args.args[0]
        assert params["scope"] == expected_scope and params["offset"] == 0 and params["request_id"] == ""
        assert logs.ctx["log_rows"] == []


@pytest.mark.parametrize(
    ("end", "valid"),
    [
        pytest.param(
            "2026-01-01T00:00:00Z",
            False,
            id="empty",
            marks=pytest.mark.case_detail("開始と終了が同じ場合は適用しない"),
        ),
        pytest.param(
            "2026-02-01T00:00:00Z",
            True,
            id="max",
            marks=pytest.mark.case_detail("ちょうど31日の期間を適用する"),
        ),
        pytest.param(
            "2026-02-01T00:00:01Z",
            False,
            id="over",
            marks=pytest.mark.case_detail("31日を超えた場合はフォームに戻す"),
        ),
    ],
)
def test_validate_absolute_period_before_search(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, end: str, valid: bool
) -> None:
    """サーバーが受け付ける期間だけを送信し、範囲外は終了時刻の欄で説明する。"""
    filters = portal_module("components.activity_filters")
    monkeypatch.setattr(filters, "value", lambda _: "custom")
    monkeypatch.setattr(filters, "selected_interval", lambda: ("2026-01-01T00:00:00Z", end))
    dispatch, event, document = Mock(), Mock(), Mock()
    monkeypatch.setattr(filters, "action", dispatch)
    monkeypatch.setattr(filters, "document", document)
    filters.submit_filters(False, event)
    if valid:
        dispatch.return_value.assert_called_once_with(event)
    else:
        dispatch.assert_not_called()
        event.preventDefault.assert_called_once()
        document.getElementById.assert_called_once_with("f-end-time")
        document.getElementById.return_value.reportValidity.assert_called_once()


def test_calendar_preserves_utc_selection_and_leap_day(portal_module: Module) -> None:
    """時差を含む既存期間もUTCの日付と時刻で復元し、うるう日を選択済みとして表示する。"""
    from test_components import elements

    picker = portal_module("components.period_picker")
    filters = {"start": "2024-03-01T06:30:00+09:00", "end": "2024-03-01T22:00:00Z", "hours": "24"}
    _, dom = render(picker.absolute_period, filters)
    fields = elements(dom)
    assert fields["f-start-date"].getAttribute("value") == "2024-02-29"
    assert fields["f-start-time"].getAttribute("value") == "21:30:00"
    assert fields["f-end-date"].getAttribute("value") == "2024-03-01"
    buttons = dom.getElementsByTagName("button")
    selected = [
        b.getAttribute("aria-label") for b in buttons if b.getAttribute("aria-pressed") == "true"
    ]
    assert selected == ["開始 2024-02-29", "終了 2024-03-01"]
