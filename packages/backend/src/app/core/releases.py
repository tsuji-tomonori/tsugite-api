# 商品の公開版と変更履歴を扱う。
import hashlib
import json

from app.core.diagnostics import asset_object
from app.core.openapi import path_items
from app.integrations.spec_archive import archive_spec, canonical
from sqlalchemy import select
from tsugite_db.models import SpecRelease


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def entries(spec):
    items = {}
    for path, item in path_items(spec):
        shared = {k: v for k, v in item.items() if k in ("parameters", "servers", "$ref")}
        for method in ("get", "post", "put", "patch", "delete", "head", "options", "trace"):
            if method in item:
                items[method.upper() + " " + path] = fingerprint([shared, item[method]])
    for group, definitions in spec.get("components", {}).items():
        if isinstance(definitions, dict):
            for name, definition in definitions.items():
                items[f"components/{group}/{name}"] = fingerprint(definition)
    return items


def record_release(db, asset):
    spec = asset_object(asset, "spec")
    digest = archive_spec(asset.id, spec)
    previous = db.scalar(
        select(SpecRelease)
        .where(SpecRelease.asset_id == asset.id)
        .order_by(SpecRelease.number.desc())
        .limit(1)
    )
    note = asset.release_note or ""
    if previous and previous.digest == digest and json.loads(previous.summary)["note"] == note:
        return
    before = json.loads(previous.manifest) if previous else {}
    after = entries(spec)
    summary = {
        "api_version": spec["info"]["version"],
        "openapi": spec["openapi"],
        "note": note,
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "changed": sorted(k for k in before.keys() & after.keys() if before[k] != after[k]),
    }
    db.add(
        SpecRelease(
            asset_id=asset.id,
            number=previous.number + 1 if previous else 1,
            digest=digest,
            manifest=json.dumps(after),
            summary=json.dumps(summary, ensure_ascii=False),
        )
    )


def history(db, asset):
    rows = db.scalars(
        select(SpecRelease).where(SpecRelease.asset_id == asset.id).order_by(SpecRelease.number.desc())
    )
    return [
        dict(json.loads(row.summary), number=row.number, published_at=row.at.isoformat()) for row in rows
    ]
