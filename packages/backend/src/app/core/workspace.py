# 所属組織に基づいて商品の公開範囲と利用権を判定する。
"""Effective membership, catalog audience and invocation boundaries."""

import hashlib
import json
from collections import defaultdict
from dataclasses import replace

from app.core.config import local_demo, settings, targets
from app.core.metadata import BUILTIN_FIELDS, DEPARTMENT, PROJECT
from sqlalchemy import select
from tsugite_db.models import Affiliation, DirectoryTree, LogUnit, Member


def private_project(subject):
    return "person-" + hashlib.sha256(subject.encode()).hexdigest()[:32]


def configured_projects():
    cfg = settings()
    ids = (
        set(cfg.get("projects", []))
        | {t["owner"] for t in cfg.get("targets", {}).values()}
        | {m["project"] for m in cfg.get("machine_projects", [])}
    )
    if local_demo():
        ids.update(["finance", "supply"])
    return ids


def retired_units(db):
    if "retired_units" not in db.info:
        row = db.get(DirectoryTree, "retired")
        db.info["retired_units"] = json.loads(row.units) if row else {}
    return db.info["retired_units"]


def project_ids(db, ids):
    retired = retired_units(db)
    return frozenset(current for key in ids if (current := retired.get(key, key)))


def workspace_targets(db):
    retired = retired_units(db)
    return {
        key: target.model_copy(update={"owner": owner})
        for key, target in targets().items()
        if (owner := retired.get(target.owner, target.owner))
    }


def units(db):
    base = {k: dict(id=k, name=k, kind=PROJECT, parent="", stopped=False) for k in configured_projects()}
    if "workspace_tree" not in db.info:
        db.info["workspace_tree"] = db.get(DirectoryTree, "tree")
    saved = db.info["workspace_tree"]
    if saved:
        base.update(json.loads(saved.units))
    return {k: v for k, v in base.items() if k not in retired_units(db)}


def project_label(tree, project):
    unit = tree.get(project)
    if not unit or unit["name"] == project:
        return f"名称未登録（{project}）"
    parent = tree.get(unit["parent"])
    return f"{parent['name']} / {unit['name']}" if parent else unit["name"]


def ancestry(tree, ids):
    found = set()
    for start in ids:
        node = start
        while node and node not in found:
            found.add(node)
            node = tree.get(node, {}).get("parent")
    return found


def populate(db, actor):
    actor = replace(
        actor,
        projects=project_ids(db, actor.projects),
        owners=project_ids(db, actor.owners),
        base_projects=project_ids(db, actor.base_projects),
    )
    if actor.machine:
        return actor
    tree = units(db)
    projects = set(actor.projects)
    account = db.get(Member, actor.subject)
    if (
        account
        and account.project
        and not account.deleted
        and account.project not in configured_projects()
    ):
        inherited = project_ids(db, [account.project])
        projects.update(inherited)
    metadata = defaultdict(set)
    metadata_leads = set()
    leads = set()
    titles = set()
    for m in db.scalars(select(Affiliation).where(Affiliation.subject == actor.subject)):
        item = tree.get(m.unit_id)
        if not item:
            continue
        if not m.active:
            projects.discard(m.unit_id)
            continue
        kind = item["kind"]
        metadata[kind].add(m.unit_id)
        if m.leader:
            metadata_leads.add(m.unit_id)
        if kind not in BUILTIN_FIELDS:
            continue
        if m.leader:
            leads.add(m.unit_id)
        if m.title:
            titles.add(m.title)
    projects.update(metadata[PROJECT])
    metadata[PROJECT] = projects
    return replace(
        actor,
        metadata={key: frozenset(values) for key, values in metadata.items() if values},
        metadata_leads=frozenset(metadata_leads),
        projects=frozenset(projects),
        owners=frozenset(projects),
        departments=frozenset(ancestry(tree, metadata[DEPARTMENT])),
        leads=frozenset(leads),
        titles=frozenset(titles),
    )


def policy(asset):
    return json.loads(asset.policy) if asset.policy else {}


def allowed_audience(asset, actor):
    p = policy(asset)
    return (
        asset.owner in actor.owners
        or p.get("visibility", "all") == "all"
        or bool(actor.projects.intersection(p.get("projects", [])))
        or bool(actor.departments.intersection(p.get("departments", [])))
        or any(
            not values.isdisjoint(p.get("metadata_values", []))
            for kind, values in actor.metadata.items()
            if kind not in BUILTIN_FIELDS
        )
    )


def attribution(db, actor, project):
    return ancestry(units(db), set(actor.departments) | ({project} if project else set()))


def stopped(db, actor, project):
    tree = units(db)
    return any(
        tree.get(k, {}).get("stopped") for k in ancestry(tree, set(actor.departments) | {project})
    )


def attribute(db, request_id, actor, project):
    for unit_id in attribution(db, actor, project):
        db.add(LogUnit(request_id=request_id, unit_id=unit_id))


def delegated(db, actor, asset, grant):
    if not grant.applicant or grant.applicant == actor.subject:
        return False
    tree = units(db)
    leaders = {k for k in actor.leads if tree.get(k, {}).get("kind") == DEPARTMENT}
    assigned = leaders.intersection(policy(asset).get("delegates", []))
    if not assigned:
        return False
    applicant_units = db.scalars(
        select(Affiliation.unit_id).where(
            Affiliation.active.is_(True), Affiliation.subject == grant.applicant
        )
    )
    return bool(
        assigned
        & ancestry(tree, [u for u in applicant_units if tree.get(u, {}).get("kind") == DEPARTMENT])
    )
