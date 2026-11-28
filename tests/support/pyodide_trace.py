# ブラウザー内のPythonで実行した画面コードの行遷移をテストランナーへ返す。
"""ブラウザー内のPythonで実行した画面コードの行遷移をテストランナーへ返す。"""

import json
import os
import sys

from js import console


# このモジュールはテスト時にブラウザー内で実行する。
# 各ファイルで初めて通った行遷移のみを、関数から戻るときにまとめて通知する。
def start(files, prefix):
    seen = {name: set() for name in files}
    paths = {
        path: name for name in files for path in (name, "./" + name, os.path.join(os.getcwd(), name))
    }

    def trace(frame, event, arg):
        name = paths.get(frame.f_code.co_filename)
        if name is None:
            return None

        entry = -frame.f_code.co_firstlineno
        previous = entry
        batch = []

        def record(frame, event, arg):
            nonlocal previous
            if event in ("line", "return"):
                current = frame.f_lineno if event == "line" else entry
                arc = (previous, current)
                if arc not in seen[name]:
                    seen[name].add(arc)
                    batch.append(arc)
                previous = current
                if event == "return" and batch:
                    console.debug(prefix + json.dumps([name, batch]))
            return record

        return record

    sys.settrace(trace)
