# 要件「使い方ガイドを検索できる」と利用手順に基づき、検索と閲覧専用の画面例を検証する。
from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from test_components import render

type PortalModule = Callable[[str], Any]


def visible_text(node: Any) -> str:
    if node.nodeType == node.TEXT_NODE:
        return str(node.data)
    return "".join(visible_text(child) for child in node.childNodes)


def profile(*, admin: bool = False, owner: bool = False, auditor: bool = False) -> dict[str, Any]:
    return {
        "subject": "guide-reader",
        "admin": admin,
        "auditor": auditor,
        "projects": ["reader-project"],
        "personal_project": "reader-personal",
        "owners": ["provider-project"] if owner else [],
        "leads": [],
        "departments": [],
        "titles": [],
        "targets": {},
        "known_projects": ["reader-project"],
    }


@pytest.mark.parametrize(
    ("query", "role", "screen"),
    [
        pytest.param(
            "読み取りだけ許可したい",
            "提供者",
            "inventory",
            id="provider-intent",
            marks=pytest.mark.case_detail("読み取り権限についての言い換えから提供APIの手順を探せる。"),
        ),
        pytest.param(
            "短期Bearer",
            "利用者",
            "keys",
            id="consumer-term",
            marks=pytest.mark.case_detail("認証方式を指定すると利用者向けの発行手順を探せる。"),
        ),
        pytest.param(
            "ユーザーを追加",
            "管理者",
            "members",
            id="admin-task",
            marks=pytest.mark.case_detail("ユーザー追加の操作から管理者向けの招待手順を探せる。"),
        ),
    ],
)
def test_search_by_work_and_role(
    portal_module: PortalModule, query: str, role: str, screen: str
) -> None:
    """役割と業務を入力すると目的の画面に進む手順が候補に含まれる。"""
    results = portal_module("content.guide_search").search(query, role)
    assert any(guide.start == screen for guide in results)


def test_guide_search_no_match(portal_module: PortalModule) -> None:
    """該当する手順がないときは件数をゼロと示して再検索を案内する。"""
    query = "zzqxxvv"
    search = portal_module("content.guide_search").search
    assert search(query) == []
    view = portal_module("components.guide_views")
    _, dom = render(view.index, {"guide_query": query, "guide_role": "すべて"})
    assert "0件" in visible_text(dom)
    assert any(
        "見つかりません" in visible_text(p) and not p.hasAttribute("hidden")
        for p in dom.getElementsByTagName("p")
    )


def test_every_guide_has_an_inert_example_and_ordered_steps(portal_module: PortalModule) -> None:
    """ガイド一覧の各手順は操作後の確認方法と入力できない画面例を持ち、対象画面を案内する。"""
    guides = portal_module("content.guide_search").search("")
    registry = portal_module("routing.screen_registry")
    article = portal_module("components.guide_views").article
    titles = {path: screen.title for path, screen in registry.screens().items()}
    examples = registry.guide_examples()
    assert {"利用者", "提供者", "管理者"} <= {guide.role for guide in guides}
    for guide in guides:
        button = Mock()
        go = AsyncMock()
        _, dom = render(
            article,
            guide.id,
            profile(admin=True, owner=True, auditor=True),
            titles,
            go,
            button,
            examples,
        )
        ordered = dom.getElementsByTagName("ol")[0]
        assert [visible_text(item) for item in ordered.getElementsByTagName("li")] == list(
            guide.steps
        ), guide.id
        assert guide.result and guide.result in visible_text(dom), guide.id
        figures = dom.getElementsByTagName("figure")
        assert len(figures) == 1, guide.id
        assert any(
            node.hasAttribute("inert") and node.childNodes
            for node in figures[0].getElementsByTagName("*")
        ), guide.id
        assert any(
            guide.start in call.args and titles[guide.start] in call.args[0]
            for call in button.call_args_list
        ), guide.id
        go.assert_not_awaited()


def test_missing_article_leads_back_to_the_index(portal_module: PortalModule) -> None:
    """存在しない手順のリンクを開くと一覧へ戻る案内が表示される。"""
    view = portal_module("components.guide_views")
    _, dom = render(view.article, "unlisted-guide", profile(), {}, AsyncMock(), Mock(), {})
    assert "見つかりません" in visible_text(dom)
    assert any(link.getAttribute("href") == "#/guide" for link in dom.getElementsByTagName("a"))


@pytest.mark.parametrize(
    ("user", "present", "absent"),
    [
        pytest.param(
            profile(),
            {"catalog", "guide", "mine"},
            {"members", "inventory"},
            id="consumer",
            marks=pytest.mark.case_detail("利用者には検索・申請とガイドの入口を示す。"),
        ),
        pytest.param(
            profile(owner=True),
            {"catalog", "inventory", "inbox"},
            {"members"},
            id="provider",
            marks=pytest.mark.case_detail("提供者には出品と届いた利用申請の入口を示す。"),
        ),
        pytest.param(
            profile(admin=True),
            {"members", "metrics", "departments"},
            set(),
            id="administrator",
            marks=pytest.mark.case_detail("管理者には利用者・組織管理と利用状況の入口を示す。"),
        ),
        pytest.param(
            profile(auditor=True),
            {"audit", "metrics"},
            {"members"},
            id="auditor",
            marks=pytest.mark.case_detail("監査担当には監査履歴と利用状況の入口を示す。"),
        ),
    ],
)
def test_role_navigation(
    portal_module: PortalModule,
    user: dict[str, Any],
    present: set[str],
    absent: set[str],
) -> None:
    """役割に合わせて日常操作と監査・管理の入口を表示する。"""
    groups = portal_module("routing.screen_registry").menu(user)
    paths = {screen.path for screens in groups.values() for screen in screens}
    assert present <= paths
    assert paths.isdisjoint(absent)


@pytest.mark.parametrize(
    ("user", "can_open"),
    [
        pytest.param(
            profile(owner=True),
            True,
            id="provider",
            marks=pytest.mark.case_detail(
                "提供者が出品ガイドを開けば、その場から提供APIの管理画面へ進める。"
            ),
        ),
        pytest.param(
            profile(),
            False,
            id="reader",
            marks=pytest.mark.case_detail(
                "利用者も出品の見本を読めるが、担当外の管理操作には進めない。"
            ),
        ),
    ],
)
def test_provider_guide_keeps_its_sample_separate_from_the_real_management_screen(
    portal_module: PortalModule,
    user: dict[str, Any],
    can_open: bool,
) -> None:
    """提供者のガイドでは誰でも見本を読め、担当者にだけ操作画面への入口を表示する。"""
    import asyncio

    guide = portal_module("components.guide_views")
    registry = portal_module("routing.screen_registry")
    titles = {key: screen.title for key, screen in registry.screens().items()}
    go = AsyncMock()
    button = Mock()
    _, dom = render(guide.article, "publish", user, titles, go, button, registry.guide_examples())
    assert dom.getElementsByTagName("figure")
    go.assert_not_awaited()
    actions = [call.args for call in button.call_args_list if "inventory" in call.args]
    if can_open:
        assert len(actions) == 1
        _, navigate, destination = actions[0]
        asyncio.run(navigate(destination))
        go.assert_awaited_once_with("inventory")
    else:
        assert not actions
