from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qsl, urlsplit
from xml.dom.minidom import Document

import pytest
from puepy import Page
from puepy.core import Tag


def render(component, *args):
    class ComponentPage(Page):
        def populate(self):
            component(*args)

    page = ComponentPage()
    with page:
        page.generate_children()
    with patch.object(Tag, "document", Document()):
        return page, page.render()


def elements(dom):
    return {el.getAttribute("id"): el for el in dom.getElementsByTagName("*") if el.hasAttribute("id")}


def test_guide_results_render_matching_cards_only(portal_module):
    """提供者の検索結果で一致したガイドを先頭に表示し、件数を読み上げる。"""
    guide = portal_module("guide_views")
    _, dom = render(guide.index, {"guide_query": "読み取りだけ許可したい", "guide_role": "提供者"})
    by_id = elements(dom)
    cards = by_id["guide-grid"].getElementsByTagName("article")
    visible = [card for card in cards if not card.hasAttribute("hidden")]
    assert visible[0].getAttribute("id") == "guide-card-operations"
    assert by_id["guide-card-member"].hasAttribute("hidden")
    assert by_id["guide-count"].getAttribute("role") == "status"
    assert by_id["guide-count"].firstChild.data == f"{len(visible)}件"
    assert by_id["guide-empty"].hasAttribute("hidden")


def test_guide_reset_restores_role_and_keyboard_focus(portal_module, monkeypatch):
    """ガイドの条件をクリアすると全件に戻り、検索欄にフォーカスする。"""
    guide = portal_module("guide_views")
    ctx = {"guide_query": "unmatchedXYZ", "guide_role": "提供者"}
    page, dom = render(guide.index, ctx)
    assert not elements(dom)["guide-empty"].hasAttribute("hidden")
    assert elements(dom)["guide-count"].firstChild.data == "0件"
    query = SimpleNamespace(value=ctx["guide_query"], focus=Mock())
    role = SimpleNamespace(value=ctx["guide_role"])
    nodes = {f"guide-card-{item.id}": SimpleNamespace(hidden=True) for item in guide.GUIDES}
    nodes.update(
        {
            "guide-query": query,
            "guide-role": role,
            "guide-grid": SimpleNamespace(appendChild=Mock()),
            "guide-count": SimpleNamespace(textContent="0件"),
            "guide-empty": SimpleNamespace(hidden=False),
            "guide-clear": SimpleNamespace(hidden=False),
        }
    )
    monkeypatch.setattr(guide, "document", SimpleNamespace(getElementById=nodes.__getitem__))
    clear = next(tag for tag in page.refs.values() if tag.attrs.get("id") == "guide-clear")
    click = next(listener for _, event, listener in clear._added_event_listeners if event == "click")
    event = Mock()
    click(event)

    event.preventDefault.assert_called_once_with()
    assert ctx == {"guide_query": "", "guide_role": "すべて"}
    assert nodes["guide-count"].textContent == f"{len(guide.GUIDES)}件"
    assert nodes["guide-empty"].hidden and nodes["guide-clear"].hidden
    assert all(not nodes[f"guide-card-{item.id}"].hidden for item in guide.GUIDES)
    query.focus.assert_called_once_with()


def test_guide_article_shows_admin_navigation_only_to_admins(portal_module):
    """ユーザー管理の手順は閲覧でき、管理画面へのボタンは管理者にだけ表示する。"""
    guide = portal_module("guide_views")
    button, navigate = Mock(), Mock()
    pages = {"members": "ユーザー管理"}
    user = {"admin": False, "owners": [], "leads": []}
    _, dom = render(guide.article, "member", user, pages, navigate, button)
    image = dom.getElementsByTagName("img")[0]
    assert image.getAttribute("src") == "/guide-images/member.webp"
    assert image.getAttribute("alt")
    button.assert_not_called()
    render(guide.article, "member", {**user, "admin": True}, pages, navigate, button)
    button.assert_called_once_with("「ユーザー管理」を開く", navigate, "members", primary=True)


def test_operation_parameter_renders_openapi_default(portal_module):
    """OpenAPIの型定義を参照し、クエリ入力欄に既定値の例を表示する。"""
    api = portal_module("api_docs")
    spec = {"components": {"schemas": {"Filters": {"type": "array", "default": ["在庫", "受注"]}}}}
    param = {"in": "query", "name": "filters", "schema": {"$ref": "#/components/schemas/Filters"}}
    _, dom = render(api.input_param, spec, param, "filters")
    assert dom.getElementsByTagName("span")[0].firstChild.data == "filters（query）"
    assert elements(dom)["filters"].getAttribute("placeholder") == '["在庫","受注"]'


def test_operation_location_encodes_path_and_query_values(portal_module):
    """パスの予約文字をエンコードし、配列とオブジェクトを指定形式で送る。"""
    api = portal_module("api_docs")
    params = [
        {"in": "path", "name": "id"},
        {"in": "query", "name": "tag", "schema": {"type": "array"}},
        {
            "in": "query",
            "name": "filter",
            "style": "deepObject",
            "schema": {"type": "object"},
        },
    ]
    location = urlsplit(
        api.build_location({}, "/items/{id}", params, {0: "名/1", 1: '["a","b"]', 2: '{"空":"あり"}'})
    )
    assert location.path == "/items/%E5%90%8D%2F1"
    assert parse_qsl(location.query) == [("tag", "a"), ("tag", "b"), ("filter[空]", "あり")]


def test_operation_location_requires_mandatory_query(portal_module):
    """必須のクエリ入力が空なら、入力項目名を示して送信を止める。"""
    api = portal_module("api_docs")
    with pytest.raises(ValueError, match="limit を入力してください"):
        api.build_location({}, "/items", [{"in": "query", "name": "limit", "required": True}], {})


def test_publication_history_shows_release_changes(portal_module):
    """公開履歴に版番号と変更された操作を表示し、差分がない種類は省く。"""
    history = portal_module("product_views").release_history
    _, dom = render(
        history,
        {
            "releases": [
                {
                    "number": 2,
                    "api_version": "1.1.0",
                    "openapi": "3.1.0",
                    "published_at": "2026-11-22T01:12:00Z",
                    "note": "在庫照会を追加",
                    "added": ["GET /stock"],
                    "changed": ["GET /items"],
                    "removed": [],
                }
            ]
        },
    )
    assert dom.getElementsByTagName("h3")[0].firstChild.data == "第2版 · API 1.1.0 · OpenAPI 3.1.0"
    assert [p.firstChild.data for p in dom.getElementsByTagName("p")] == [
        "在庫照会を追加",
        "追加　GET /stock",
        "変更　GET /items",
    ]


def test_login_form_uses_native_labels_and_keyboard_submit(portal_module):
    """ログインフォームに入力ラベルと自動入力の用途を示し、Enterで送信できる。"""
    view = portal_module("login_views")
    ctx = {"config": {"client_id": "web", "identity_endpoint": "https://identity.example"}}
    _, dom = render(view.portal_form, ctx, Mock(), Mock(), Mock())
    fields = elements(dom)
    assert fields["login-user"].getAttribute("autocomplete") == "username"
    assert fields["login-password"].getAttribute("autocomplete") == "current-password"
    assert fields["login-password"].getAttribute("type") == "password"
    assert (
        dom.getElementsByTagName("form")[0].getElementsByTagName("button")[0].getAttribute("type")
        == "submit"
    )
    assert [
        label.getElementsByTagName("span")[0].firstChild.data
        for label in dom.getElementsByTagName("label")
    ] == [
        "ユーザー名",
        "パスワード",
    ]
