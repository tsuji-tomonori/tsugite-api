import json
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from openapi_spec_validator import validate
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.apis.schemas import Apply, Audit, Decision, Detail, Listing, Register, Right
from app.core.auth import Actor, human
from app.core.config import targets
from app.db.models import Access, Asset, Event, new_id
from app.db.session import session

router = APIRouter()
DB = Annotated[Session,Depends(session)]
User = Annotated[Actor,Depends(human)]


def event(db, request, actor, asset, action, project="", environment="", detail=""):
    db.add(Event(actor=actor.subject,asset_id=asset.id,owner=asset.owner,project=project,
                 environment=environment,action=action,detail=detail,request_id=request.state.request_id))


def record(db: Session, key: str) -> Asset:
    row = db.get(Asset,key)
    if row is None:
        raise HTTPException(404,"APIが見つかりません")
    return row


def listing(row: Asset) -> Listing:
    return Listing(id=row.id,owner=row.owner,name=row.name,summary=row.summary,
                   environments=list(json.loads(row.targets)),published=row.published,revision=row.revision)


def right_id(asset_id: str, project: str, environment: str) -> str:
    return "/".join((asset_id,project,environment))


def allowed_spec(node):
    if isinstance(node,dict):
        return all((key not in {"$ref","$dynamicRef","$recursiveRef"} or isinstance(v,str) and v.startswith("#/"))
                   and key not in {"$id","$dynamicAnchor"} and allowed_spec(v) for key,v in node.items())
    return not isinstance(node,list) or all(allowed_spec(v) for v in node)


@router.get("/me")
def me(actor: User):
    return {"subject":actor.subject,"projects":sorted(actor.projects),"owners":sorted(actor.owners),
            "auditor":actor.auditor,"targets":{k:{"owner":v.owner,"environment":v.environment}
                  for k,v in targets().items() if v.owner in actor.owners}}


@router.get("/apis",response_model=list[Listing])
def catalog(actor: User, db: DB, q: str = Query("",max_length=120), inventory: bool=False):
    stmt = select(Asset).where(Asset.owner.in_(actor.owners) if inventory else Asset.published.is_(True))
    if q.strip():
        term=q.strip()
        stmt=stmt.where(or_(Asset.name.icontains(term,autoescape=True),Asset.summary.icontains(term,autoescape=True),
                            Asset.owner.icontains(term,autoescape=True)))
    return [listing(a) for a in db.scalars(stmt.order_by(Asset.name,Asset.id))]


@router.post("/apis",response_model=Listing,status_code=201)
def register(data: Register, request: Request, actor: User, db: DB):
    if data.owner not in actor.owners:
        raise HTTPException(403,"提供プロジェクトの権限が必要です")
    bindings = targets()
    for env,key in data.targets.items():
        target = bindings.get(key)
        if not target or target.owner != data.owner or target.environment != env:
            raise HTTPException(422,"プロジェクトと環境に対応する接続先を選んでください")
    spec = json.dumps(data.spec,ensure_ascii=False)
    if len(spec.encode())>500_000 or not allowed_spec(data.spec) or not data.spec.get("paths"):
        raise HTTPException(422,"外部参照を含まない500KB以内のOpenAPI JSONを指定してください")
    if not str(data.spec.get("openapi","")).startswith(("3.0.","3.1.")):
        raise HTTPException(422,"OpenAPI 3.0または3.1を指定してください")
    try:
        validate(data.spec)
    except Exception as exc:
        raise HTTPException(422,"OpenAPIの形式または内部参照を確認してください") from exc
    row = Asset(id=new_id(),name=data.name,summary=data.summary,owner=data.owner,
                base_path=data.base_path,targets=json.dumps(data.targets),spec=spec,published=False)
    db.add(row)
    event(db,request,actor,row,"register",row.owner)
    db.commit()
    return listing(row)


