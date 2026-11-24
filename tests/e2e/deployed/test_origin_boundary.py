"""デプロイした同一スタックの2経路を、利用者の認証情報を使わずに照合する。"""

import json
import os
from pathlib import Path

import httpx


def test_deployed_origin_boundary():
    """ヘルスチェックはCloudFront経由で200になり、API Gateway直アクセスは入口で403になる。"""
    outputs = json.loads(Path(os.environ["STACK_OUTPUTS"]).read_text())["TsugiteApi"]
    with httpx.Client(timeout=45, follow_redirects=False) as client:
        public = client.get(outputs["PortalUrl"].rstrip("/") + "/api/health")
        assert public.status_code == 200 and public.json() == {"status": "ok"}
        assert public.headers.get("x-amz-cf-id")
        direct = client.get(outputs["GatewayEndpoint"].rstrip("/") + "/api/health")
        assert direct.status_code == 403 and direct.json() == {"detail": "入口を確認してください"}
