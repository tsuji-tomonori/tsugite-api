# 商品登録・検索・掲載・申請で利用者が指定した条件がAPIに正しく渡ることを検証する。
import asyncio
import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import pytest

Module = Callable[[str], Any]


class Nodes(list[Any]):
    """ブラウザーのフォーム・ファイル一覧を表す。"""

    @property
    def length(self) -> int:
        """画面上の項目数を返す。"""
        return len(self)

    def item(self, index: int) -> Any:
        """指定した位置の要素を返す。"""
        return self[index]


@pytest.fixture
def inputs(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """商品用フォームの入力と確認ダイアログをブラウザー境界で置き換える。"""
    import js

    data: dict[str, Any] = {}

    def element(key: str) -> SimpleNamespace:
        value = data.get(key, "")
        return SimpleNamespace(value=value, checked=value is True, children=Nodes(), files=Nodes(), querySelectorAll=lambda selector: Nodes())

    monkeypatch.setattr(js, "document", SimpleNamespace(getElementById=element, querySelectorAll=lambda selector: Nodes()))
    monkeypatch.setattr(js.window, "confirm", Mock(return_value=True), raising=False)
    monkeypatch.setattr(js.window, "location", SimpleNamespace(hash="#/catalog"), raising=False)
    return data


def test_search_resets_page_and_submits_filters(portal_module: Module, inputs: dict[str, Any],
                                               monkeypatch: pytest.MonkeyPatch) -> None:
    """検索し直すと先頭ページから選択した環境と入力した語句で問い合わせ、返った商品を表示対象にする。"""
    action = portal_module("actions.catalog")
    client = portal_module("apis.client")
    state = portal_module("runtime.portal_ui").ctx
    inputs.update({"search": "東京の倉庫", "filter-env": "production"})
    state.update(page=3)
    response = {"items": [{"id": "warehouse", "name": "在庫照会"}], "total": 1, "page_size": 12, "page": 1}
    backend = AsyncMock(return_value=response)
    monkeypatch.setattr(client, "request_object", backend)
    monkeypatch.setattr(action, "load", AsyncMock(side_effect=lambda: None))
    asyncio.run(action.search())
    asyncio.run(action.load_catalog("catalog"))
    assert backend.await_args is not None
    parsed = urlsplit(backend.await_args.args[0])
    assert parsed.path == "/catalog-page"
    assert parse_qs(parsed.query) == {"inventory": ["false"], "page": ["1"], "q": ["東京の倉庫"], "environment": ["production"]}
    assert state["rows"] == response["items"]
    assert state["page"] == 1 and state["total"] == 1
    asyncio.run(action.turn_page(2))
    assert state["page"] == 2


@pytest.mark.parametrize("personal", [
    pytest.param(True, id="individual", marks=pytest.mark.case_detail("本人を対象に利用目的と利用規約への同意を送る")),
    pytest.param(False, id="project", marks=pytest.mark.case_detail("プロジェクト全員を対象に環境別の利用条件を送る")),
])
def test_application_submits_terms_and_answers(portal_module: Module, inputs: dict[str, Any],
                                              monkeypatch: pytest.MonkeyPatch, personal: bool) -> None:
    """申請すると、選択した対象・環境・目的に加えて、同意した条件の版と回答を送信する。"""
    action = portal_module("actions.application")
    state = portal_module("runtime.portal_ui").ctx
    state["me"] = {"personal_project": "private-u1"}
    inputs.update({"grant-kind": "personal" if personal else "project", "project": "finance",
                   "environment": "sandbox", "reason": "年度末棚卸", "agree-sandbox": True, "answer-sandbox-0": "Q1"})
    offer = {"terms": "同意が必要", "version": "v7", "fields": [{"label": "会計番号", "required": True}]}
    backend = AsyncMock(return_value={"status": "pending"})
    monkeypatch.setattr(portal_module("apis.client"), "api", backend)
    monkeypatch.setattr(action, "go", AsyncMock())
    asyncio.run(action.apply({"id": "stock", "offers": {"sandbox": offer}}))
    backend.assert_awaited_once_with("/apis/stock/requests", "POST", {
        "project": "finance", "personal": personal, "environment": "sandbox", "reason": "年度末棚卸",
        "answers": {"会計番号": "Q1"}, "terms_accepted": True, "offer_version": "v7"})
    assert "申請" in state["message"]


@pytest.mark.parametrize(("initial", "requested"), [
    pytest.param(False, "true", id="publish", marks=pytest.mark.case_detail("下書きを公開してカタログ掲載を受け付ける")),
    pytest.param(True, "false", id="withdraw", marks=pytest.mark.case_detail("掲載停止は新規受付だけを止める")),
])
def test_publication_updates_listing_acceptance(portal_module: Module, monkeypatch: pytest.MonkeyPatch,
                                             initial: bool, requested: str) -> None:
    """掲載を開始または停止したときは掲載状態だけを更新し、最新の商品画面を読み直す。"""
    action = portal_module("actions.listing_data")
    backend, reload = AsyncMock(), AsyncMock()
    monkeypatch.setattr(portal_module("apis.client"), "api", backend)
    monkeypatch.setattr(action, "load", reload)
    asyncio.run(action.publication({"id": "stock", "published": initial}))
    backend.assert_awaited_once_with(f"/apis/stock/publication?published={requested}", "PUT")
    reload.assert_awaited_once_with()


@pytest.mark.parametrize(("initial", "requested"), [
    pytest.param(False, "true", id="suspend", marks=pytest.mark.case_detail("全環境の呼び出しを一時停止する")),
    pytest.param(True, "false", id="resume", marks=pytest.mark.case_detail("一時停止中の商品の呼び出しを再開する")),
])
def test_suspension_controls_all_environments(portal_module: Module, inputs: dict[str, Any],
                                             monkeypatch: pytest.MonkeyPatch, initial: bool, requested: str) -> None:
    """商品単位で一時停止・再開を確認すると、全環境に適用する指定を送る。"""
    action = portal_module("actions.listing_detail")
    backend = AsyncMock()
    monkeypatch.setattr(portal_module("apis.client"), "api", backend)
    monkeypatch.setattr(action, "load", AsyncMock())
    asyncio.run(action.change_suspension({"id": "stock", "name": "在庫", "suspended": initial}))
    backend.assert_awaited_once_with(f"/apis/stock/suspension?suspended={requested}", "PUT")


def test_delete_listing_sends_seen_revision(portal_module: Module, inputs: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """商品の削除は表示した版を指定し、終了後に提供一覧へ戻る。"""
    action = portal_module("actions.listing_detail")
    backend, go = AsyncMock(), AsyncMock()
    monkeypatch.setattr(portal_module("apis.client"), "api", backend)
    monkeypatch.setattr(action, "go", go)
    asyncio.run(action.delete_listing({"id": "stock", "revision": 17, "name": "倉庫照会"}))
    backend.assert_awaited_once_with("/apis/stock?revision=17", "DELETE")
    go.assert_awaited_once_with("inventory")


def test_review_preserves_reason_and_revision(portal_module: Module, inputs: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """提供者の審査は、対象の申請・環境・プロジェクトに理由と判断時点の版を送る。"""
    action = portal_module("actions.requests")
    key = "stock/finance/production"
    inputs[f"reason-{key}"] = "本番の棚卸に必要"
    backend = AsyncMock()
    monkeypatch.setattr(portal_module("apis.client"), "api", backend)
    monkeypatch.setattr(action, "load", AsyncMock())
    asyncio.run(action.decide({"id": key, "revision": 12}, "approve"))
    backend.assert_awaited_once_with(f"/requests/{key}", "POST",
                                     {"action": "approve", "revision": 12, "reason": "本番の棚卸に必要"})


@pytest.mark.parametrize("publish", [
    pytest.param(False, id="draft", marks=pytest.mark.case_detail("下書きの商品を作成し直ちには公開しない")),
    pytest.param(True, id="published", marks=pytest.mark.case_detail("保存した新規商品の識別子を指定して公開する")),
])
def test_register_with_openapi_and_environment(portal_module: Module, inputs: dict[str, Any],
                                              monkeypatch: pytest.MonkeyPatch, publish: bool) -> None:
    """新規商品を保存すると選択環境の接続先・仕様・利用条件を登録し、指定時にその商品を公開する。"""
    action = portal_module("actions.listing_editor")
    state = portal_module("runtime.portal_ui").ctx
    state.update(detail=None, me={"owners": ["supply"], "targets": {"stock-test": {"environment": "sandbox", "owner": "supply"}}})
    spec = {"openapi": "3.0.3", "info": {"title": "在庫照会", "version": "1.0"}, "paths": {}}
    inputs.update({"api-slug": "stock", "name": "在庫照会", "summary": "在庫の集計", "spec": json.dumps(spec), "base-path": "/v1",
                   "sandbox": "stock-test", "offer-sandbox-instructions": "月末用", "offer-sandbox-terms": "倉庫利用",
                   "offer-sandbox-route": "provider", "release-note": "初回公開"})
    client = portal_module("apis.client")
    create, publication = AsyncMock(return_value={"id": "new-stock", "published": False}), AsyncMock()
    monkeypatch.setattr(client, "request_object", create)
    monkeypatch.setattr(client, "api", publication)
    monkeypatch.setattr(portal_module("actions.listing_data"), "load", AsyncMock())
    monkeypatch.setattr(action, "go", AsyncMock())
    asyncio.run(action.register(publish))
    assert create.await_args is not None
    path, method, body = create.await_args.args
    assert (path, method) == ("/apis", "POST")
    assert body["spec"] == spec and body["targets"] == {"sandbox": "stock-test"}
    assert (body["slug"], body["name"], body["base_path"], body["release_note"]) == ("stock", "在庫照会", "/v1", "初回公開")
    assert body["offers"]["sandbox"]["terms"] == "倉庫利用"
    if publish:
        publication.assert_awaited_once_with("/apis/new-stock/publication?published=true", "PUT")
    else:
        publication.assert_not_awaited()


def test_provider_custom_approval_order_and_questions(portal_module: Module, inputs: dict[str, Any],
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """提供者が設定した承認担当の順序、回答候補、必須か任意かを本番の利用条件として保持する。"""
    import js

    def row(label: str, required: bool, accepted: str) -> Any:
        fields = {".field-name": SimpleNamespace(value=label), ".field-required": SimpleNamespace(checked=required),
                  ".field-values": SimpleNamespace(value=accepted)}
        return SimpleNamespace(querySelector=fields.__getitem__)

    fields = Nodes([row("確認番号", True, "Q1\nQ2"), row("備考", False, "")])
    steps = Nodes([SimpleNamespace(value="department"), SimpleNamespace(value="provider")])
    component = portal_module("components.product_views")
    form = {"offer-production-fields": SimpleNamespace(children=fields),
            "offer-production-steps": SimpleNamespace(querySelectorAll=lambda selector: steps)}
    monkeypatch.setattr(js.document, "getElementById", form.__getitem__)
    inputs.update({"offer-production-instructions": "本番は事前確認", "offer-production-terms": "倉庫内のみ",
                   "offer-production-route": "custom"})
    offer = component.read_offer("production", inputs.__getitem__)
    assert offer == {"instructions": "本番は事前確認", "terms": "倉庫内のみ", "route": "custom",
                     "steps": ["department", "provider"], "fields": [
                         {"label": "確認番号", "required": True, "allowed_values": ["Q1", "Q2"]},
                         {"label": "備考", "required": False, "allowed_values": []}]}


@pytest.mark.parametrize(("answer", "agreed", "reason"), [
    pytest.param("", True, "確認番号", id="answer", marks=pytest.mark.case_detail("必須の申請項目が空なら項目名を示す")),
    pytest.param("Q1", False, "同意", id="terms", marks=pytest.mark.case_detail("規約への同意がなければ同意を求める")),
])
def test_application_requires_answers_and_terms(portal_module: Module, inputs: dict[str, Any],
                                              monkeypatch: pytest.MonkeyPatch, answer: str, agreed: bool, reason: str) -> None:
    """提供者の必須条件が満たされないときは利用申請を送信せず、修正すべき項目を案内する。"""
    action = portal_module("actions.application")
    state = portal_module("runtime.portal_ui").ctx
    state["me"] = {"personal_project": "private-u1"}
    inputs.update({"environment": "sandbox", "project": "finance", "grant-kind": "project", "reason": "棚卸",
                   "agree-sandbox": agreed, "answer-sandbox-0": answer})
    backend = AsyncMock()
    monkeypatch.setattr(portal_module("apis.client"), "api", backend)
    offer = {"terms": "同意が必要", "version": "2", "fields": [{"label": "確認番号", "required": True}]}
    with pytest.raises(portal_module("apis.client").InputError, match=reason):
        asyncio.run(action.apply({"id": "s1", "offers": {"sandbox": offer}}))
    backend.assert_not_awaited()


def test_provider_policy_targets_units_and_titles(portal_module: Module, inputs: dict[str, Any],
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    """限定公開の部署・プロジェクト、委任先と自動承認条件を表示時の版とともに保存する。"""
    import js

    action = portal_module("actions.listing_detail")
    inputs.update({"policy-visibility": "restricted", "policy-titles": "課長"})
    selections = {"projects": ["finance", "warehouse"], "departments": ["dept-a"], "delegates": ["dept-b"],
                  "auto_departments": ["dept-c"]}
    checks = {f'input[name="policy-{field}"]:checked': Nodes(SimpleNamespace(value=v) for v in values)
              for field, values in selections.items()}
    monkeypatch.setattr(js.document, "querySelectorAll", checks.__getitem__)
    backend = AsyncMock()
    monkeypatch.setattr(portal_module("apis.client"), "api", backend)
    monkeypatch.setattr(action, "load", AsyncMock())
    asyncio.run(action.save_policy({"id": "stock", "revision": 14}))
    backend.assert_awaited_once_with("/apis/stock/policy?revision=14", "PUT",
                                     {"visibility": "restricted", "auto_titles": ["課長"], **selections})


def test_manual_browser_send_displays_response(portal_module: Module, inputs: dict[str, Any],
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    """URLを直接指定して送ると、接続先専用のヘッダーと本文が使われ、応答状態と本文を画面で読める。"""
    manual = portal_module("components.manual_request")
    inputs.update({"manual-url": "https://inventory.example/items", "manual-method": "PATCH",
                   "manual-headers": "X-Warehouse: Tokyo", "manual-body": '{"stock":17}'})
    response = SimpleNamespace(status=200, headers={}, string=AsyncMock(return_value="在庫を更新"))
    send = AsyncMock(return_value=response)
    monkeypatch.setattr(manual, "fetch", send)
    button = SimpleNamespace(textContent="送信", disabled=True, removeAttribute=Mock(), setAttribute=Mock(),
                             classList=SimpleNamespace(add=Mock(), remove=Mock()))
    result = SimpleNamespace(textContent="")
    asyncio.run(manual.send(button, result))
    assert send.await_args is not None
    url, = send.await_args.args
    options = send.await_args.kwargs
    assert url == "https://inventory.example/items"
    assert options["headers"] == {"x-warehouse": "Tokyo"} and options["body"] == '{"stock":17}'
    assert options["credentials"] == "omit" and options["method"] == "PATCH"
    assert "200" in result.textContent and "在庫を更新" in result.textContent
    assert not button.disabled


def test_trial_issues_personal_product_key(portal_module: Module, monkeypatch: pytest.MonkeyPatch) -> None:
    """API Docsの初回発行は選択プロジェクトと商品のみに使う短期の個人認証情報を作る。"""
    docs = portal_module("components.api_docs")
    result = {"id": "key-1", "name": "在庫照会用"}
    issue = AsyncMock(return_value=result)
    monkeypatch.setattr(portal_module("apis.client"), "request_object", issue)
    key = asyncio.run(docs.trial_key_issuer({"id": "stock", "name": "在庫照会"})("finance"))
    assert key == result and issue.await_args is not None
    path, method, payload = issue.await_args.args
    assert (path, method) == ("/credentials", "POST")
    assert (payload["project"], payload["kind"], payload["mode"], payload["api_ids"]) == (
        "finance", "personal", "bearer", ["stock"])
    assert "在庫照会" in payload["name"]


@pytest.mark.parametrize("owner", [
    pytest.param(False, id="consumer", marks=pytest.mark.case_detail("利用者は商品仕様、認証情報と利用申請を取得する")),
    pytest.param(True, id="provider", marks=pytest.mark.case_detail("提供者は加えて公開範囲、操作の設定と部署の選択肢を取得する")),
])
def test_listing_loads_appropriate_details(portal_module: Module, monkeypatch: pytest.MonkeyPatch, owner: bool) -> None:
    """商品を開くと商品別の申請と仕様を読み、提供者にはその商品用の管理設定を読み込む。"""
    action = portal_module("actions.listing_data")
    state = portal_module("runtime.portal_ui").ctx
    state.update(me={"owners": ["supply"] if owner else [], "admin": False})
    forms = {"/apis/stock": {"id": "stock", "owner": "supply"}, "/apis/stock/policy": {"visibility": "restricted"},
             "/apis/stock/operation-policy": {"permissions": {}}, "/workspace": {"units": []}}
    collections = {"/keys": [{"id": "k1"}], "/requests?asset_id=stock": [{"id": "r1"}]}
    client = portal_module("apis.client")
    records, rows = AsyncMock(side_effect=forms.__getitem__), AsyncMock(side_effect=collections.__getitem__)
    monkeypatch.setattr(client, "request_object", records)
    monkeypatch.setattr(client, "request_rows", rows)
    asyncio.run(action.load_listing("api/stock"))
    assert state["detail"] == forms["/apis/stock"]
    assert state["rights"] == collections["/requests?asset_id=stock"]
    assert state["keys"] == collections["/keys"]
    queried = {call.args[0] for call in records.await_args_list}
    assert queried == (set(forms) if owner else {"/apis/stock"})
