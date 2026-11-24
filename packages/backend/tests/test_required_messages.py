# 通知の個人別既読と問い合わせの受付・回答履歴を受信者の視点から検証する。
from uuid import UUID, uuid4

import pytest

from tests.support.catalog import headers


def test_independent_notification_counts(portal):
    """同じ所属先の二人が通知を受け、一人が複数回開いても既読件数は本人の一件分だけ変わる。"""
    admin = headers(portal, "admin")
    recipients = [headers(portal, persona) for persona in ("consumer", "provider")]
    project = "notice-team"
    created = portal.put(
        f"/api/workspace/units/{project}",
        headers=admin,
        json={"kind": "project", "name": "連絡用"},
    )
    assert created.status_code == 200
    for recipient in recipients:
        subject = portal.get("/api/me", headers=recipient).json()["subject"]
        added = portal.put(
            "/api/workspace/memberships",
            headers=admin,
            json={"subject": subject, "unit_id": project},
        )
        assert added.status_code == 200

    def unread(recipient):
        return portal.get("/api/notifications/count", headers=recipient).json()["unread"]

    before = [unread(recipient) for recipient in recipients]
    message = {"title": "稼働日の変更", "body": "来週は月曜日から利用できます。", "project": project}
    sent = portal.post("/api/notifications", headers=admin, json=message)
    assert sent.status_code == 201
    notice_id = sent.json()["id"]
    for index, recipient in enumerate(recipients):
        inbox = portal.get("/api/notifications", headers=recipient).json()
        assert inbox["unread"] == before[index] + 1
        notice = next(item for item in inbox["items"] if item["id"] == notice_id)
        assert notice["unread"] and all(notice[key] == value for key, value in message.items())
    for _ in range(2):
        read = portal.put(f"/api/notifications/{notice_id}/read", headers=recipients[0])
        assert read.status_code == 200 and read.json()["read"]
        assert unread(recipients[0]) == before[0]
        assert unread(recipients[1]) == before[1] + 1


@pytest.mark.parametrize(
    "question, answer",
    [
        pytest.param(
            "質問",
            "回答",
            id="minimum",
            marks=pytest.mark.case_detail("本文と回答が最短の二文字でも同じ受付に記録される"),
        ),
        pytest.param(
            "問" * 2000,
            "答" * 2000,
            id="maximum",
            marks=pytest.mark.case_detail("本文と回答が各二千文字でも全文を保持する"),
        ),
    ],
)
def test_retry_and_reply_in_inquiry_history(portal, question, answer):
    """問い合わせを同じ受付番号で再送すると一件だけ残り、運営の回答は本人の履歴に反映される。"""
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    inquiry_id = str(uuid4())
    submission = {"inquiry_id": inquiry_id, "question": question}
    receipts = []
    for _ in range(2):
        response = portal.post("/api/inquiries", headers=user, json=submission)
        assert response.status_code == 201
        record = response.json()
        receipts.append(record["inquiry_id"])
        assert UUID(record["inquiry_id"]) == UUID(inquiry_id) and record["question"] == question
        assert record["answer"] is None and record["answered_at"] is None
    assert receipts[0] == receipts[1]
    inbox = portal.get("/api/inquiries", headers=admin, params={"incoming": True})
    assert sum(record["inquiry_id"] == receipts[0] for record in inbox.json()) == 1
    reply = portal.put(f"/api/inquiries/{inquiry_id}/reply", headers=admin, json={"answer": answer})
    assert reply.status_code == 200
    assert reply.json()["answer"] == answer and reply.json()["answered_at"]
    history = portal.get("/api/inquiries", headers=user).json()
    matching = [record for record in history if record["inquiry_id"] == receipts[0]]
    assert len(matching) == 1
    assert matching[0]["question"] == question and matching[0]["answer"] == answer
    assert matching[0]["answered_at"]


def test_invalid_inquiry_does_not_consume_receipt(portal):
    """短すぎる問い合わせを訂正すると、元の受付番号で送信し直せる。"""
    user = headers(portal, "consumer")
    submission = {"inquiry_id": str(uuid4()), "question": "問"}
    invalid = portal.post("/api/inquiries", headers=user, json=submission)
    assert invalid.status_code == 422
    assert any(item["loc"][-1] == "question" for item in invalid.json()["detail"])
    submission["question"] = "申請方法を教えてください。"
    accepted = portal.post("/api/inquiries", headers=user, json=submission)
    assert accepted.status_code == 201 and UUID(accepted.json()["inquiry_id"]) == UUID(
        submission["inquiry_id"]
    )


