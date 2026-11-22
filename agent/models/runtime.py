"""Download the pinned model once per Lambda execution environment."""

import hashlib
import json
import os
from functools import cache
from pathlib import Path

import boto3


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
            boto3.client("s3").download_file(os.environ["MODEL_BUCKET"], object_key(role, item), str(temp))
            if "sha256" in item:
                with temp.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                        raise ValueError("Model checksum does not match the manifest")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)
    return str(path)
