"""Effective membership, catalog audience and invocation boundaries."""

import hashlib
import json
from dataclasses import replace

from app.core.config import local_demo, settings
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


def units(db):
    base = {
        k: dict(id=k, name=k, kind="project", parent="", stopped=False) for k in configured_projects()
    }
    if "workspace_tree" not in db.info:
        db.info["workspace_tree"] = db.get(DirectoryTree, "tree")
    saved = db.info["workspace_tree"]
    if saved:
        base.update(json.loads(saved.units))
    return base


def ancestry(tree, ids):
    found = set()
    for start in ids:
        node = start
        while node and node not in found:
            found.add(node)
            node = tree.get(node, {}).get("parent")
    return found


def populate(db, actor):
    if actor.machine:
        return actor
    tree = units(db)
    projects = set(actor.projects)
    owners = set(actor.owners)
    account = db.get(Member, actor.subject)
    if (
        account
        and account.project
        and not account.deleted
        and account.project not in configured_projects()
    ):
        projects.add(account.project)
        if account.role == "provider":
            owners.add(account.project)
    departments = set()
    leads = set()
    titles = set()
    for m in db.scalars(select(Affiliation).where(Affiliation.subject == actor.subject)):
        item = tree.get(m.unit_id)
        if not item:
            continue
        if not m.active:
            projects.discard(m.unit_id)
            owners.discard(m.unit_id)
            continue
        if item["kind"] == "department":
            departments.add(m.unit_id)
        else:
            projects.add(m.unit_id)
        if m.leader:
            leads.add(m.unit_id)
        if m.title:
            titles.add(m.title)
    return replace(
        actor,
        projects=frozenset(projects),
        owners=frozenset(owners),
        departments=frozenset(ancestry(tree, departments)),
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
    leaders = {k for k in actor.leads if tree.get(k, {}).get("kind") == "department"}
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
        & ancestry(tree, [u for u in applicant_units if tree.get(u, {}).get("kind") == "department"])
    )
