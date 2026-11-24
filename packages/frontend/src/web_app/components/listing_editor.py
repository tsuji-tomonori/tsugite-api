# 掲載商品の編集フォームを描画する。
from __future__ import annotations

import json
from typing import Any

from actions.listing_editor import register
from content.portal_labels import LABEL
from puepy import t
from runtime.portal_ui import ctx, route

from components import product_views
from components.controls import btn, field

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


def listing_identity(item: dict[str, Any]) -> None:
    """商品識別子と基本情報の欄を表示する。"""
    field("API名", "name", text=item.get("name", ""))
    if item.get("slug"):
        t.p("API識別名　" + item["slug"])
    else:
        field("API識別名", "api-slug", placeholder="stock-lookup")
        t.small(
            "呼び出しURLに使います。半角小文字の英字で始め、数字とハイフンも使えます。設定後は変更できません。"
        )
    field("用途・説明", "summary", text=item.get("summary", ""))


def inventory_form(asset: dict[str, Any] | None = None) -> None:
    """商品情報と環境別の利用条件を入力する欄を表示する。"""
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


def editor() -> None:
    """新規または既存商品の編集欄を表示する。"""
    if ctx["me"]["owners"]:
        inventory_form(ctx["detail"] if route().startswith("edit/") else None)