def test_receipt_reuse_and_answer_retry(portal):
    """異なる質問を同じ受付番号に送っても元の質問を保持し、運営はその受付に回答できる。"""
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    submission = {"inquiry_id": str(uuid4()), "question": "申請した商品はいつ使えますか。"}
    accepted = portal.post("/api/inquiries", headers=user, json=submission)
    assert accepted.status_code == 201
    receipt = accepted.json()["inquiry_id"]
    conflict = portal.post(
        "/api/inquiries",
        headers=user,
        json={**submission, "question": "回答方法も教えてください。"},
    )
    assert conflict.status_code == 409 and conflict.json()["detail"]
    reply_url = f"/api/inquiries/{receipt}/reply"
    missing = portal.put(
        f"/api/inquiries/{uuid4()}/reply", headers=admin, json={"answer": "準備中です。"}
    )
    assert missing.status_code == 404 and missing.json()["detail"]
    response = portal.put(reply_url, headers=admin, json={"answer": "承認後に使用できます。"})
    assert response.status_code == 200 and response.json()["question"] == submission["question"]
    history = portal.get("/api/inquiries", headers=user, params={"offset": 1}).json()
    assert not any(item["inquiry_id"] == receipt for item in history)


def test_inquiry_history_separates_requesters(portal):
    """二人が別々に相談すると各自の履歴には本人の受付だけが載り、管理者は双方を確認できる。"""
    people = [headers(portal, role) for role in ("provider", "consumer")]
    admin = headers(portal, "admin")
    ids = []
    for actor, question in zip(
        people, ("公開日を教えてください。", "申請日を教えてください。"), strict=True
    ):
        response = portal.post(
            "/api/inquiries",
            headers=actor,
            json={"inquiry_id": str(uuid4()), "question": question},
        )
        assert response.status_code == 201
        ids.append(response.json()["inquiry_id"])
    for actor, receipt in zip(people, ids, strict=True):
        own = portal.get("/api/inquiries", headers=actor).json()
        assert [row["inquiry_id"] for row in own] == [receipt]
    incoming = portal.get("/api/inquiries", headers=admin, params={"incoming": True}).json()
    assert set(ids) == {row["inquiry_id"] for row in incoming}


def test_response_retry_after_an_inquiry_has_been_answered(portal):
    """受付の確認が回答後になった場合も、同じ本文の再送は既存の回答を保持する。"""
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    payload = {"inquiry_id": str(uuid4()), "question": "申請環境を変更できますか。"}
    submitted = portal.post("/api/inquiries", headers=user, json=payload)
    assert submitted.status_code == 201
    receipt = submitted.json()["inquiry_id"]
    answered = portal.put(
        f"/api/inquiries/{receipt}/reply", headers=admin, json={"answer": "環境別に申請してください。"}
    )
    assert answered.status_code == 200
    retried = portal.post("/api/inquiries", headers=user, json=payload)
    assert retried.status_code == 201 and retried.json()["inquiry_id"] == receipt
    assert (
        retried.json()["question"] == payload["question"]
        and retried.json()["answer"] == answered.json()["answer"]
    )
    own = portal.get("/api/inquiries", headers=user).json()
    assert [item["inquiry_id"] for item in own] == [receipt]


def test_blank_question_and_reply_leave_history_unchanged(portal):
    """空白だけの問い合わせ・回答は本文として受理せず、利用者が本文を書き直すまでは履歴を変えない。"""
    user = headers(portal, "consumer")
    admin = headers(portal, "admin")
    receipt = str(uuid4())
    submission = {"inquiry_id": receipt, "question": "  \n  "}
    blank = portal.post("/api/inquiries", headers=user, json=submission)
    assert blank.status_code == 422 and blank.json()["detail"]
    assert portal.get("/api/inquiries", headers=user).json() == []
    question = "納期を確認する方法はありますか。"
    valid = portal.post("/api/inquiries", headers=user, json={**submission, "question": question})
    assert valid.status_code == 201
    empty_reply = portal.put(f"/api/inquiries/{receipt}/reply", headers=admin, json={"answer": "  \n  "})
    assert empty_reply.status_code == 422 and empty_reply.json()["detail"]
    records = portal.get("/api/inquiries", headers=user).json()
    assert len(records) == 1 and records[0]["question"] == question and records[0]["answer"] is None
