import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from app.core.auth import DEMO_GROUPS

from tests.support.catalog import FORM, approved, headers


def test_member_lifecycle(portal):
    """管理者が追加・削除し、同一メールで再登録しても旧利用権を復活させない"""
    admin, other = (headers(portal, r) for r in ("admin", "auditor"))
    data = {"email": "account@example.org", "role": "consumer", "project": "finance"}
    assert portal.post("/api/members", headers=other, json=data).status_code == 403
    member = portal.post("/api/members", headers=admin, json=data).raise_for_status().json()
    assert portal.post("/api/members", headers=admin, json=data).status_code == 409
    assert any(
        m["subject"] == member["subject"]
        for m in portal.get("/api/members", headers=admin).json()["items"]
    )
    user = headers(portal, data["email"])
    assert portal.get("/api/me", headers=user).json()["projects"] == ["finance"]
    assert portal.delete("/api/members/admin?username=admin", headers=admin).status_code == 409
    portal.delete(
        "/api/members/" + member["subject"], params={"username": data["email"]}, headers=admin
    ).raise_for_status()
    assert portal.get("/api/dashboard", headers=user).status_code == 403
    assert portal.post("/api/demo/" + data["email"]).status_code == 404
    second = portal.post("/api/members", headers=admin, json=data).json()
    assert second["subject"] != member["subject"]
    assert portal.get("/api/me", headers=user).status_code == 403


def test_listing_revisions(portal):
    """掲載内容の修正と仕様の変更を区別し、競合を検知し、削除後も監査を保持する"""
    owner, user = (headers(portal, r) for r in ("provider", "consumer"))
    key, url, path = approved(portal, owner, user)
    revision = portal.get(url, headers=owner).json()["revision"]
    change = {**FORM, "name": "在庫照会v2"}
    assert portal.put(url, params={"revision": revision}, headers=user, json=change).status_code == 403
    updated = (
        portal.put(url, params={"revision": revision}, headers=owner, json=change)
        .raise_for_status()
        .json()
    )
    assert updated["published"] and portal.get(path, headers=user).is_success
    assert portal.put(url, params={"revision": revision}, headers=owner, json=FORM).status_code == 409
    change = deepcopy(change)
    change["spec"]["info"]["version"] = "2.0"
    updated = (
        portal.put(url, params={"revision": updated["revision"]}, headers=owner, json=change)
        .raise_for_status()
        .json()
    )
    assert not updated["published"] and portal.get(path, headers=user).status_code == 403
    portal.put(url + "/publication?published=true", headers=owner).raise_for_status()
    right = portal.post(
        url + "/requests",
        headers=user,
        json={"project": "finance", "environment": "sandbox", "reason": "新版の利用"},
    ).json()
    assert right["status"] == "pending"
    revision = portal.get(url, headers=owner).json()["revision"]
    portal.delete(url, params={"revision": revision}, headers=owner).raise_for_status()
    assert (
        portal.get(url, headers=owner).status_code == 404
        and portal.get(path, headers=user).status_code == 404
    )
    assert {"edit", "delete", "reject", "revoke"} <= {
        r["action"] for r in portal.get("/api/audit", headers=owner, params={"asset_id": key}).json()
    }
    assert len(portal.get("/api/access-logs?status=200", headers=user).json()) == 1


