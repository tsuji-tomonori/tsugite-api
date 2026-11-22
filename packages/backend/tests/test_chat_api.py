from uuid import uuid4

from tests.support.catalog import FORM, headers


def ask(api, actor, question):
    key = str(uuid4())
    created = api.post("/api/chat", headers=actor, json={"job_id": key, "question": question})
    assert created.status_code == 202, created.text
    return key, api.get("/api/chat", headers=actor, params={"job_id": key}).json()


def test_chat_only_returns_currently_visible_products(portal):
    """チャットが公開中の商品だけを勧め、別の利用者や取り下げ後の閲覧を拒む。"""
    provider = headers(portal, "provider")
    consumer = headers(portal, "consumer")
    public = portal.post("/api/apis", headers=provider, json=FORM).json()["id"]
    portal.post("/api/apis", headers=provider, json={**FORM, "name": "在庫の下書き"})
    endpoint = f"/api/apis/{public}/publication"
    assert portal.put(endpoint, headers=provider, params={"published": True}).status_code == 200
    job, result = ask(portal, consumer, "在庫を確認できるAPIを探して")
    assert result["kind"] == "catalog"
    assert [row["id"] for row in result["products"]] == [public]
    assert portal.get("/api/chat", headers=provider, params={"job_id": job}).status_code == 404
    assert portal.put(endpoint, headers=provider, params={"published": False}).status_code == 200
    assert portal.get("/api/chat", headers=consumer, params={"job_id": job}).json()["kind"] == "empty"


def test_chat_cites_authored_guide_steps(portal):
    """操作の質問に実際の手順を返し、使い方ガイドを参照できる。"""
    _, result = ask(portal, headers(portal, "consumer"), "APIキーを発行する手順を教えて")
    assert result["kind"] == "manual"
    source = result["guides"][0]
    assert result["answer"] in [*source["steps"], source["result"]]
    assert "キー" in source["title"]


def test_invalid_worker_step_returns_first_visible_guide_step(portal, monkeypatch):
    """ワーカーの手順番号が文字列でも、閲覧できるガイドの最初の手順を案内する。"""
    from agent import jobs

    consumer = headers(portal, "consumer")
    key, manual = ask(portal, consumer, "APIキーを発行する手順を教えて")
    guide = manual["guides"][0]
    saved = {"kind": "manual", "answer": "", "keys": [guide["id"]], "focus": [guide["id"], "2"]}
    monkeypatch.setenv("CHAT_WORKER", "worker")
    monkeypatch.setattr(jobs, "status", lambda subject, job_id: saved)
    reply = portal.get("/api/chat", headers=consumer, params={"job_id": key})
    assert reply.status_code == 200
    assert reply.json()["answer"] == guide["steps"][0]


def test_inquiry_requires_explicit_submission_and_private_reply(portal):
    """問い合わせの案内だけでは未送信で、送信後の回答は本人と管理者にだけ表示する。"""
    consumer = headers(portal, "consumer")
    provider = headers(portal, "provider")
    admin = headers(portal, "admin")
    _, result = ask(portal, consumer, "運営に問い合わせたい")
    assert result["kind"] == "contact"
    assert portal.get("/api/inquiries", headers=consumer).json() == []
    identifier = uuid4()
    body = {"inquiry_id": str(identifier), "question": "利用申請の状態を調べてください"}
    for _ in range(2):
        assert portal.post("/api/inquiries", headers=consumer, json=body).status_code == 201
    assert portal.get("/api/inquiries", headers=provider).json() == []
    assert portal.get("/api/inquiries?incoming=true", headers=provider).status_code == 403
    records = portal.get("/api/inquiries?incoming=true", headers=admin).json()
    assert [row["inquiry_id"] for row in records] == [identifier.hex]
    path = f"/api/inquiries/{identifier}/reply"
    reply = {"answer": "処理は完了しています"}
    assert portal.put(path, headers=provider, json=reply).status_code == 403
    assert portal.put(path, headers=admin, json=reply).status_code == 200
    assert portal.get("/api/inquiries", headers=consumer).json()[0]["answer"] == reply["answer"]
