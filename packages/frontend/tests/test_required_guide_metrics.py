"""要件「利用状況を把握するとき、プロジェクト別の実績を確認できる」と画面仕様のUTC集計を検証する。"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from test_components import render
from test_required_guide import PortalModule, profile, visible_text

START = "2026-02-11T23:55:00Z"
END = "2026-02-12T00:10:00Z"
POINT = {"at": START, "calls": 13, "success": 10, "errors": 3, "denied": 1, "avg_ms": 17, "max_ms": 52}


@pytest.mark.parametrize(
    ("measure", "expected", "label"),
    [
        pytest.param(
            "calls",
            "13",
            "呼び出し件数",
            id="calls",
            marks=pytest.mark.case_detail("件数の表と棒に呼び出し総数を示す。"),
        ),
        pytest.param(
            "errors",
            "3",
            "エラー件数",
            id="errors",
            marks=pytest.mark.case_detail("エラーを選ぶと失敗した件数を示す。"),
        ),
        pytest.param(
            "denied",
            "1",
            "拒否件数",
            id="denied",
            marks=pytest.mark.case_detail("拒否を選ぶと拒否された件数を示す。"),
        ),
        pytest.param(
            "avg_ms",
            "17",
            "平均応答時間",
            id="average",
            marks=pytest.mark.case_detail("平均応答時間をミリ秒で示す。"),
        ),
    ],
)
def test_metrics_show_the_selected_measure_for_each_utc_bucket(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
    measure: str,
    expected: str,
    label: str,
) -> None:
    """利用状況の表と棒は、指定した表示指標とUTCの時間帯を示す。"""
    page = portal_module("components.metrics")
    ui = portal_module("runtime.portal_ui")
    monkeypatch.setitem(ui.ctx, "me", profile())
    monkeypatch.setitem(ui.ctx["filters"], "measure", measure)
    monkeypatch.setitem(
        ui.ctx, "metrics", {"start": START, "end": END, "minutes": 15, "points": [POINT]}
    )
    _, dom = render(page.metrics_view)
    table = dom.getElementsByTagName("table")[0]
    assert label in visible_text(table)
    assert expected in [visible_text(cell) for cell in table.getElementsByTagName("td")]
    assert "2026-02-11 23:55" in visible_text(table)
    assert "ログ" in visible_text(table)
    bars = [button.getAttribute("aria-label") for button in dom.getElementsByTagName("button")]
    assert any("23:55 UTC" in text and expected in text for text in bars)


def test_empty_period_identifies_the_absence_of_calls(
    portal_module: PortalModule, monkeypatch: pytest.MonkeyPatch
) -> None:
    """利用実績がない期間はUTCの範囲と空の結果を表示する。"""
    page = portal_module("components.metrics")
    ui = portal_module("runtime.portal_ui")
    monkeypatch.setitem(ui.ctx, "me", profile())
    monkeypatch.setitem(ui.ctx, "metrics", {"start": START, "end": END, "minutes": 15, "points": []})
    _, dom = render(page.metrics_view)
    content = visible_text(dom)
    assert "2026-02-11 23:55" in content and "2026-02-12 00:10" in content and "UTC" in content
    assert "記録はありません" in content


def test_drilldown_carries_only_the_selected_utc_interval(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """日付をまたぐ棒を選ぶと、APIとプロジェクトの条件を保ってその区間のログへ移る。"""
    chart = portal_module("components.activity_filters")
    ui = portal_module("runtime.portal_ui")
    monkeypatch.setitem(ui.ctx, "me", profile())
    filters = dict(ui.ctx["filters"], project="fulfillment", asset="stock", minutes="15")
    monkeypatch.setitem(ui.ctx, "filters", filters)
    navigate = AsyncMock()
    monkeypatch.setattr(chart, "go", navigate)
    asyncio.run(chart.inspect_bucket(START, 15))
    selected = ui.ctx["filters"]
    start = datetime.fromisoformat(selected["start"])
    end = datetime.fromisoformat(selected["end"])
    assert start.replace(tzinfo=None) == datetime(2026, 2, 11, 23, 55)
    assert end - start == timedelta(minutes=15)
    assert selected["project"] == "fulfillment" and selected["asset"] == "stock"
    navigate.assert_awaited_once_with("logs")


@pytest.mark.parametrize(
    "explicit",
    [
        pytest.param(
            True,
            id="absolute",
            marks=pytest.mark.case_detail("開始・終了を指定したらその区間を集計する。"),
        ),
        pytest.param(
            False,
            id="relative",
            marks=pytest.mark.case_detail("相対期間を選んだら指定時間数のUTC区間を集計する。"),
        ),
    ],
)
def test_selected_metric_filters_reach_the_api(
    portal_module: PortalModule,
    monkeypatch: pytest.MonkeyPatch,
    explicit: bool,
) -> None:
    """API・環境・プロジェクトと応答コードを選ぶと、指定の条件・期間・間隔で集計を取得する。"""
    data = portal_module("pages.metrics.data")
    controls = portal_module("components.activity_filters")
    activity = portal_module("apis.activity")
    ui = portal_module("runtime.portal_ui")
    monkeypatch.setitem(ui.ctx, "me", profile())
    fields = {
        "f-asset": "inventory",
        "f-project": "warehouse",
        "f-env": "production",
        "f-status": "503",
        "f-minutes": "15",
        "f-hours": "custom" if explicit else "24",
        "f-unit": "",
        "f-measure": "errors",
        "f-start-date": START[:10],
        "f-start-time": START[11:16],
        "f-end-date": END[:10],
        "f-end-time": END[11:16],
    }
    monkeypatch.setattr(controls, "value", fields.__getitem__)
    monkeypatch.setattr(controls, "load", AsyncMock())
    monkeypatch.setattr(data, "load_dimensions", AsyncMock())
    summary = {"start": START, "end": END, "minutes": 15, "points": [POINT]}
    metrics = AsyncMock(return_value=summary)
    monkeypatch.setattr(activity, "metrics", metrics)
    asyncio.run(controls.apply_filters(True))
    asyncio.run(data.load_metrics("metrics"))
    metrics.assert_awaited_once()
    assert metrics.await_args is not None
    params = metrics.await_args.args[0]
    assert {key: params[key] for key in ("asset_id", "project", "environment", "status", "minutes")} == {
        "asset_id": "inventory",
        "project": "warehouse",
        "environment": "production",
        "status": "503",
        "minutes": "15",
    }
    if explicit:
        assert params["start"] == START and params["end"] == END
    else:
        start, end = (datetime.fromisoformat(params[k]) for k in ("start", "end"))
        assert start.utcoffset() == end.utcoffset() == timedelta(0)
        assert end - start == timedelta(hours=24)
    assert ui.ctx["metrics"] == summary