def test_notification_scope(portal, monkeypatch):
    """管理者・提供者の通知先を制御し、同じプロジェクトでも既読状態を利用者ごとに保持する"""
    monkeypatch.setitem(DEMO_GROUPS, "second", ["use-finance"])
    monkeypatch.setitem(DEMO_GROUPS, "other", ["use-another"])
    owner, user, second, other, admin = (
        headers(portal, r) for r in ("provider", "consumer", "second", "other", "admin")
    )
    key, _, _ = approved(portal, owner, user)
    msg = {
        "project": "finance",
        "asset_id": key,
        "title": "メンテナンス",
        "body": "翌日10時に更新します",
    }
    assert portal.post("/api/notifications", headers=user, json=msg).status_code == 403
    assert (
        portal.post("/api/notifications", headers=owner, json={**msg, "project": "*"}).status_code == 403
    )
    notice = portal.post("/api/notifications", headers=owner, json=msg).raise_for_status().json()["id"]
    assert portal.put("/api/notifications/" + notice + "/read", headers=other).status_code == 404
    portal.put("/api/notifications/" + notice + "/read", headers=user).raise_for_status()
    portal.post(
        "/api/notifications", headers=admin, json={**msg, "project": "*", "asset_id": ""}
    ).raise_for_status()
    for actor, count in ((user, 1), (second, 2), (other, 1)):
        assert portal.get("/api/notifications/count", headers=actor).json()["unread"] == count


def test_alert_window_and_access_logs(portal, monkeypatch, request):
    """同時実行の上限、通知のみ・停止・解除、次期間の回復、メトリクス集計とログの閲覧範囲を確認する"""
    from app.apis.governance import alerts

    monkeypatch.setattr(alerts, "time", lambda: 600.0)
    monkeypatch.setitem(DEMO_GROUPS, "other", ["use-another"])
    owner, user, other, admin = (headers(portal, r) for r in ("provider", "consumer", "other", "admin"))
    key, _, path = approved(portal, owner, user)
    rule = {
        "asset_id": key,
        "project": "finance",
        "environment": "sandbox",
        "threshold": 2,
        "minutes": 1,
        "stop": True,
    }
    assert portal.put("/api/alerts", headers=user, json=rule).status_code == 403
    portal.put("/api/alerts", headers=owner, json=rule).raise_for_status()
    with ThreadPoolExecutor(max_workers=4) as pool:
        codes = list(pool.map(lambda _: portal.get(path, headers=user).status_code, range(4)))
    assert sorted(codes) == [200, 200, 429, 429]
    assert len(portal.get("/api/audit?action=invoke.start", headers=owner).json()) == 2
    assert portal.get("/api/notifications/count", headers=user).json()["unread"] == 1
    rows = [
        json.loads(line)
        for line in portal.get("/api/access-logs/download", headers=user).text.splitlines()
    ]
    for actor in (admin, user, owner):
        assert portal.get("/api/dashboard", headers=actor).json()["calls"] == 4
        pts = portal.get("/api/metrics?minutes=5&project=finance", headers=actor).json()["points"]
        assert sum(p["success"] for p in pts) == 2 and sum(p["denied"] for p in pts) == 2
    assert portal.get("/api/access-logs/download", headers=other).text == ""
    assert sum(p["calls"] for p in portal.get("/api/metrics", headers=other).json()["points"]) == 0
    denied = next(r for r in rows if r["status"] == 429)
    detail_path = "/api/access-logs/detail"
    params = {"request_id": denied["request_id"]}
    detail = portal.get(detail_path, params=params, headers=user).raise_for_status().json()
    assert detail["started_at"] <= detail["responded_at"]
    assert detail["error_code"] == "http_429" and detail["request_id"] == denied["request_id"]
    assert "operator_action" not in detail
    assert portal.get(detail_path, params=params, headers=other).status_code == 404
    assert portal.get(detail_path, params={"request_id": "missing"}, headers=user).status_code == 404
    assert len(portal.get("/api/access-logs?limit=2", headers=user).json()) == 2
    events = portal.get("/api/audit", params={"request_id": denied["request_id"]}, headers=admin).json()
    assert [r["action"] for r in events] == ["invoke.denied"]
    request.node.user_properties.extend(
        [
            (
                "trace_sample",
                json.dumps(
                    {"業務監査": events, "HTTPアクセスログ": denied}, ensure_ascii=False, indent=2
                ),
            ),
            ("access_sample", json.dumps(rows, ensure_ascii=False)),
            (
                "finding",
                "同時呼び出し4件のうち2件を転送し、2件は429で停止。リクエストIDで業務監査と照合し、別プロジェクトのダウンロードが0件であることを確認。",
            ),
        ]
    )
    monkeypatch.setattr(alerts, "time", lambda: 660.0)
    assert portal.get(path, headers=user).status_code == 200
    portal.put(
        "/api/alerts", headers=admin, json={**rule, "stop": False, "threshold": 1}
    ).raise_for_status()
    assert [portal.get(path, headers=user).status_code for _ in range(2)] == [200, 200]
    assert portal.get("/api/notifications/count", headers=user).json()["unread"] == 2
    portal.put("/api/alerts", headers=admin, json={**rule, "enabled": False}).raise_for_status()
    assert portal.get(path, headers=user).status_code == 200


def test_log_download_pages(portal):
    """同じ時刻の251件を複数ページに分けて全件取得し、重複・欠落と時差を確認する"""
    from datetime import UTC, datetime, timedelta, timezone

    from sqlalchemy.orm import Session
    from tsugite_db.models import AccessLog
    from tsugite_db.session import engine

    user = headers(portal, "consumer")
    stamp = datetime.now(UTC)
    with Session(engine()) as db:
        for n in range(251):
            db.add(
                AccessLog(
                    request_id=f"req{n:03}",
                    at=stamp,
                    actor="consumer",
                    owner="supply",
                    project="finance",
                    asset_id="example",
                    environment="sandbox",
                    method="GET",
                    operation="/stock",
                    status=200,
                    duration_ms=n,
                )
            )
        db.commit()
    legacy = (
        portal.get("/api/access-logs/detail?request_id=req000", headers=user).raise_for_status().json()
    )
    assert legacy["started_at"] is legacy["responded_at"] is legacy["error_code"] is None
    jst = timezone(timedelta(hours=9))
    params = {
        "start": (stamp - timedelta(seconds=1)).astimezone(jst).isoformat(),
        "end": (stamp + timedelta(seconds=1)).astimezone(jst).isoformat(),
    }
    path = "/api/access-logs/download"
    first = portal.get(path, headers=user, params=params).raise_for_status()
    second = portal.get(
        path, headers=user, params={**params, "cursor": first.headers["x-next-cursor"]}
    ).raise_for_status()
    assert len(first.text.splitlines()) == 250 and len(second.text.splitlines()) == 1
    assert [json.loads(row)["request_id"] for row in (first.text + second.text).splitlines()] == [
        f"req{n:03}" for n in range(251)
    ]
    assert "x-next-cursor" not in second.headers


def test_admin_metrics_across_pages(portal):
    """管理者が同時刻の501件をカーソル非対応のDBで集計しても、失敗や二重計上が起きない。"""
    from datetime import UTC, datetime

    from sqlalchemy import event
    from sqlalchemy.orm import Session
    from tsugite_db.models import AccessLog
    from tsugite_db.session import engine

    admin = headers(portal, "admin")
    stamp = datetime.now(UTC)
    database = engine()
    with Session(database) as db:
        db.add_all(
            AccessLog(
                request_id=f"req{n:03}",
                at=stamp,
                actor="consumer",
                owner="supply",
                project="finance",
                asset_id="example",
                environment="sandbox",
                method="GET",
                operation="/stock",
                status=403 if n == 500 else 200,
                duration_ms=n,
            )
            for n in range(501)
        )
        db.commit()

    def reject_server_cursor(conn, cursor, statement, parameters, context, executemany):
        assert not context.execution_options.get("stream_results")
        assert not context.execution_options.get("yield_per")

    event.listen(database, "before_cursor_execute", reject_server_cursor)
    try:
        data = portal.get("/api/metrics?minutes=60", headers=admin).raise_for_status().json()
    finally:
        event.remove(database, "before_cursor_execute", reject_server_cursor)
    active = [point for point in data["points"] if point["calls"]]
    assert len(active) == 1
    assert active[0] == {
        "at": stamp.replace(minute=0, second=0, microsecond=0).isoformat(),
        "calls": 501,
        "success": 500,
        "errors": 1,
        "denied": 1,
        "avg_ms": 250.0,
        "max_ms": 500,
    }
