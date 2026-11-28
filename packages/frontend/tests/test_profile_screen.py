"""プロフィールの表示権限と、保存時にブラウザーが送信する項目を検証する。"""

import asyncio
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock

import pytest
from test_components import render


def test_profile_reads_only_the_allowed_member(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """利用者には本人の編集欄を表示し、他者のプロフィールの読み込みと編集を制限する。"""
    profile = portal_module("actions.profile")
    member = {"email": "user@example.test", "full_name": "氏名", "display_name": "表示", "revision": 3}
    api = AsyncMock(return_value=member)
    monkeypatch.setattr(profile.organization_api, "profile", api)
    directory = AsyncMock(
        return_value={"units": [], "memberships": [], "my_units": [], "metadata_fields": []}
    )
    monkeypatch.setattr(profile.organization_api, "workspace", directory)
    screen = portal_module("components.profile")
    state: dict[str, Any] = {"me": {"admin": False, "subject": "user"}}
    monkeypatch.setattr(profile, "ctx", state)
    monkeypatch.setattr(screen, "ctx", state)
    page = "member-profile/other"
    monkeypatch.setattr(screen, "route", lambda: page)
    monkeypatch.setattr(profile, "route", lambda: page)
    asyncio.run(profile.load_profile(page))
    api.assert_not_awaited()
    directory.assert_not_awaited()
    dom = render(screen.view)[1]
    assert "権限が必要" in dom.toxml()
    assert not dom.getElementsByTagName("input")

    for page, endpoint, admin in (
        ("profile", "/me/profile", False),
        ("member-profile/other", "/members/other/profile", True),
    ):
        profile.ctx["me"]["admin"] = admin
        asyncio.run(profile.load_profile(page))
        api.assert_awaited_with(endpoint)
        dom = render(screen.view)[1]
        assert [item.getAttribute("value") for item in dom.getElementsByTagName("input")] == [
            "氏名",
            "表示",
        ]
        assert ("ユーザー管理に戻る" in dom.toxml()) == admin


def test_profile_save_preserves_revision_and_clears_blank_names(
    portal_module: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch
) -> None:
    """プロフィール更新で読み込み時の版を送り、空に戻した表示名を解除する。"""
    profile = portal_module("actions.profile")
    api = AsyncMock(return_value={"revision": 5})
    monkeypatch.setattr(profile.organization_api, "update_profile", api)
    monkeypatch.setattr(profile, "ctx", {})
    monkeypatch.setattr(
        profile, "value", {"profile-full-name": "新しい氏名", "profile-display-name": ""}.__getitem__
    )
    asyncio.run(profile.save("/me/profile", 4))
    api.assert_awaited_once_with(
        "/me/profile", {"revision": 4, "full_name": "新しい氏名", "display_name": None}
    )
    assert profile.ctx == {"member_profile": {"revision": 5}, "message": "プロフィールを保存しました"}
