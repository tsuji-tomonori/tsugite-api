import json

import client
import product_views
from js import document
from listing_data import load_listing, publication
from portal_labels import LABEL
from portal_navigation import go
from portal_ui import btn, ctx, field, route, value
from puepy import t
from screen_registry import Screen

SAMPLE = {
    "openapi": "3.0.3",
    "info": {"title": "在庫照会", "version": "1.0.0"},
    "paths": {
        "/items": {
            "get": {"summary": "在庫一覧を取得", "responses": {"200": {"description": "在庫一覧"}}}
        },
        "/items/{sku}": {
            "get": {
                "summary": "商品コードで在庫を取得",
                "parameters": [
                    {
                        "in": "path",
                        "name": "sku",
                        "required": True,
                        "schema": {"type": "string"},
                        "example": "TS-01",
                    }
                ],
                "responses": {
                    "200": {"description": "該当商品の在庫"},
                    "404": {"description": "商品が見つかりません"},
                },
            }
        },
    },
}


async def register(publish_now=False):
    editing = route().startswith("edit/")
    slug = ctx["detail"].get("slug") if editing else None
    if not slug:
        slug = value("api-slug").strip()
    if not editing and not slug:
        raise client.InputError("API識別名を入力してください")
    chosen = [value(k) for k in product_views.ENV if value(k)]
    if not chosen:
        raise client.InputError("接続先を一つ以上選んでください")
    bindings = ctx["me"]["targets"]
    spec_text = value("spec")
    files = document.getElementById("spec-file").files
    if files.length:
        file = files.item(0)
        if file.size > 500000:
            raise client.InputError("500KB以内のファイルを選んでください")
        spec_text = str(await file.text())
    try:
        spec = json.loads(spec_text)
        info = spec["info"]
    except (ValueError, TypeError, KeyError) as exc:
        raise client.InputError("OpenAPI 3.0 / 3.1 のJSONファイルを指定してください") from exc
    data = {
        "release_note": value("release-note"),
        "offers": {
            bindings[k]["environment"]: product_views.read_offer(bindings[k]["environment"], value)
            for k in chosen
        },
        "base_path": value("base-path"),
        "name": value("name") or info.get("title", ""),
        "slug": slug or None,
        "summary": value("summary") or info.get("description") or info.get("title", ""),
        "owner": bindings[chosen[0]]["owner"],
        "targets": {bindings[k]["environment"]: k for k in chosen},
        "spec": spec,
    }
    if editing:
        row = ctx["detail"]
        asset = await client.api("/apis/" + row["id"] + "?revision=" + str(row["revision"]), "PUT", data)
    else:
        asset = await client.api("/apis", "POST", data)
    await go("api/" + asset["id"])
    if publish_now and not asset["published"]:
        await publication(asset)
    else:
        ctx["message"] = (
            "掲載内容を保存しました"
            if asset["published"]
            else "下書きを保存しました。仕様を確認して公開してください。"
        )


def listing_identity(item):
    field("API名", "name", text=item.get("name", ""))
    if item.get("slug"):
        t.p("API識別名　" + item["slug"])
    else:
        field("API識別名", "api-slug", placeholder="stock-lookup")
        t.small(
            "呼び出しURLに使います。半角小文字の英字で始め、数字とハイフンも使えます。設定後は変更できません。"
        )
    field("用途・説明", "summary", text=item.get("summary", ""))


def inventory_form(asset=None):
    item = asset or {}
    t.p(
        "出品する環境の接続先とOpenAPI 3.0 / 3.1のJSONを選びます。API名と説明はファイルから取り込めます。",
        classes="muted",
    )
    with t.div(classes="box"):
        listing_identity(item)
        for env in product_views.ENV:
            opts = [("", "指定しない")] + [
                (k, k + " · " + v["owner"])
                for k, v in ctx["me"]["targets"].items()
                if v["environment"] == env
            ]
            field(LABEL[env] + "の接続先", env, options=opts, text=item.get("bindings", {}).get(env, ""))
            product_views.offer_editor(
                env,
                item.get("offers", {}).get(env, {}),
                field,
                bool(asset),
                ctx["policy_directory"]["units"],
            )
        field(
            "この版の変更内容",
            "release-note",
            textarea=True,
            text=item.get("release_note", ""),
            placeholder="例：在庫照会に倉庫別の検索を追加",
        )
        field(
            "接続先のベースパス（任意）",
            "base-path",
            text=item.get("base_path", ""),
            placeholder="/inventory/v1",
        )
        with t.label(classes="field"):
            t.span("OpenAPIファイル（JSON）")
            t.input(id="spec-file", type="file", accept=".json,application/json", classes="form-control")
        field(
            "またはOpenAPI定義を貼り付け（JSON）",
            "spec",
            textarea=True,
            text=json.dumps(item.get("spec", SAMPLE), ensure_ascii=False, indent=2)
            if asset or ctx["config"]["demo"]
            else "",
        )
        if asset:
            t.p(
                "仕様や接続先を変えると全環境の利用権と申請を終了します。利用条件のみの変更では、変更した環境で再申請が必要です。"
            )
        with t.div(classes="btn-grouping"):
            btn("変更を保存" if asset else "下書きを保存", register)
            btn("保存して公開", register, True, primary=True)


async def load_directory(_page):
    ctx["policy_directory"] = await client.api("/workspace")


def editor():
    if ctx["me"]["owners"]:
        inventory_form(ctx["detail"] if route().startswith("edit/") else None)


SCREENS = (
    Screen(
        "register",
        "APIを登録",
        editor,
        load_directory,
        parent="inventory",
        examples={"publish": lambda: listing_identity({})},
    ),
    Screen("edit/", "掲載内容を編集", editor, load_listing),
)
