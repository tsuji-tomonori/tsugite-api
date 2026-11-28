"""テスト用ポータルを起動する。"""

import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]


@contextmanager
def serve_portal(env, *, log=None):
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "packages/database/alembic.ini", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=True,
    )
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    try:
        for _ in range(100):
            try:
                with urlopen(url + "/api/health", timeout=0.5) as r:
                    if r.status == 200:
                        break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("ポータルが起動しませんでした")
        yield url
    finally:
        proc.terminate()
        proc.wait(timeout=10)
