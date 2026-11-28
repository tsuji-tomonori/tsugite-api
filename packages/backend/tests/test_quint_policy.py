"""Quintの判定結果と業務関数を照合し、外部サービスなしで境界条件を検証する。"""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.apis import gateway
from app.core import credential_policy, workspace
from app.core.auth import Actor
from app.core.catalog import right_id
from fastapi import HTTPException
from tsugite_db.models import Access, PortalKey

from tests.support.quint import histories


@pytest.mark.parametrize("states", histories("audience"))
def test_audience_policy(states):
    """限定公開における提供元・所属・直接属性の各条件を照合する。"""
    org = {"desk": {"parent": "east"}, "east": {"parent": ""}}
    for step in states:
        source = step["source"]
        actor = Actor(
            "member",
            frozenset({"field"}),
            frozenset({"owner"}) if source == "owner" else frozenset(),
            False,
            False,
            departments=frozenset(workspace.ancestry(org, {"desk"})),
            metadata={"contract": frozenset({"full-time"})},
        )
        policy = {
            "visibility": "all" if source == "public" else "restricted",
            "projects": ["field" if source == "project" else "another"],
            "departments": ["east" if source == "ancestor" else "west"],
            "metadata_values": ["full-time" if source == "directAttribute" else "all-contracts"],
        }
        asset = SimpleNamespace(owner="owner", policy=json.dumps(policy))
        assert workspace.allowed_audience(asset, actor) == step["visible"], source


@pytest.mark.parametrize("states", histories("credentials"))
def test_operation_policy(states, monkeypatch):
    """認証情報と利用者の操作制限、世代、発行後の秒境界を照合する。"""
    db = Mock()
    for step in states:
        actor = SimpleNamespace(
            issued=100, departments=(), key_id="key", generation=1, machine=False, subject="member"
        )
        key = SimpleNamespace(
            mode="app",
            revision=1 if step["currentGeneration"] else 2,
            config=json.dumps({"operations": {"product": ["GET /"] if step["keyAllows"] else []}}),
        )
        db.get.return_value = key
        monkeypatch.setattr(credential_policy, "clock", lambda: 100 + step["age"])
        monkeypatch.setattr(
            credential_policy, "unit_bounds", lambda *_: [{"minutes": step["projectMinutes"]}]
        )
        monkeypatch.setattr(credential_policy, "minutes", lambda *_: step["apiMinutes"])
        monkeypatch.setattr(
            credential_policy, "individual", lambda *_: ["GET /"] if step["userAllows"] else []
        )
        try:
            credential_policy.check_operation(db, SimpleNamespace(id="product"), actor, "GET /", "field")
            code = 200
        except HTTPException as error:
            code = error.status_code
        assert code == step["response"], step


@pytest.mark.parametrize("states", histories("entitlement"))
def test_entitlement_policy(states, monkeypatch):
    """本人、別人、共有キーとマシンの権利を区別し、停止・失効を即時反映する。"""
    monkeypatch.setattr(gateway, "check_member", lambda *_: None)
    for step in states:
        right, who, gate = step["scope"], step["caller"], step["gate"]
        actor = Actor(
            "peer" if who == "colleague" else "person",
            frozenset({"field"}),
            frozenset(),
            False,
            who == "machine",
            key_id="key",
            key_shared=who == "shared",
        )
        asset = SimpleNamespace(id="product", suspended=gate == "suspended")
        key = SimpleNamespace(revoked=gate == "revokedKey", project="field", scopes="[]")
        rows = {(PortalKey, "key"): key}
        if right != "absent":
            principal = "person" if right == "personal" else ""
            rows[Access, right_id("product", "field", "production", principal)] = SimpleNamespace(
                status="approved"
            )
        db = Mock()
        db.get.side_effect = lambda model, pk: rows.get((model, pk))
        monkeypatch.setattr(gateway, "allowed_audience", lambda *_: gate != "outside")
        monkeypatch.setattr(gateway, "stopped", lambda *_: gate == "stopped")
        try:
            gateway.authorize(db, asset, "field", "production", actor)
            allowed = True
        except HTTPException as error:
            assert error.status_code == 403
            allowed = False
        assert allowed == step["permitted"], step
