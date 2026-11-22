"""ブラウザー内のPythonで実行した画面コードの行遷移をテストランナーへ返す。"""

import json
import sys

from js import console


# このモジュールはテスト時にブラウザー内で実行する。
# 各ファイルで初めて通った行遷移のみを、関数から戻るときにまとめて通知する。
def start(files, prefix):
    seen = {name: set() for name in files}

    def trace(frame, event, arg):
        filename = frame.f_code.co_filename
        name = filename.rsplit("/", 1)[-1]
        if name not in seen or filename.rsplit("/", 1)[0] not in (name, ".", "/home/pyodide"):
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
