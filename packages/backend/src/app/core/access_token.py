"""API呼び出し専用のエンドポイントで、ポータルが発行したアクセストークンを検証する。"""

import json
import os
import secrets
from dataclasses import replace

import jwt
from app.core import credential_policy
from app.core.auth import Actor, check_member
from app.core.workspace import ancestry, populate, private_project, stopped, units
from fastapi import HTTPException
from tsugite_db.models import PortalKey

_local_signer = secrets.token_bytes(64)
ISSUER = "tsugite-portal"
AUDIENCE = "tsugite-invoke"


def signer():
    if os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return os.environ["TOKEN_SIGNING_KEY"]
    return os.getenv("TOKEN_SIGNING_KEY") or _local_signer


def encode(claims):
    return "tst_" + jwt.encode({"iss": ISSUER, "aud": AUDIENCE, **claims}, signer(), algorithm="HS256")


def machine_actor(db, key):
    parents = ancestry(units(db), [key.project]) - {key.project}
    return Actor(
        "system-" + key.id,
        frozenset([key.project]),
        frozenset(),
        False,
        True,
        departments=frozenset(parents),
    )


def may_use(key, actor):
    if actor.machine:
        return key.mode == "system"
    conf = json.loads(key.config)
    return (
        (key.project in actor.projects or key.project == private_project(actor.subject))
        and (key.kind == "shared" or key.creator == actor.subject)
        and (not conf["users"] or actor.subject in conf["users"])
    )


def resolve(db, token):
    try:
        claims = jwt.decode(
            token[4:],
            signer(),
            algorithms=["HS256"],
            issuer=ISSUER,
            audience=AUDIENCE,
            options={
                "require": [
                    "iss",
                    "aud",
                    "exp",
                    "iat",
                    "sub",
                    "client",
                    "gen",
                    "jti",
                    "service",
                    "base",
                ],
                "verify_exp": False,
                "verify_iat": False,
            },
        )
        now = credential_policy.clock()
        if not claims["iat"] <= now < claims["exp"]:
            raise ValueError("expired")
        key = db.get(PortalKey, claims["client"])
        if not key or not key.mode or key.revoked or key.revision != claims["gen"]:
            raise ValueError("revoked")
    except (ValueError, jwt.PyJWTError, KeyError) as exc:
        raise HTTPException(401, "トークンが失効しました。再発行してください") from exc
    if claims["service"]:
        actor = machine_actor(db, key)
    else:
        base = frozenset(claims["base"])
        actor = populate(db, Actor(claims["sub"], base, frozenset(), False, False))
        check_member(db, actor)
    if not may_use(key, actor) or stopped(db, actor, key.project):
        raise HTTPException(403, "この認証情報を利用できません")
    return replace(
        actor,
        key_id=key.id,
        key_shared=key.kind == "shared",
        issued=claims["iat"],
        expires=claims["exp"],
        generation=key.revision,
    )
