# モデルを取得して実行環境にキャッシュする。
"""Download the pinned model once per Lambda execution environment."""

import hashlib
import json
import os
from functools import cache, wraps
from pathlib import Path

import boto3
from log_record import log_record


class WeightMismatch(ValueError):
    """The downloaded object differs from a pinned weight."""


def model_failure(event, context, exc):
    fields = event.get("log_context", {})
    role = os.environ.get("MODEL_ROLE")
    action = None
    if isinstance(exc, WeightMismatch):
        action = "対象モデルのmanifest.jsonにあるSHA-256とS3の重みを照合する。固定版の重みを復元し、推論が成功することを確認する。"
    entry = log_record(
        "model.failure",
        source="model",
        operation=role,
        method="POST",
        route="/api/chat",
        failed=True,
        action=action,
        reason=type(exc).__name__,
        actor_id=fields.get("actor_id"),
        screen=fields.get("screen"),
        request_id=fields.get("request_id") or getattr(context, "aws_request_id", None),
    )
    print(json.dumps(entry, ensure_ascii=False))


def logged_model(handler):
    @wraps(handler)
    def invoke(event, context):
        try:
            return handler(event, context)
        except Exception as exc:
            model_failure(event, context, exc)
            raise

    return invoke


@cache
def manifest():
    return json.loads(Path(__file__).with_name("manifest.json").read_text(encoding="utf-8"))


def object_key(role, item):
    return f"tsugite-chat-models/{role}/{item.get('sha256', item['revision'])}/{item['name']}"


@cache
def model_file(role, name):
    item = next(item for item in manifest()[role] if item["name"] == name)
    path = Path("/tmp") / f"{role}-{name}"
    if not path.exists():
        temp = path.with_suffix(".download")
        try:
            boto3.client("s3").download_file(
                os.environ["MODEL_BUCKET"], object_key(role, item), str(temp)
            )
            if "sha256" in item:
                with temp.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                        raise WeightMismatch("Model checksum does not match the manifest")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    return str(path)
