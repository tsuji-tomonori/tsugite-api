"""テスト用の在庫APIをHTTPSで提供する。"""

import json
import secrets
import ssl
import subprocess
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


@contextmanager
def https_stock(aws, directory, emulator_ca):
    token = secrets.token_urlsafe(32)
    secret = aws.client("secretsmanager").create_secret(
        Name="stock/https-" + secrets.token_hex(4), SecretString=token
    )
    calls = []

    class Stock(BaseHTTPRequestHandler):
        def reply(self, data):
            if self.headers.get("Authorization") != "Bearer " + token:
                self.send_error(403)
                return
            calls.append((self.command, self.path))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(data)

        def do_HEAD(self):
            self.reply(b"")

        def do_GET(self):
            responses = {
                "/warehouse/v1/items": {"items": [{"sku": "TS-01", "stock": 12}]},
                "/warehouse/v1/parcels/JP17": {"parcel": "JP17", "status": "配送中"},
                "/warehouse/v1/rates/JPY": {"currency": "JPY", "rate": 1},
                "/warehouse/v1/stores": {"stores": ["岐阜", "名古屋"]},
                "/warehouse/v1/calendar/next": {"business_date": "2026-11-24"},
            }
            if self.path not in responses:
                self.send_error(404)
                return
            self.reply(json.dumps(responses[self.path]).encode())

        def do_POST(self):
            if self.path != "/warehouse/v1/orders":
                self.send_error(404)
                return
            order = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.reply(json.dumps({"order": "PO-17", "units": order["units"]}).encode())

    cert, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-noenc",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-out",
            str(cert),
            "-keyout",
            str(key),
        ],
        check=True,
        capture_output=True,
    )
    bundle = directory / "trust.pem"
    bundle.write_bytes(Path(emulator_ca).read_bytes() + b"\n" + cert.read_bytes())
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    with ThreadingHTTPServer(("127.0.0.1", 0), Stock) as server:
        server.socket = tls.wrap_socket(server.socket, server_side=True)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield (
                {
                    "kind": "https",
                    "address": f"https://127.0.0.1:{server.server_port}/warehouse",
                    "secret_arn": secret["ARN"],
                },
                bundle,
                calls,
            )
        finally:
            server.shutdown()
            thread.join()
