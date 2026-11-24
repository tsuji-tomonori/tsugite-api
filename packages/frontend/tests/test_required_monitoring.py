# 監視画面の期間・検索条件と業務履歴の保存を、画面とAPIの公開契約から検証する。
import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from test_components import render
from test_required_people_support import content, member, unit, workspace


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
def test_apply_monitoring_filters(portal_module, monkeypatch, chart):
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


def test_relative_period_uses_utc(portal_module):
    """開始と終了を直接選ばない場合、選択した時間数を直近のUTC期間に変換する。"""
    activity = portal_module("actions.activity")
    activity.ctx["filters"].update(hours="168", start="", end="")
    params = activity.time_params()
    start = datetime.fromisoformat(params["start"])
    end = datetime.fromisoformat(params["end"])
    assert start.utcoffset() == end.utcoffset() == timedelta(0)
    assert end - start == timedelta(days=7)


def test_metrics_page_loads_organization_filter_and_period(portal_module, monkeypatch):
    """集計画面の読込は組織の選択肢を取得し、期間とプロジェクトを保持してAPIの実績を表示用に渡す。"""
    loader = portal_module("pages.metrics.data")
    reload_options = AsyncMock()
    monkeypatch.setattr(loader, "load_dimensions", reload_options)
    loader.ctx["filters"].update(project="north", unit="accounts", minutes="15")
    expected = {"minutes": 15, "points": [{"at": "2026-02-01T12:00:00Z", "calls": 9}]}
    api = AsyncMock(return_value=expected)
    monkeypatch.setattr(loader.activity_api, "metrics", api)
    asyncio.run(loader.load_metrics("/metrics"))
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
    portal_module, monkeypatch, function, args, endpoint, params
):
    """URLの構成で日本語と予約文字を失わず、業務画面が指定した絞り込みを渡す。"""
    api = portal_module("apis.activity")
    dispatch = AsyncMock()
    for method in ("api", "request_object", "request_rows"):
        monkeypatch.setattr(api.client, method, dispatch)
    asyncio.run(getattr(api, function)(*args))
    address = urlsplit(dispatch.await_args.args[0])
    assert address.path == endpoint
    assert parse_qs(address.query) == {key: [value] for key, value in params.items()}


def test_saved_file_uses_requested_filename_and_releases_url(portal_module, monkeypatch):
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
def test_available_monitoring_dimensions_follow_scope(portal_module, monkeypatch, scope, path):
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
            "提供者",
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
    portal_module, monkeypatch, admin, provider, role, show_inventory
):
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
