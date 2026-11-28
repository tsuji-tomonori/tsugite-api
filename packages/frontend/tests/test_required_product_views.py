"""商品を探して仕様・利用条件を読み、申請と提供の状態を判断する画面を検証する。"""

import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace as Namespace
from typing import Any
from xml.dom import Node

import pytest
from test_components import render

Module = Callable[[str], Any]


def visible(node: Any) -> str:
    """要素配下に表示されたテキストを読む。"""
    if node.nodeType == Node.TEXT_NODE:
        return str(node.data)
    return " ".join(visible(child) for child in node.childNodes).strip()


def control(doc: Any, tag: str, identifier: str) -> Any:
    """画面上のタグ名と識別子で入力欄を取得する。"""
    return next(e for e in doc.getElementsByTagName(tag) if e.getAttribute("id") == identifier)


def choices(select: Any) -> list[str]:
    """選択肢から送信用の値を順番に取り出す。"""
    return [e.getAttribute("value") for e in select.getElementsByTagName("option")]


@pytest.fixture
def product() -> dict[str, Any]:
    """公開API仕様と二つの公開版を持つ商品を用意する。"""
    example = Path(__file__).resolve().parents[3] / "docs/examples/stock.openapi.json"
    return {
        "id": "s1",
        "slug": "stock-api",
        "name": "在庫照会",
        "owner": "supply",
        "summary": "倉庫ごとの在庫を確認",
        "environments": ["sandbox", "production"],
        "published": True,
        "suspended": False,
        "revision": 3,
        "spec": json.loads(example.read_text()),
        "base_path": "/v1",
        "bindings": {"sandbox": "stock-test", "production": "stock-live"},
        "offers": {
            "sandbox": {
                "instructions": "棚卸の前に確認してください",
                "terms": "倉庫内でのみ利用できます",
                "route": "department_provider",
                "steps": ["department", "provider"],
                "version": "rev-7",
                "fields": [
                    {"label": "会計番号", "required": True, "allowed_values": ["Q1", "Q2"]},
                    {"label": "備考", "required": False},
                ],
            }
        },
        "releases": [
            {
                "number": 2,
                "published_at": "2026-03-03T09:00:00Z",
                "api_version": "2.0",
                "openapi": "3.1.0",
                "added": ["GET /bins"],
                "changed": ["StockItem"],
                "removed": ["DELETE /labels"],
                "note": "棚番を追加",
            },
            {
                "number": 1,
                "published_at": "2026-01-11T08:00:00Z",
                "api_version": "1.0",
                "openapi": "3.0.3",
                "added": ["GET /items"],
                "changed": [],
                "removed": [],
                "note": "初回公開",
            },
        ],
    }


@pytest.fixture
def right() -> dict[str, Any]:
    """検証環境でのプロジェクト利用が承認された申請を用意する。"""
    return {
        "id": "r1",
        "asset_id": "s1",
        "asset_name": "在庫照会",
        "project": "finance",
        "environment": "sandbox",
        "subject": None,
        "applicant": "u1",
        "reason": "年度末の棚卸",
        "decision_reason": "利用目的を確認",
        "status": "approved",
        "revision": 3,
    }


