"""Durable asynchronous responses shared by the HTTP and worker Lambdas."""

import json
import os
from dataclasses import asdict
from functools import cache
from hashlib import sha256
from time import time
from typing import Any, Protocol, cast

import boto3
from app.apis.catalog.catalog.router import visible_collection
from app.core.auth import Actor
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session
from tsugite_db.session import engine

from agent.retrieval import ask

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


def submit(question, actor, job_id):
    key = key_for(actor.subject, job_id)
    data = asdict(actor)
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
            Payload=json.dumps({"key": key, "question": question, "actor": data}).encode(),
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


def models(role: str, data: dict[Any, Any]) -> dict:
    name = os.environ.get("CHAT_" + role.upper())
    if not name:
        return {}
    try:
        invocation = lambda_client().invoke(
            FunctionName=name, Payload=json.dumps(data, ensure_ascii=False).encode()
        )
        if not invocation.get("FunctionError"):
            payload = json.load(invocation["Payload"])
            if isinstance(payload, dict):
                return payload
    except Exception as exc:
        print(json.dumps({"event": "chat.model_unavailable", "role": role, "error": type(exc).__name__}))
    return {}


def handler(event, context):
    key = event["key"]
    job = table().get_item(Key={"pk": key}, ConsistentRead=True).get("Item")
    if not job or job.get("result") or job["deadline"] <= time():
        return
    data = event["actor"]
    actor = Actor(**{**data, **{name: frozenset(data[name]) for name in SETS}})

    def products():
        with Session(engine()) as db:
            return visible_collection(db, actor, spec=True)

    try:
        result = ask(event["question"], products, actor, models)
    except Exception as exc:
        print(json.dumps({"event": "chat.worker_error", "error": type(exc).__name__}))
        result = FAILED
    store(key, result)
