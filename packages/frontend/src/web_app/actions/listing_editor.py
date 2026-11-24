# 掲載商品の登録と編集を扱う。
from __future__ import annotations

import json

from apis import client
from apis import organization as organization_api
from apis import products as products_api
from components import product_views
from js import document
from routing.portal_navigation import go
from runtime.portal_ui import ctx, route, value

from actions.listing_data import publication


async def register(publish_now: bool = False) -> None:
    """フォームの入力を商品として保存する。"""
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
        asset = await products_api.update_asset(row["id"], row["revision"], data)
    else:
        asset = await products_api.create_asset(data)
    await go("api/" + asset["id"])
    if publish_now and not asset["published"]:
        await publication(asset)
    else:
        ctx["message"] = (
            "掲載内容を保存しました"
            if asset["published"]
            else "下書きを保存しました。仕様を確認して公開してください。"
        )


async def load_directory(_page: str) -> None:
    """編集で選択できる部署とプロジェクトを取得する。"""
    ctx["policy_directory"] = await organization_api.workspace()
