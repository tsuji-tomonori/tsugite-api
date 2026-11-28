"""商品を提供する環境ごとに利用条件と承認の順序を管理する。"""

import json
from typing import Any

from app.core.publication import assigned
from app.core.workspace import delegated
from fastapi import HTTPException
from tsugite_db.models import now


def configured(asset):
    return json.loads(asset.offers or "{}")


def describe(offer, revision, owner=False):
    public: dict[str, Any] = dict(offer, version=str(revision))
    if not owner:
        public["fields"] = [
            {"label": f["label"], "required": f["required"]} for f in offer.get("fields", [])
        ]
    return public


def submission(asset, data, actor):
    offer = configured(asset).get(data.environment, {})
    if data.offer_version and data.offer_version != str(asset.revision):
        raise HTTPException(409, "利用条件が変わりました。再読み込みしてください")
    fields = offer.get("fields", [])
    if (fields or offer.get("terms")) and not data.offer_version:
        raise HTTPException(409, "表示中の利用条件を確認してください")
    if offer.get("terms") and not data.terms_accepted:
        raise HTTPException(422, "利用規約への同意が必要です")
    if data.answers.keys() - {f["label"] for f in fields}:
        raise HTTPException(422, "未定義の申請項目があります")
    for f in fields:
        answer = data.answers.get(f["label"])
        if f["required"] and not answer:
            raise HTTPException(422, f["label"] + "を入力してください")
        if answer and f["allowed_values"] and answer not in f["allowed_values"]:
            raise HTTPException(422, f["label"] + "の許可情報を確認してください")
    route = offer.get("route", "legacy")
    steps = {
        "department_provider": ["department", "provider"],
        "provider": ["provider"],
        "department": ["department"],
        "custom": offer.get("steps", []),
    }.get(route, [])
    if "department" in steps and not actor.departments:
        raise HTTPException(422, "部署承認には申請者の所属部署を登録してください")
    evidence = {
        "route": route,
        "steps": steps,
        "decisions": [],
        "departments": sorted(actor.departments),
        "terms": offer.get("terms", ""),
        "submitted_at": now().isoformat(),
        "terms_accepted": bool(offer.get("terms") and data.terms_accepted),
        "version": str(asset.revision),
        "answers": data.answers,
    }
    return json.dumps(evidence, ensure_ascii=False), route, steps[0] if steps else None


def can_review(db, actor, asset, grant):
    if grant.applicant == actor.subject:
        return False
    if grant.stage:
        return assigned(grant.stage, actor, asset.owner, grant.application.get("departments", []))
    return asset.owner in actor.owners or delegated(db, actor, asset, grant)
