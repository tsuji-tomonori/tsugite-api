"""Store a canonical document once for each product and content digest."""

import hashlib
import json
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def archive_spec(asset_id, spec):
    body = canonical(spec)
    digest = hashlib.sha256(body).hexdigest()
    bucket = os.getenv("SPEC_BUCKET")
    if bucket:
        try:
            #: API仕様文書の保管（Amazon S3） / API仕様文書を保存
            boto3.client("s3").put_object(
                Bucket=bucket,
                Key=f"specs/{asset_id}/{digest}.json",
                ContentType="application/json",
                Body=body,
                IfNoneMatch="*",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("PreconditionFailed", "412"):
                raise HTTPException(503, "OpenAPIを保存できませんでした。再試行してください") from exc
        except BotoCoreError as exc:
            raise HTTPException(503, "OpenAPIを保存できませんでした。再試行してください") from exc
    elif os.getenv("DSQL_HOST") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        raise HTTPException(503, "OpenAPIの保存先を設定してください")
    return digest
