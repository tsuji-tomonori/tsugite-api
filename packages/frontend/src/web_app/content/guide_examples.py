# 操作ガイドの表示例に使うサンプル値を定義する。
from typing import Any

PROJECT: dict[str, Any] = {
    "id": "sample-project",
    "name": "サンプルプロジェクト",
    "kind": "project",
    "stopped": False,
}
PROJECTS = [(PROJECT["id"], PROJECT["name"])]
USER: dict[str, Any] = {
    "subject": "sample-user",
    "username": "サンプル利用者",
    "admin": False,
    "projects": [PROJECT["id"]],
    "personal_project": "sample-personal",
}
ASSET = {
    "id": "sample-stock",
    "name": "在庫照会",
    "published": True,
    "environments": ["sandbox"],
    "offers": {"sandbox": {"route": "provider"}},
    "spec": {
        "openapi": "3.0.3",
        "info": {"title": "在庫照会", "version": "1.0"},
        "paths": {
            "/items": {"get": {"summary": "在庫一覧", "responses": {"200": {"description": "在庫一覧"}}}}
        },
    },
}
DIMENSION = {"asset_id": ASSET["id"], "name": ASSET["name"], "project": PROJECT["id"]}
TARGETS = [("sample-target", "在庫照会 · サンプルプロジェクト · 検証")]
REQUEST = {
    "id": "sample-request",
    "asset_id": ASSET["id"],
    "asset_name": ASSET["name"],
    "project": PROJECT["id"],
    "environment": "sandbox",
    "status": "pending",
    "reason": "棚卸しのため",
    "stage": "provider",
}
KEY = {
    "id": "sample-credential",
    "name": "棚卸し用",
    "kind": "personal",
    "project": PROJECT["id"],
    "creator": USER["subject"],
    "mode": "bearer",
    "revoked": False,
    "api_ids": [],
    "ttl_minutes": 60,
    "refresh_minutes": 45,
}
OPTIONS = {"assets": [], "members": [], "max_minutes": 60, "may_manage": True}
POLICY = {
    "visibility": "restricted",
    "projects": [PROJECT["id"]],
    "departments": [],
    "auto_departments": [],
    "delegates": [],
    "auto_titles": [],
}
OPERATIONS = {
    "me": USER,
    "op_policy": {
        "operations": ["GET /items", "POST /items"],
        "permissions": {USER["subject"]: ["GET /items"]},
        "members": [USER],
    },
    "edit_operations": {"api": ASSET["id"], "subject": USER["subject"]},
}
LIMIT = {
    "me": USER,
    "credential_limit": {
        "owner": USER["subject"],
        "endpoint": "/credential-limits/units/" + PROJECT["id"],
        "data": {"inherited_minutes": 60, "max_minutes": 30},
    },
}
