"""HTTP受付用とワーカー用のLambdaで非同期ジョブを共有し、保存した処理結果をAPIに返す。"""

import json
import os
from dataclasses import asdict
from functools import cache
from hashlib import sha256
from time import time
from typing import Any, Protocol, cast

import boto3
from app.core.auth import Actor
from app.core.catalog_visibility import visible_collection
from app.core.chat_search import ask
from app.core.diagnostics import OperationalRepair, emit
from app.core.log_record import SCREENS
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from tsugite_db.session import engine

JOB_SECONDS = 150
JOB_TTL = 900
FAILED = {"kind": "error", "answer": "回答を準備できませんでした。時間をおいて再度お試しください。"}
SETS = ("projects", "owners", "departments", "leads", "titles", "base_projects")


class JobTable(Protocol):
    def get_item(self, *, Key: dict[str, str], ConsistentRead: bool) -> dict[str, Any]: ...
    def put_item(self, *, Item: dict[str, Any], **conditions: object) -> object: ...
    def update_item(
        self, *, Key: dict[str, str], UpdateExpression: str, **conditions: object
    ) -> object: ...


class DynamoResource(Protocol):
    def Table(self, name: str) -> JobTable: ...


class RateLimited(Exception):
    pass


@cache
def table() -> JobTable:
    dynamodb = cast(DynamoResource, boto3.resource("dynamodb"))
    return dynamodb.Table(os.environ["CHAT_TABLE"])


@cache
def lambda_client():
    return boto3.client(
        "lambda",
        config=Config(connect_timeout=3, read_timeout=70, retries={"total_max_attempts": 1}),
    )


def key_for(subject, job_id):
    return "job/" + sha256(subject.encode()).hexdigest() + "/" + str(job_id)


def submit(question, actor, job_id, request_id=None, screen=None):
    key = key_for(actor.subject, job_id)
    data = asdict(actor)
    data.pop("metadata_leads", None)
    data["metadata"] = {key: sorted(values) for key, values in actor.metadata.items()}
    for name in SETS:
        data[name] = sorted(data[name])
    now = int(time())
    if table().get_item(Key={"pk": key}, ConsistentRead=True).get("Item"):
        return
    try:
        table().put_item(
            Item={"pk": key.rsplit("/", 1)[0], "expires": now + 4},
            ConditionExpression="attribute_not_exists(pk) OR #ttl <= :now",
            ExpressionAttributeNames={"#ttl": "expires"},
            ExpressionAttributeValues={":now": now},
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        raise RateLimited from exc
    table().put_item(Item={"pk": key, "deadline": now + JOB_SECONDS, "expires": now + JOB_TTL})
    try:
        lambda_client().invoke(
            FunctionName=os.environ["CHAT_WORKER"],
            InvocationType="Event",
            Payload=json.dumps(
                {
                    "key": key,
                    "question": question,
                    "actor": data,
                    "request_id": request_id,
                    "screen": screen if screen in SCREENS else None,
                }
            ).encode(),
        )
    except Exception:
        store(key, FAILED)
        raise


def status(subject, job_id):
    job = table().get_item(Key={"pk": key_for(subject, job_id)}, ConsistentRead=True).get("Item")
    if not job or job["expires"] <= time():
        return None
    if "result" in job:
        return json.loads(job["result"])
    return FAILED if job["deadline"] <= time() else {}


def store(key, result):
    try:
        table().update_item(
            Key={"pk": key},
            UpdateExpression="SET #result = :result",
            ConditionExpression="attribute_exists(pk) AND attribute_not_exists(#result)",
            ExpressionAttributeNames={"#result": "result"},
            ExpressionAttributeValues={":result": json.dumps(result, ensure_ascii=False)},
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def models(role: str, data: dict[Any, Any], **fields) -> dict:
    name = os.environ.get("CHAT_" + role.upper())
    if not name:
        return {}
    try:
        invocation = lambda_client().invoke(
            FunctionName=name,
            Payload=json.dumps(
                {**data, "log_context": fields} if fields else data, ensure_ascii=False
            ).encode(),
        )
        if not invocation.get("FunctionError"):
            payload = json.load(invocation["Payload"])
            if isinstance(payload, dict):
                return payload
        reason = "model_response_invalid"
    except Exception as exc:
        reason = type(exc).__name__
    emit(
        "chat.model_unavailable",
        source="worker",
        route="/api/chat",
        method="POST",
        failed=True,
        operation=role,
        reason=reason,
        **fields,
    )
    return {}


def handler(event, context):
    fields = {
        "actor_id": event.get("actor", {}).get("subject"),
        "request_id": event.get("request_id") or getattr(context, "aws_request_id", None),
        "screen": event.get("screen"),
    }
    try:
        return process(event, fields)
    except Exception as exc:
        emit(
            "chat.worker_error",
            source="worker",
            route="/api/chat",
            method="POST",
            failed=True,
            reason=type(exc).__name__,
            **fields,
        )
        raise


def process(event, fields):
    key = event["key"]
    job = table().get_item(Key={"pk": key}, ConsistentRead=True).get("Item")
    if not job or job.get("result") or job["deadline"] <= time():
        return
    data = event["actor"]
    actor = Actor(
        **{
            **data,
            **{name: frozenset(data[name]) for name in SETS},
            "metadata": {key: frozenset(values) for key, values in data.get("metadata", {}).items()},
        }
    )

    def products():
        with Session(engine()) as db:
            return visible_collection(db, actor, spec=True)

    try:
        result = ask(event["question"], products, actor, lambda role, data: models(role, data, **fields))
    except OperationalRepair as exc:
        emit(
            "chat.worker_error",
            source="worker",
            route="/api/chat",
            method="POST",
            **exc.fields,
            **fields,
        )
        result = FAILED
    except Exception as exc:
        emit(
            "chat.worker_error",
            source="worker",
            route="/api/chat",
            method="POST",
            failed=True,
            reason=type(exc).__name__,
            **fields,
        )
        result = FAILED
    store(key, result)
