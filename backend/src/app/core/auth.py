import secrets
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import local_demo, settings

bearer = HTTPBearer(auto_error=False)
_demo_key = secrets.token_bytes(48)
DEMO_GROUPS = {"provider":["own-supply"],"consumer":["use-finance"],"auditor":["audit"]}


@dataclass(frozen=True)
class Actor:
    subject: str
    projects: frozenset[str]
    owners: frozenset[str]
    auditor: bool
    machine: bool


@lru_cache
def keyset(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(issuer + "/.well-known/jwks.json",timeout=4)


def demo_token(persona: str) -> str:
    from time import time
    if not local_demo() or persona not in DEMO_GROUPS:
        raise HTTPException(404)
    return jwt.encode({"sub":persona,"exp":int(time())+3600,"groups":DEMO_GROUPS[persona]},_demo_key,algorithm="HS256")


def identify(token: str) -> Actor:
    cfg = settings()
    try:
        if local_demo():
            claims = jwt.decode(token,_demo_key,algorithms=["HS256"],options={"require":["exp","sub"]})
            groups = claims["groups"]
        else:
            issuer = cfg["issuer"]
            claims = jwt.decode(token,keyset(issuer).get_signing_key_from_jwt(token).key,algorithms=["RS256"],
                                issuer=issuer,options={"verify_aud":False,"require":["exp","iss","sub","client_id"]})
            if claims.get("token_use") != "access":
                raise ValueError("token_use")
            client = claims["client_id"]
            project = {m["client"]:m["project"] for m in cfg.get("machine_projects",[])}.get(client)
            if project and "hub/invoke" in claims.get("scope","").split():
                return Actor(client,frozenset([project]),frozenset(),False,True)
            if client != cfg["portal_client"]:
                raise ValueError("client")
            groups = claims.get("cognito:groups",[])
        owners = frozenset(g[4:] for g in groups if g.startswith("own-"))
        projects = frozenset(g[4:] for g in groups if g.startswith("use-")) | owners
        return Actor(claims["sub"],projects,owners,"audit" in groups,False)
    except (ValueError,KeyError,jwt.PyJWTError) as exc:
        raise HTTPException(401,"認証情報を確認してください") from exc


def current(credentials: Annotated[HTTPAuthorizationCredentials|None,Depends(bearer)]) -> Actor:
    if credentials is None:
        raise HTTPException(401,"ログインしてください")
    return identify(credentials.credentials)


def human(actor: Annotated[Actor,Depends(current)]) -> Actor:
    if actor.machine:
        raise HTTPException(403,"ポータルは利用者専用です")
    return actor
