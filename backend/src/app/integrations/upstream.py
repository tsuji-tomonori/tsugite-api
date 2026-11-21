import base64
import json
from functools import lru_cache

import boto3
import httpx
from app.core.config import Target
from botocore.config import Config
from fastapi import HTTPException, Response

MAX_BODY = 2_000_000


@lru_cache
def aws(service):
    return boto3.client(
        service, config=Config(connect_timeout=2, read_timeout=15, retries={"total_max_attempts": 1})
    )


def auth_headers(target: Target) -> dict[str, str]:
    if not target.secret_arn:
        return {}
    secret = aws("secretsmanager").get_secret_value(SecretId=target.secret_arn)["SecretString"]
    return {"authorization": "Bearer " + secret}


def probe(target: Target) -> None:
    """Check connectivity before advertising a target. Never invoke its business operation."""
    try:
        if target.kind == "lambda":
            aws("lambda").invoke(FunctionName=target.address, InvocationType="DryRun")
        elif target.kind == "https":
            with httpx.Client(timeout=4, follow_redirects=False, trust_env=False) as client:
                reply = client.head(target.address, headers=auth_headers(target))
                if reply.status_code not in (404, 405):
                    reply.raise_for_status()
    except Exception as exc:
        raise HTTPException(502, "接続先または接続権限を確認してください") from exc


def dispatch(target: Target, method: str, path: str, query: str, body: bytes, headers: dict) -> Response:
    if target.kind == "demo":
        payload = json.dumps(
            {
                "project": headers["x-tsugite-project"],
                "method": method,
                "path": path,
                "environment": target.environment,
            },
            ensure_ascii=False,
        ).encode()
        return response(200, payload, "application/json")
    if target.kind == "https":
        headers = {**headers, **auth_headers(target)}
        url = target.address.rstrip("/") + path
        with httpx.Client(timeout=12, follow_redirects=False, trust_env=False) as client:
            with client.stream(method, url, params=query, headers=headers, content=body) as r:
                data = bytearray()
                for chunk in r.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BODY:
                        raise HTTPException(502, "応答サイズが上限を超えました")
                return response(r.status_code, bytes(data), r.headers.get("content-type", ""))
    event = {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": query,
        "headers": headers,
        "requestContext": {
            "domainName": "tsugite.internal",
            "stage": "$default",
            "requestId": headers["x-request-id"],
            "http": {"method": method, "path": path, "sourceIp": "127.0.0.1", "protocol": "HTTP/1.1"},
        },
        "body": base64.b64encode(body).decode(),
        "isBase64Encoded": True,
    }
    result = aws("lambda").invoke(FunctionName=target.address, Payload=json.dumps(event).encode())
    if result.get("FunctionError"):
        raise HTTPException(502, "接続先でエラーが発生しました")
    data = json.load(result["Payload"])
    payload = (
        base64.b64decode(data.get("body", ""))
        if data.get("isBase64Encoded")
        else data.get("body", "").encode()
    )
    return response(
        int(data["statusCode"]),
        payload,
        {k.lower(): v for k, v in data.get("headers", {}).items()}.get("content-type", ""),
    )


def response(status: int, body: bytes, media: str) -> Response:
    if len(body) > MAX_BODY:
        raise HTTPException(502, "応答サイズが上限を超えました")
    kind = media.partition(";")[0].strip().lower()
    if kind not in {"application/json", "application/problem+json", "text/plain"}:
        kind = "application/octet-stream"
    return Response(
        content=body,
        status_code=status,
        media_type=kind,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )
