import secrets
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Annotated

import jwt
from app.core.config import local_demo, settings
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from tsugite_db.models import Member
from tsugite_db.session import session

bearer = HTTPBearer(auto_error=False)
_demo_key = secrets.token_bytes(48)
DEMO_GROUPS = {
    "provider": ["own-supply"],
    "consumer": ["use-finance"],
    "auditor": ["audit"],
    "admin": ["admin"],
}


@dataclass(frozen=True)
class Actor:
    subject: str
    projects: frozenset[str]
    owners: frozenset[str]
    auditor: bool
    machine: bool
    admin: bool = False
    departments: frozenset[str] = frozenset()
    leads: frozenset[str] = frozenset()
    titles: frozenset[str] = frozenset()
    key_id: str = ""
    key_shared: bool = False
    issued: int = 0
    expires: int = 0
    base_projects: frozenset[str] = frozenset()
    generation: int = 0
    metadata: dict[str, frozenset[str]] = field(default_factory=dict, hash=False)
    metadata_leads: frozenset[str] = frozenset()


@lru_cache
def keyset(issuer: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(issuer + "/.well-known/jwks.json", timeout=4)


def demo_token(persona: str, db: Session | None = None) -> str:
    from time import time

    groups = DEMO_GROUPS.get(persona)
    if local_demo() and groups is None and db is not None:
        from sqlalchemy import select

        member = db.scalar(select(Member).where(Member.username == persona, Member.deleted.is_(False)))
        if member:
            persona = member.subject
            groups = [("own-" if member.role == "provider" else "use-") + member.project]
    if not local_demo() or groups is None:
        raise HTTPException(404)
    return jwt.encode(
        {"sub": persona, "iat": int(time()), "exp": int(time()) + 3600, "groups": groups},
        _demo_key,
        algorithm="HS256",
    )


def identify(token: str) -> Actor:
    cfg = settings()
    try:
        if local_demo():
            claims = jwt.decode(
                token, _demo_key, algorithms=["HS256"], options={"require": ["exp", "sub"]}
            )
            groups = claims["groups"]
        else:
            issuer = cfg["issuer"]
            claims = jwt.decode(
                token,
                keyset(issuer).get_signing_key_from_jwt(token).key,
                algorithms=["RS256"],
                issuer=issuer,
                options={"verify_aud": False, "require": ["exp", "iss", "sub", "client_id"]},
            )
            if claims.get("token_use") != "access":
                raise ValueError("token_use")
            client = claims["client_id"]
            project = {m["client"]: m["project"] for m in cfg.get("machine_projects", [])}.get(client)
            if project and "hub/invoke" in claims.get("scope", "").split():
                return Actor(
                    client,
                    frozenset([project]),
                    frozenset(),
                    False,
                    True,
                    issued=int(claims.get("iat", 0)),
                    expires=int(claims["exp"]),
                )
            if client != cfg["portal_client"]:
                raise ValueError("client")
            groups = claims.get("cognito:groups", [])
        owners = frozenset(g[4:] for g in groups if g.startswith("own-"))
        projects = frozenset(g[4:] for g in groups if g.startswith("use-")) | owners
        return Actor(
            claims["sub"],
            projects,
            owners,
            "audit" in groups,
            False,
            "admin" in groups,
            issued=int(claims.get("iat", 0)),
            expires=int(claims["exp"]),
            base_projects=projects,
        )
    except jwt.exceptions.PyJWKClientConnectionError as exc:
        raise HTTPException(503, "認証サービスに接続できませんでした") from exc
    except (ValueError, KeyError, jwt.PyJWTError) as exc:
        raise HTTPException(401, "認証情報を確認してください") from exc


def check_member(db, actor):
    if not actor.machine:
        member = db.get(Member, actor.subject)
        if member and member.deleted:
            raise HTTPException(403, "削除済みの利用者です")


def current(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(session)],
) -> Actor:
    if credentials is None:
        raise HTTPException(401, "ログインしてください")
    actor = identify(credentials.credentials)
    request.state.actor_id = actor.subject
    check_member(db, actor)
    from app.core.workspace import populate

    return populate(db, actor)


def human(actor: Annotated[Actor, Depends(current)]) -> Actor:
    if actor.machine:
        raise HTTPException(403, "ポータルは利用者専用です")
    return actor
