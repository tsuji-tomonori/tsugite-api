import json
import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, model_validator


def local_demo() -> bool:
    return os.getenv("TSUGITE_DEMO") == "1" and not os.getenv("AWS_LAMBDA_FUNCTION_NAME")


class Target(BaseModel):
    owner: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    environment: Literal["sandbox", "production"]
    kind: Literal["lambda", "https", "demo"]
    address: str
    secret_arn: str = ""

    @model_validator(mode="after")
    def valid_binding(self):
        from urllib.parse import urlsplit

        if self.kind == "https":
            url = urlsplit(self.address)
            if (
                url.scheme != "https"
                or not url.hostname
                or url.username
                or url.password
                or url.query
                or url.fragment
            ):
                raise ValueError("HTTPS接続先を確認してください")
        if self.kind == "demo" and not local_demo():
            raise ValueError("デモ接続はローカル専用です")
        return self


@lru_cache
def settings() -> dict:
    if name := os.getenv("HUB_SETTINGS_PARAMETER"):
        import boto3

        value = boto3.client("ssm").get_parameter(Name=name)["Parameter"]["Value"]
        return json.loads(value)
    if os.getenv("HUB_SETTINGS_FILE"):
        with open(os.environ["HUB_SETTINGS_FILE"], encoding="utf-8") as file:
            return json.load(file)
    if local_demo():
        return {
            "targets": {
                "sample-sandbox": {
                    "owner": "supply",
                    "environment": "sandbox",
                    "kind": "demo",
                    "address": "sample",
                },
                "sample-production": {
                    "owner": "supply",
                    "environment": "production",
                    "kind": "demo",
                    "address": "sample",
                },
            }
        }
    return {}


def targets() -> dict[str, Target]:
    return {k: Target.model_validate(v) for k, v in settings().get("targets", {}).items()}