@pytest.fixture
def portal(
    portal_module: Module,
    product: dict[str, Any],
    right: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    """利用者が公開商品を閲覧するときの画面状態を用意する。"""
    import js

    monkeypatch.setattr(
        js.window,
        "location",
        Namespace(hash="#/catalog", origin="https://portal.example"),
        raising=False,
    )
    state: dict[str, Any] = portal_module("runtime.portal_ui").ctx
    user = {
        "subject": "u1",
        "personal_project": "private-u1",
        "projects": ["finance"],
        "owners": [],
        "admin": False,
        "auditor": False,
        "leads": [],
        "departments": [],
        "titles": [],
        "known_projects": ["finance"],
        "targets": {
            "stock-test": {"owner": "supply", "environment": "sandbox"},
            "stock-live": {"owner": "supply", "environment": "production"},
        },
    }
    state.update(
        me=user,
        detail=product,
        rights=[right],
        keys=[],
        rows=[product],
        page=1,
        size=12,
        total=1,
        query="",
        env="",
        config={"demo": False},
        console_asset=product,
        console_keys=[],
        console_operation="",
        console_rights=[right],
        policy=dict(
            visibility="all",
            projects=[],
            departments=[],
            auto_departments=[],
            auto_titles=[],
            delegates=[],
        ),
        policy_directory={"units": []},
        op_policy=dict(operations=[], members=[], permissions={}),
    )
    return state


def test_catalog_displays_matching_product(portal_module: Module, portal: dict[str, Any]) -> None:
    """カタログの商品行に名称・用途・提供元・環境を示し、検索条件を初期状態で閉じる。"""
    doc = render(portal_module("components.catalog").cards)[1]
    row = next(row for row in doc.getElementsByTagName("tr") if "在庫照会" in visible(row))
    assert all(value in visible(row) for value in ("倉庫ごとの在庫を確認", "supply", "検証", "本番"))
    assert row.getElementsByTagName("a")[0].getAttribute("href") == "#/api/s1"
    assert not doc.getElementsByTagName("details")[0].hasAttribute("open")
    assert choices(control(doc, "select", "filter-env")) == ["", "sandbox", "staging", "production"]


def test_catalog_last_page_shows_count(portal_module: Module, portal: dict[str, Any]) -> None:
    """カタログ末尾のページでは総件数と今回の表示範囲を確認できる。"""
    portal.update(page=2, total=13)
    doc = render(portal_module("components.catalog").cards)[1]
    assert "13件" in visible(doc) and "13–13 件を表示" in visible(doc) and "2 / 2 ページ" in visible(doc)
    buttons = [visible(button) for button in doc.getElementsByTagName("button")]
    assert any("前" in label for label in buttons)
    assert any("在庫照会" in visible(link) for link in doc.getElementsByTagName("a"))


def test_release_table_separates_versions(portal_module: Module, product: dict[str, Any]) -> None:
    """公開履歴は各版の公開日・バージョン・仕様差分・提供者の説明を同じ行にまとめる。"""
    doc = render(portal_module("components.product_views").release_history, product)[1]
    rows = [visible(row) for row in doc.getElementsByTagName("tr")]
    second = next(row for row in rows if "第2版" in row)
    first = next(row for row in rows if "第1版" in row)
    assert all(
        part in second
        for part in (
            "2026-03-03",
            "2.0",
            "3.1.0",
            "追加",
            "GET /bins",
            "変更",
            "StockItem",
            "削除",
            "DELETE /labels",
            "棚番を追加",
        )
    )
    assert all(part in first for part in ("2026-01-11", "1.0", "3.0.3", "GET /items", "初回公開"))
    assert "GET /bins" not in first


def test_application_displays_environment_terms(
    portal_module: Module, product: dict[str, Any], portal: dict[str, Any]
) -> None:
    """利用申請にはプロジェクト・対象・環境の選択肢、規約、環境別の必須項目と利用目的を表示する。"""
    doc = render(portal_module("components.application").application_panel, product, portal["me"])[1]
    assert choices(control(doc, "select", "project")) == ["finance", "private-u1"]
    assert choices(control(doc, "select", "grant-kind")) == ["project", "personal"]
    assert choices(control(doc, "select", "environment")) == ["sandbox", "production"]
    assert all(
        v in visible(doc)
        for v in ("棚卸の前に確認してください", "倉庫内でのみ利用できます", "会計番号", "備考")
    )
    for tag, name in [("input", "agree-sandbox"), ("input", "answer-sandbox-0"), ("textarea", "reason")]:
        assert control(doc, tag, name).hasAttribute("required")
    assert not control(doc, "input", "answer-sandbox-1").hasAttribute("required")


def test_listing_form_preserves_provider_settings(
    portal_module: Module, product: dict[str, Any], portal: dict[str, Any]
) -> None:
    """既存商品を開くと識別名を固定し、環境ごとの接続先と承認条件を編集できる。"""
    doc = render(portal_module("components.listing_editor").inventory_form, product)[1]
    assert control(doc, "input", "name").getAttribute("value") == product["name"]
    assert "stock-api" in visible(doc)
    assert not any(e.getAttribute("id") == "api-slug" for e in doc.getElementsByTagName("input"))
    assert choices(control(doc, "select", "sandbox")) == ["", "stock-test"]
    assert choices(control(doc, "select", "production")) == ["", "stock-live"]
    assert visible(control(doc, "textarea", "offer-sandbox-terms")) == "倉庫内でのみ利用できます"
    assert "department_provider" in choices(control(doc, "select", "offer-sandbox-route"))


def test_listing_registration_accepts_slug_and_openapi(
    portal_module: Module, portal: dict[str, Any]
) -> None:
    """商品登録では識別名・環境別接続先と仕様ファイルを入力し、下書きまたは公開を選べる。"""
    doc = render(portal_module("components.listing_editor").inventory_form)[1]
    assert control(doc, "input", "api-slug")
    assert any(e.getAttribute("type") == "file" for e in doc.getElementsByTagName("input"))
    assert all(choices(control(doc, "select", env)) for env in ("sandbox", "staging", "production"))
    assert "下書き" in visible(doc) and "保存して公開" in visible(doc)


def test_product_detail_links_to_application(portal_module: Module, portal: dict[str, Any]) -> None:
    """公開商品には名称、説明、利用申請への入口、API操作と公開履歴を表示する。"""
    doc = render(portal_module("components.listing_detail").detail_page)[1]
    assert all(
        value in visible(doc)
        for value in (
            "在庫照会",
            "倉庫ごとの在庫を確認",
            "利用申請",
            "API操作一覧",
            "公開版の変更履歴",
            "商品コードで在庫を取得",
        )
    )


def test_approved_request_links_to_client(portal_module: Module, right: dict[str, Any]) -> None:
    """承認済みの申請は商品・プロジェクト・理由と実行画面への入口を示す。"""
    doc = render(portal_module("components.requests").rights_page, False, [right])[1]
    assert all(
        term in visible(doc)
        for term in ("在庫照会", "finance", "年度末の棚卸", "利用目的を確認", "利用中")
    )
    assert {"APIを開く", "APIクライアントで開く"} <= {
        visible(b) for b in doc.getElementsByTagName("button")
    }


def test_pending_request_can_be_withdrawn(portal_module: Module, right: dict[str, Any]) -> None:
    """承認待ちの申請では取り下げが可能で、実行画面への入口を表示しない。"""
    doc = render(
        portal_module("components.requests").rights_page, False, [{**right, "status": "pending"}]
    )[1]
    labels = [visible(b) for b in doc.getElementsByTagName("button")]
    assert any("取り下げ" in label for label in labels)
    assert "APIクライアントで開く" not in labels


def test_docs_match_openapi_operations(
    portal_module: Module, product: dict[str, Any], right: dict[str, Any]
) -> None:
    """API Docsは各操作の入力・成功応答・エラーとモデルを仕様どおり表示し、承認先で試行できる。"""

    def view() -> None:
        portal_module("components.api_docs").view(
            product, [right], [], subject="u1", personal_project="private-u1"
        )

    doc = render(view)[1]
    text = visible(doc)
    assert all(
        term in text
        for term in (
            "GET /items",
            "GET /items/{sku}",
            "sku",
            "照会する商品コード",
            "200",
            "404",
            "商品が見つかりません",
            "StockItem",
            "在庫数",
            "finance",
            "個人認証情報",
        )
    )
    assert control(doc, "input", "docs-1-param-0").hasAttribute("required")
    assert "ACCESS_TOKEN" in text


def test_console_shows_approved_operations_and_manual_url(
    portal_module: Module, portal: dict[str, Any]
) -> None:
    """クライアントには承認商品と操作の選択肢があり、手動URL送信用の独立した入力欄もある。"""
    doc = render(portal_module("components.console").console_view)[1]
    assert choices(control(doc, "select", "console-asset")) == ["", "s1"]
    assert choices(control(doc, "select", "console-operation")) == ["GET /items", "GET /items/{sku}"]
    methods = choices(control(doc, "select", "manual-method"))
    assert {"GET", "POST", "PATCH", "DELETE"} <= set(methods)
    for tag, identifier in [
        ("input", "manual-url"),
        ("textarea", "manual-headers"),
        ("textarea", "manual-body"),
    ]:
        assert control(doc, tag, identifier)


def test_docs_offers_only_current_approved_environment(
    portal_module: Module, product: dict[str, Any], right: dict[str, Any]
) -> None:
    """商品・環境・本人に対応する承認だけを抽出し、同じ申請先を重複して表示しない。"""
    docs = portal_module("components.api_docs")
    mine = {**right, "project": "private-u1", "subject": "u1"}
    invalid = [
        {**right, "subject": "colleague"},
        {**right, "status": "pending"},
        {**right, "asset_id": "different"},
        {**right, "environment": "staging"},
    ]
    approved = docs.approved_rights(product, [right, mine, *invalid], "u1")
    assert approved == [right, mine]
    options = docs.trial_bindings([*approved, mine], "private-u1")
    assert [(environment, project) for _, environment, project, _ in options] == [
        ("sandbox", "finance"),
        ("sandbox", "private-u1"),
    ]
    assert "個人" in options[1][3]


def test_docs_credential_choices_respect_grant(portal_module: Module, right: dict[str, Any]) -> None:
    """本人用の承認は同じ商品とプロジェクトで本人に使える個人認証情報だけを選択肢にする。"""
    docs = portal_module("components.api_docs")
    key = {
        "id": "ok",
        "name": "棚卸用",
        "project": "finance",
        "kind": "personal",
        "creator": "u1",
        "mode": "bearer",
        "revoked": False,
        "can_portal_exchange": True,
        "api_ids": ["s1"],
    }
    variants: list[dict[str, Any]] = [
        {"kind": "shared"},
        {"revoked": True},
        {"api_ids": ["other"]},
        {"creator": "u2"},
        {"can_portal_exchange": False},
        {"project": "sales"},
        {"mode": "legacy"},
    ]
    keys = [key] + [{**key, **change, "id": str(index)} for index, change in enumerate(variants)]
    result = docs.available_bindings("s1", [{**right, "subject": "u1"}], keys, "u1")
    assert len(result) == 1
    credential, env, project_id, label = result[0]
    assert (credential, env, project_id) == (key, "sandbox", "finance")
    assert "棚卸用" in label and "個人" in label


def test_suspended_console_omits_execution(portal_module: Module, portal: dict[str, Any]) -> None:
    """一時停止している商品では実行ボタンを表示せず、直接URLを指定する別の操作は利用できる。"""
    portal["console_asset"]["suspended"] = True
    doc = render(portal_module("components.console").console_view)[1]
    labels = {visible(b) for b in doc.getElementsByTagName("button")}
    assert "認証して実行" not in labels
    assert any("指定したURL" in label for label in labels)


def test_incoming_pending_request_shows_review_evidence(
    portal_module: Module, right: dict[str, Any]
) -> None:
    """提供者に届いた承認待ち申請に、申請時の規約、回答、段階ごとの判断と承認・却下を表示する。"""
    application = {
        "terms": "本番の規約",
        "terms_accepted": True,
        "version": "rev-7",
        "answers": {"確認番号": "Q2"},
        "route": "custom",
        "steps": ["department", "provider"],
        "submitted_at": "2026-04-01T00:00:00Z",
        "decisions": [
            {
                "stage": "department",
                "actor": "leader",
                "action": "approve",
                "reason": "部署内で確認",
                "at": "2026-04-03T09:00:00Z",
            }
        ],
    }
    request = {
        **right,
        "status": "pending",
        "stage": "provider",
        "subject": "u1",
        "application": application,
    }
    doc = render(portal_module("components.requests").rights_page, True, [request])[1]
    text = visible(doc)
    assert all(term in text for term in ("finance", "年度末の棚卸", "Q2", "部署内で確認"))
    labels = {visible(b) for b in doc.getElementsByTagName("button")}
    assert "承認" in labels and "却下" in labels


def test_application_page_for_unlisted_product(portal_module: Module, portal: dict[str, Any]) -> None:
    """掲載停止の商品を申請画面で開くと利用申請を送信できない。"""
    portal["detail"]["published"] = False
    doc = render(portal_module("components.application").application_page)[1]
    assert "在庫照会" in visible(doc)
    assert "申請する" not in [visible(b) for b in doc.getElementsByTagName("button")]


def test_application_personal_workspace(portal_module: Module, portal: dict[str, Any]) -> None:
    """プロジェクトに所属していない利用者は、個人ワークスペースで利用申請を始められる。"""
    portal["me"]["projects"] = []
    doc = render(portal_module("components.application").application_page)[1]
    assert choices(control(doc, "select", "project")) == ["private-u1"]
    assert "個人ワークスペース" in visible(doc)
    assert "申請する" in [visible(b) for b in doc.getElementsByTagName("button")]


class FormEvents:
    """PuePyが描いたフォームのクリックと変更をブラウザーの代わりに送る。"""

    def __init__(self) -> None:
        self.click: Any = None
        self.change: Any = None

    def __getattr__(self, tag: str) -> Any:
        from puepy import t

        def draw(*children: Any, **attributes: Any) -> Any:
            if "on_click" in attributes:
                self.click = attributes["on_click"]
            if "on_change" in attributes:
                self.change = attributes["on_change"]
            return getattr(t, tag)(*children, **attributes)

        return draw


@pytest.mark.parametrize(
    ("list_id", "title", "row_class"),
    [
        pytest.param(
            "offer-sandbox-fields",
            "申請項目を追加",
            "application-field",
            id="questions",
            marks=pytest.mark.case_detail("申請項目の追加と削除で回答欄の行数が変化する"),
        ),
        pytest.param(
            "offer-sandbox-steps",
            "承認段階を追加",
            "approval-step",
            id="steps",
            marks=pytest.mark.case_detail("承認段階の追加と削除で担当順の行数が変化する"),
        ),
    ],
)
def test_offer_editor_adds_and_removes_rows(
    portal_module: Module, monkeypatch: pytest.MonkeyPatch, list_id: str, title: str, row_class: str
) -> None:
    """提供者が指定した環境で申請項目と承認段階を追加・削除すると、対応する一覧だけが更新される。"""
    module = portal_module("components.product_views")
    events = FormEvents()
    monkeypatch.setattr(module, "t", events)
    doc = render(
        module.offer_editor, "sandbox", {}, portal_module("components.controls").field, False, []
    )[1]

    def browser_element(key: str) -> Any:
        node = control(doc, "div", key)
        return Namespace(firstElementChild=node.firstChild, appendChild=node.appendChild)

    monkeypatch.setattr(module, "document", Namespace(getElementById=browser_element))
    group = control(doc, "div", list_id)
    original = len(group.childNodes)
    add = next(b for b in doc.getElementsByTagName("button") if visible(b) == title)
    events.click(Namespace(target=add))
    assert len(group.childNodes) == original + 1
    row = group.lastChild
    assert row_class in row.getAttribute("class").split()
    remove = row.getElementsByTagName("button")[0]
    target = Namespace(
        getAttribute=remove.getAttribute,
        closest=lambda selector: Namespace(remove=lambda: group.removeChild(row)),
    )
    events.click(Namespace(target=target))
    assert len(group.childNodes) == original


def test_application_environment_switches_terms(
    portal_module: Module, product: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """環境を切り替えると、その環境の利用条件を表示し、前の環境に固有の条件を隠す。"""
    module = portal_module("components.product_views")
    events = FormEvents()
    monkeypatch.setattr(module, "t", events)
    doc = render(module.application_form, product, portal_module("components.controls").field)[1]
    initial = {
        e.getAttribute("id"): Namespace(hidden=e.hasAttribute("hidden"))
        for e in doc.getElementsByTagName("*")
        if e.getAttribute("id").startswith("requirements-")
    }
    monkeypatch.setattr(module, "document", Namespace(getElementById=initial.__getitem__))
    for env in ("production", "sandbox"):
        events.change(Namespace(target=Namespace(value=env)))
        assert not initial[f"requirements-{env}"].hidden
        assert sum(not section.hidden for section in initial.values()) == 1


def test_openapi_documents_response_media_and_input_examples(portal_module: Module) -> None:
    """操作ごとの仕様は複数の本文形式、応答コード、説明と任意入力の例を表示する。"""
    docs = portal_module("components.api_docs")
    params = [
        {"name": "filters", "in": "query", "schema": {"type": "object", "example": {"倉庫": "北"}}}
    ]
    body = {
        "description": "在庫集計の内容",
        "content": {"application/json": {"schema": {"type": "object"}}, "text/plain": {}},
    }
    operation = {
        "responses": {
            "201": {"description": "在庫登録完了", "content": {"text/plain": {}}},
            "204": {"description": "更新結果に本文なし"},
        }
    }
    doc = render(docs.operation_definition, {}, operation, params, body)[1]
    assert all(
        term in visible(doc)
        for term in (
            "201",
            "204",
            "在庫登録完了",
            "更新結果に本文なし",
            "在庫集計の内容",
            "application/json",
            "text/plain",
            "filters",
            "任意",
        )
    )
    example = render(docs.input_param, {}, params[0], "stock-filter")[1]
    assert json.loads(control(example, "input", "stock-filter").getAttribute("placeholder")) == {
        "倉庫": "北"
    }


def test_openapi_displays_union_array_types(portal_module: Module) -> None:
    """仕様に複数の型を許した場合、配列内の型の選択肢を入力欄の案内で確認できる。"""
    docs = portal_module("components.api_docs")
    param = {
        "in": "query",
        "name": "bins",
        "schema": {"type": "array", "items": {"type": ["integer", "null"]}},
    }
    doc = render(docs.input_param, {}, param, "stock-bins")[1]
    placeholder = control(doc, "input", "stock-bins").getAttribute("placeholder")
    assert all(term in placeholder for term in ("array", "integer", "null"))


def test_console_changes_execution_by_selected_operation(
    portal_module: Module, portal: dict[str, Any]
) -> None:
    """APIクライアントでは、認証情報で許可した操作を選んだときだけ対応する実行欄を表示する。"""
    portal["console_keys"] = [
        {
            "id": "k",
            "mode": "bearer",
            "project": "finance",
            "creator": "u1",
            "kind": "personal",
            "name": "棚卸用認証",
            "can_portal_exchange": True,
            "api_ids": ["s1"],
            "revoked": False,
            "operations": {"s1": ["GET /items/{sku}"]},
        }
    ]
    module = portal_module("components.console")
    portal["console_operation"] = "GET /items/{sku}"
    permitted = render(module.approved_view)[1]
    assert "棚卸用認証" in visible(permitted) and "この操作を実行" in [
        visible(b) for b in permitted.getElementsByTagName("button")
    ]
    portal["console_operation"] = "GET /items"
    unavailable = render(module.approved_view)[1]
    assert "この操作を実行" not in [visible(b) for b in unavailable.getElementsByTagName("button")]
    assert any(a.getAttribute("href") == "#/keys" for a in unavailable.getElementsByTagName("a"))


def test_empty_catalog_offers_new_search(portal_module: Module, portal: dict[str, Any]) -> None:
    """カタログに一致する商品がないときは0件と明示して次の検索を案内する。"""
    portal.update(rows=[], total=0, query="海外倉庫", env="production")
    doc = render(portal_module("components.catalog").cards)[1]
    assert "0件" in visible(doc) and "該当するAPIはありません" in visible(doc)
    assert "キーワード" in visible(doc)
    assert control(doc, "input", "search").getAttribute("value") == "海外倉庫"


def test_provider_inventory_distinguishes_listing_status(
    portal_module: Module, portal: dict[str, Any]
) -> None:
    """提供一覧では公開済み商品と未掲載商品の状態を行ごとに区別できる。"""
    import js

    js.window.location.hash = "#/inventory"
    portal["me"]["owners"] = ["supply"]
    portal.update(
        rows=[
            portal["detail"],
            {**portal["detail"], "id": "new", "name": "棚番取得", "published": False},
            {
                **portal["detail"],
                "id": "pending",
                "name": "在庫更新",
                "published": False,
                "publication_stage": "admin",
                "publication_position": 2,
                "publication_total": 3,
            },
        ],
        total=3,
    )
    doc = render(portal_module("components.catalog").cards)[1]
    rows = [visible(r) for r in doc.getElementsByTagName("tr")]
    assert any("在庫照会" in row and "公開中" in row for row in rows)
    assert any("棚番取得" in row and ("未掲載" in row or "下書き" in row) for row in rows)
    assert any("在庫更新" in row and "公開承認待ち（2/3段階）　管理者" in row for row in rows)


def test_provider_publication_buttons_follow_status(
    portal_module: Module, portal: dict[str, Any]
) -> None:
    """提供者の詳細画面に現在の掲載状態に合った公開操作と、既存の利用権を別々に示す。"""
    portal["me"].update(owners=["supply"], admin=True)
    detail = portal_module("components.listing_detail")
    for published, action in [(False, "公開申請する"), (True, "掲載を取り下げる")]:
        portal["detail"]["published"] = published
        doc = render(detail.detail_page)[1]
        assert action in [visible(b) for b in doc.getElementsByTagName("button")]
        assert "finance" in visible(doc) and "利用中" in visible(doc)
        assert "公開範囲と承認ルール" in visible(doc)


def test_operation_list_honors_user_scope(
    portal_module: Module, product: dict[str, Any], right: dict[str, Any]
) -> None:
    """許可された操作が限定された商品では、対象操作の入力と応答だけを実行できる。"""
    docs = portal_module("components.api_docs")
    product["allowed_operations"] = ["GET /items/{sku}"]

    def view() -> None:
        docs.view(product, [right], [], subject="u1", personal_project="private-u1")

    doc = render(view)[1]
    assert "商品コードで在庫を取得" in visible(doc)
    assert "在庫一覧を取得" not in visible(doc)
    assert "短期認証で呼び出す" in [visible(b) for b in doc.getElementsByTagName("button")]
    product["allowed_operations"] = []
    unavailable = render(view)[1]
    assert "許可されている操作はありません" in visible(unavailable)
    assert not unavailable.getElementsByTagName("button")


def test_docs_show_multi_media_and_approval_requirement(
    portal_module: Module, product: dict[str, Any]
) -> None:
    """未承認でも商品仕様の操作・本文形式・応答を閲覧でき、その操作の実行には承認を求める。"""
    docs = portal_module("components.api_docs")
    operation = {
        "summary": "棚番を登録",
        "requestBody": {
            "content": {"text/plain": {}, "application/json": {"schema": {"type": "object"}}}
        },
        "responses": {"201": {"description": "棚番を作成"}},
    }
    spec = {
        "openapi": "3.1.0",
        "info": {"title": "棚番", "version": "2.0"},
        "paths": {
            "/bins": {
                "summary": "棚管理用",
                "parameters": [{"in": "query", "name": "zone", "schema": {"type": "integer"}}],
                "post": operation,
            }
        },
    }
    product["spec"] = spec

    def view() -> None:
        docs.view(product, [], [], subject="u1", personal_project="private-u1")

    doc = render(view)[1]
    assert all(
        term in visible(doc)
        for term in (
            "POST /bins",
            "zone",
            "棚番を登録",
            "text/plain",
            "application/json",
            "201",
            "棚番を作成",
            "承認が必要",
        )
    )
    assert not doc.getElementsByTagName("button")


@pytest.mark.parametrize(
    "audience",
    [
        pytest.param(
            [],
            id="no-audience",
            marks=pytest.mark.case_detail("限定公開で公開先がない商品には属性値のチェックが付かない"),
        ),
        pytest.param(
            ["employee"],
            id="employees",
            marks=pytest.mark.case_detail(
                "社員に限定した商品では社員だけが登録済みの公開条件として選択される"
            ),
        ),
    ],
)
def test_restricted_visibility_displays_selected_metadata_values(
    portal_module: Module, product: dict[str, Any], portal: dict[str, Any], audience: list[str]
) -> None:
    """提供者の公開条件フォームは公開先なしと任意属性の値による限定公開を区別して表示する。"""
    detail = portal_module("components.listing_detail")
    directory = [
        {"id": "employee", "name": "社員", "kind": "employment-type", "parent": "", "stopped": False},
        {
            "id": "contractor",
            "name": "業務委託",
            "kind": "employment-type",
            "parent": "",
            "stopped": False,
        },
        {"id": "internal-tag", "name": "社内評価", "kind": "rating", "parent": "", "stopped": False},
    ]
    portal["policy_directory"] = {
        "units": directory,
        "metadata_fields": [
            {"key": "employment-type", "label": "雇用区分", "builtin": False, "public_values": True},
            {"key": "rating", "label": "人事評価", "builtin": False, "public_values": False},
        ],
    }
    portal["me"]["owners"] = ["supply"]
    portal["policy"].update(visibility="restricted", metadata_values=audience)
    product["published"] = bool(audience)
    doc = render(detail.detail_page)[1]
    assert ("公開中" if audience else "未掲載") in visible(doc)
    options = control(doc, "select", "policy-visibility").getElementsByTagName("option")
    assert [o.getAttribute("value") for o in options if o.hasAttribute("selected")] == ["restricted"]
    boxes = [
        e
        for e in doc.getElementsByTagName("input")
        if e.getAttribute("name") == "policy-metadata_values"
    ]
    assert {e.getAttribute("value") for e in boxes} == {"employee", "contractor"}
    assert [e.getAttribute("value") for e in boxes if e.hasAttribute("checked")] == audience
    assert "社員" in visible(doc) and "業務委託" in visible(doc)


def test_publication_inbox_shows_assigned_reviews_and_admin_settings(
    portal_module: Module, portal: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """公開審査の担当者には商品への入口を、管理者には承認順の編集欄を表示する。"""
    module = portal_module("components.requests")
    portal.update(rows=[], publication_requests=[])
    ordinary = render(module.inbox)[1]
    assert "判断を待っている公開申請はありません" in visible(ordinary)
    assert "提供ガイドラインと公開承認の設定" not in visible(ordinary)
    portal["me"]["admin"] = True
    portal.update(
        publication_requests=[{"id": "s1", "name": "棚卸API"}],
        publication_policy={"guidelines": "仕様を確認", "steps": ["unit/sales", "person/u1"]},
        policy_directory={
            "units": [
                {"id": "sales", "name": "営業部", "kind": "department"},
                {"id": "title", "name": "役職", "kind": "title"},
            ],
            "users": [{"subject": "u1", "username": "sato", "full_name": "佐藤 明"}],
        },
    )
    events = FormEvents()
    monkeypatch.setattr(module, "t", events)
    doc = render(module.inbox)[1]
    assert doc.getElementsByTagName("a")[0].getAttribute("href") == "#/api/s1"
    steps = control(doc, "div", "publication-steps")
    assert [
        e.getAttribute("value")
        for e in steps.getElementsByTagName("option")
        if e.hasAttribute("selected")
    ] == ["unit/sales", "person/u1"]
    assert "営業部のリーダー" in visible(steps) and "佐藤 明" in visible(steps)
    assert "unit/title" not in choices(steps)

    def element(key: str) -> Any:
        node = control(doc, "div", key)
        return Namespace(firstElementChild=node.firstChild, appendChild=node.appendChild)

    monkeypatch.setattr(module, "document", Namespace(getElementById=element))
    add = next(
        button for button in doc.getElementsByTagName("button") if visible(button) == "承認段階を追加"
    )
    events.click(Namespace(target=add))
    assert len(steps.childNodes) == 3
    last = steps.lastChild
    remove = last.getElementsByTagName("button")[0]
    events.click(
        Namespace(
            target=Namespace(
                getAttribute=remove.getAttribute,
                closest=lambda _: Namespace(remove=lambda: steps.removeChild(last)),
            )
        )
    )
    assert len(steps.childNodes) == 2


def test_publication_detail_shows_responsibility_and_current_reviewer(
    portal_module: Module, portal: dict[str, Any], product: dict[str, Any]
) -> None:
    """下書きの現在の担当者がガイドラインと責任者を確認し、申請に判断を記録できる。"""
    product.update(
        published=False,
        publication_stage="admin",
        can_review_publication=True,
        publication_guidelines="公開前に確認",
        responsible_label="物流 太郎",
    )
    detail = render(portal_module("components.listing_detail").detail_page)[1]
    assert "公開前に確認" in visible(detail) and "物流 太郎" in visible(detail)
    assert {"公開申請を承認", "公開申請を却下"} <= {
        visible(el) for el in detail.getElementsByTagName("button")
    }
    portal["me"]["owners"] = ["supply"]
    portal["publication_policy"] = {"guidelines": "利用規約を掲載", "steps": ["admin"]}
    portal["policy_directory"]["users"] = [
        {"subject": "u1", "username": "logistics", "full_name": "物流 太郎"}
    ]
    product["responsible"] = "u1"
    editor = render(portal_module("components.listing_editor").inventory_form, product)[1]
    assert "利用規約を掲載" in visible(editor)
    assert control(editor, "input", "responsible").getAttribute("value") == "u1"
    assert choices(control(editor, "datalist", "responsible-people")) == ["logistics"]
    owner = render(portal_module("components.listing_detail").publication_actions, product)[1]
    assert "公開申請を取り下げる" in visible(owner)


def test_owner_sees_publication_progress(portal_module: Module, portal: dict[str, Any]) -> None:
    """同じ担当を含む三段階でも承認済み・承認待ち・未到達を申請順に表示する。"""
    portal["me"]["owners"] = ["supply"]
    asset = portal["detail"]
    asset.update(
        published=False,
        publication_stage="admin",
        publication_steps=["admin", "admin", "department"],
        publication_position=2,
        publication_total=3,
    )
    page = portal_module("components.listing_detail").detail_page
    doc = render(page)[1]
    assert "公開承認待ち（2/3段階）　管理者" in visible(doc)
    rows = doc.getElementsByTagName("ol")[0].getElementsByTagName("li")
    assert [visible(row) for row in rows] == [
        "管理者（承認済み）",
        "管理者（承認待ち）",
        "申請者の所属部署の上長（未到達）",
    ]
    assert rows[1].getAttribute("aria-current") == "step"
    asset.update(publication_stage=None, publication_outcome="rejected", publication_reason="仕様を修正")
    text = visible(render(page)[1])
    assert "却下されました。理由：仕様を修正" in text and "次回の公開申請（全3段階）" in text
    asset["publication_outcome"] = "withdrawn"
    assert "公開申請を取り下げました。" in visible(render(page)[1])
