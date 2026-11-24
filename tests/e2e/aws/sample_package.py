"""エミュレーターへ登録した配布ZIPをCPythonで展開・実行する独立プロセス。"""

import json
import sys

# 起動オプション -I -S により、開発環境のsite-packagesは使用しない。
sys.path.insert(0, sys.argv[1])
from sample_api.main import handler  # noqa: E402

for event in json.load(sys.stdin):
    print(json.dumps(handler(event, None)))