@router.get("/apis/{key}",response_model=Detail)
def detail(key: str, actor: User, db: DB):
    a=record(db,key)
    grant=db.scalar(select(Access.id).where(Access.asset_id==key,Access.project.in_(actor.projects),Access.status=="approved").limit(1))
    if not a.published and a.owner not in actor.owners and not grant:
        raise HTTPException(404)
    return Detail(**listing(a).model_dump(),spec=json.loads(a.spec))


@router.put("/apis/{key}/publication",response_model=Listing)
def publish(key: str, published: bool, request: Request, actor: User, db: DB):
    a=record(db,key)
    if a.owner not in actor.owners:
        raise HTTPException(403)
    if a.published!=published:
        if published:
            bindings=targets()
            if any(name not in bindings or (bindings[name].owner,bindings[name].environment)!=(a.owner,env)
                   for env,name in json.loads(a.targets).items()):
                raise HTTPException(409,"接続設定を確認してください")
        a.published=published
        event(db,request,actor,a,"publish" if published else "unpublish",a.owner)
        db.commit()
    return listing(a)


@router.post("/apis/{key}/requests",status_code=201,response_model=Right)
def apply(key: str, data: Apply, request: Request, actor: User, db: DB):
    if data.project not in actor.projects:
        raise HTTPException(403)
    asset=record(db,key)
    if not asset.published or data.environment not in json.loads(asset.targets):
        raise HTTPException(409,"対象のAPIまたは環境は申請できません")
    key_id=right_id(key,data.project,data.environment)
    grant=db.get(Access,key_id)
    if grant is None:
        grant=Access(id=key_id,asset_id=key,project=data.project,environment=data.environment)
        db.add(grant)
    elif grant.status in {"pending","approved"}:
        raise HTTPException(409,"同じ環境への申請または利用権限がすでにあります")
    grant.status="pending"
    grant.reason=data.reason
    event(db,request,actor,asset,"apply",data.project,data.environment,data.reason)
    db.commit()
    return grant


@router.get("/requests",response_model=list[Right])
def requests(actor: User, db: DB, incoming: bool=False):
    stmt=select(Access,Asset.name).join(Asset,Asset.id==Access.asset_id)
    stmt=stmt.where(Asset.owner.in_(actor.owners) if incoming else Access.project.in_(actor.projects))
    return [Right.model_validate(row).model_copy(update={"asset_name":name}) for row,name in db.execute(stmt.order_by(Asset.name,Access.project,Access.environment))]


NEXT={"approve":("pending","approved"),"reject":("pending","rejected"),"withdraw":("pending","withdrawn"),
      "revoke":("approved","revoked")}


@router.post("/requests/{key}/{project}/{environment}",response_model=Right)
def decide(key: str, project: str, environment: str, data: Decision, request: Request, actor: User, db: DB):
    asset=record(db,key)
    allowed=project in actor.projects if data.action=="withdraw" else asset.owner in actor.owners
    if not allowed:
        raise HTTPException(403)
    row=db.get(Access,right_id(key,project,environment))
    if row is None:
        raise HTTPException(404)
    previous,following=NEXT[data.action]
    if row.status!=previous or row.revision!=data.revision:
        raise HTTPException(409,"申請状態が変わりました。再読み込みしてください")
    row.status=following
    event(db,request,actor,asset,data.action,project,environment,data.reason)
    db.commit()
    return row


@router.get("/audit",response_model=list[Audit])
def audit(actor: User, db: DB, asset_id: str="", request_id: str="", limit: int=Query(100,ge=1,le=500)):
    stmt=select(Event)
    if not actor.auditor:
        stmt=stmt.where(or_(Event.owner.in_(actor.owners),Event.project.in_(actor.projects)))
    if asset_id:
        stmt=stmt.where(Event.asset_id==asset_id)
    if request_id:
        stmt=stmt.where(Event.request_id==request_id)
    return list(db.scalars(stmt.order_by(Event.at.desc(),Event.id.desc()).limit(limit)))
