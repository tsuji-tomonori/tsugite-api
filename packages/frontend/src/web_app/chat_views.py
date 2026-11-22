"""The signed-in chat, sources and private inquiry controls."""

import asyncio
from urllib.parse import quote

import client
from js import document, window
from puepy import t

SUGGESTIONS = ("在庫を確認できるAPIを探して", "APIキーを発行する手順を教えて")
ENVIRONMENTS = {"sandbox": "検証", "staging": "準本番", "production": "本番"}


def uuid():
    return str(window.crypto.randomUUID())


async def wait_for_result(job_id):
    for attempt in range(35):
        if attempt:
            await asyncio.sleep(min(attempt, 5))
        answer = await client.api("/chat?job_id=" + quote(job_id, safe=""))
        if answer["kind"] != "pending":
            return answer
    return {"kind": "error", "answer": "回答に時間がかかっています。時間をおいて再度お試しください。"}


def refresh(render, path):
    if str(window.location.hash).lstrip("#/") in ("", path):
        render()
        history = document.getElementById("chat-history")
        if history:
            history.scrollTop = history.scrollHeight


def show_result(reply):
    t.p(reply["answer"], classes="chat-text")
    for product in reply.get("products", []):
        with t.article(classes="chat-source"):
            with t.h3():
                t.a(product["name"], href="#/api/" + quote(product["id"], safe=""))
            if product["summary"]:
                t.p(product["summary"])
            if product["environments"]:
                t.small("・".join(ENVIRONMENTS.get(env, env) for env in product["environments"]))
    for index, guide in enumerate(reply.get("guides", [])):
        with t.details(classes="chat-source", open=index == 0):
            t.summary(guide["title"])
            with t.ol():
                for step in guide["steps"]:
                    t.li(step)
            t.p(guide["result"])
            t.a("ガイドで確認", href="#/guide/" + quote(guide["id"], safe=""))


def home(ctx, render):
    state = ctx.setdefault("chat", {"turns": [], "busy": False, "contact": False})
    turns = state["turns"]

    async def ask(question):
        if len(question) < 2 or state["busy"]:
            return
        state["busy"] = True
        state["question_text"] = ""
        turn = {"question": question}
        turns.append(turn)
        del turns[:-12]
        refresh(render, "home")
        job_id = uuid()
        try:
            await client.api("/chat", "POST", {"job_id": job_id, "question": question})
            reply = await wait_for_result(job_id)
        except Exception as exc:
            client.report(exc, "ask", route="/api/chat")
            reply = {"kind": "error", "answer": str(exc)}
        if ctx.get("chat") is state:
            turn["reply"] = reply
            state["busy"] = False
            if reply["kind"] == "contact":
                state["contact"] = True
            refresh(render, "home")

    def submit(event):
        event.preventDefault()
        element = document.getElementById("chat-question")
        asyncio.ensure_future(ask(str(element.value).strip()))

    def remember_question(event):
        state["question_text"] = str(event.target.value)

    def remember_inquiry(event):
        state["contact_text"] = str(event.target.value)

    def suggestion(question):
        def submit_suggestion(event):
            asyncio.ensure_future(ask(question))

        return submit_suggestion

    def contact(event):
        state["contact"] = not state["contact"]
        refresh(render, "home")
        if state["contact"]:
            document.getElementById("inquiry-question").focus()

    async def send_inquiry(question):
        if len(question) < 2 or state.get("sending"):
            return
        if state.get("draft") != question:
            state.update(draft=question, inquiry_id=uuid())
        state["sending"] = True
        refresh(render, "home")
        try:
            record = await client.api(
                "/inquiries", "POST", {"inquiry_id": state["inquiry_id"], "question": question}
            )
        except Exception as exc:
            client.report(exc, "send_inquiry", route="/api/inquiries")
            state["inquiry_error"] = str(exc)
        else:
            state.update(contact=False, draft="", contact_text="", inquiry_id=None, inquiry_error="")
            turns.append(
                {
                    "question": question,
                    "reply": {
                        "kind": "receipt",
                        "answer": "問い合わせを受け付けました。受付番号 " + record["inquiry_id"],
                    },
                }
            )
            del turns[:-12]
        finally:
            state["sending"] = False
        if ctx.get("chat") is state:
            refresh(render, "home")

    def submit_inquiry(event):
        event.preventDefault()
        question = str(document.getElementById("inquiry-question").value).strip()
        asyncio.ensure_future(send_inquiry(question))

    with t.section(classes="chat box", aria_label="継手APIのチャット"):
        if not turns:
            with t.div(classes="chat-welcome"):
                t.h2("どのAPIをお探しですか？")
                t.p("利用目的からAPIを探したり、使い方ガイドの手順を確認したりできます。")
                with t.div(classes="chat-actions"):
                    for question in SUGGESTIONS:
                        t.button(
                            question,
                            type="button",
                            classes="btn btn-outline-secondary",
                            on_click=suggestion(question),
                        )
        with t.div(id="chat-history", classes="chat-history", role="log", aria_label="会話"):
            for turn in turns:
                with t.article(classes="chat-turn"):
                    with t.div(classes="chat-user"):
                        t.small("あなた")
                        t.p(turn["question"], classes="chat-text")
                    with t.div(classes="chat-agent"):
                        t.small("継手API")
                        if reply := turn.get("reply"):
                            show_result(reply)
                        else:
                            t.p("回答を準備しています…", role="status")
        with t.form(classes="chat-composer", on_submit=submit):
            with t.label(classes="field"):
                t.span("質問")
                t.input(
                    id="chat-question",
                    type="text",
                    required=True,
                    minlength=2,
                    maxlength=400,
                    disabled=state["busy"],
                    classes="form-control",
                    placeholder="利用目的や操作名を入力",
                    value=state.get("question_text", ""),
                    on_input=remember_question,
                )
            t.button("送信", type="submit", disabled=state["busy"], classes="btn btn-primary")
        with t.div(classes="chat-actions"):
            t.button(
                "運営に問い合わせる",
                type="button",
                classes="btn btn-outline-secondary",
                on_click=contact,
                aria_expanded="true" if state["contact"] else "false",
            )
            t.a("自分の問い合わせ", href="#/inquiries")
        if state["contact"]:
            with t.form(classes="chat-inquiry", on_submit=submit_inquiry):
                t.p("内容は運営担当者に送信されます。回答は［自分の問い合わせ］で確認できます。")
                if error := state.get("inquiry_error"):
                    t.p(error, role="alert")
                with t.label(classes="field"):
                    t.span("問い合わせ内容")
                    t.textarea(
                        state.get("contact_text", ""),
                        id="inquiry-question",
                        classes="form-control",
                        minlength=2,
                        maxlength=2000,
                        required=True,
                        disabled=state.get("sending", False),
                        on_input=remember_inquiry,
                    )
                t.button(
                    "問い合わせを送信",
                    type="submit",
                    classes="btn btn-primary",
                    disabled=state.get("sending", False),
                )


def inquiries(ctx, btn, reply, move):
    admin_view = ctx.get("inquiry_incoming", False)
    if ctx["me"]["admin"]:
        with t.div(classes="chat-actions"):
            btn("自分の問い合わせ", move, False, 0, primary=not admin_view)
            btn("運営への問い合わせ", move, True, 0, primary=admin_view)
    entries = ctx.get("inquiries", [])
    if not entries:
        t.p("問い合わせはありません。", classes="empty")
    for record in entries[:20]:
        key = record["inquiry_id"]
        with t.article(classes="box chat-ticket"):
            t.small("受付番号 " + key)
            t.p(record["question"], classes="chat-text")
            if record["answer"]:
                t.h3("運営からの回答")
                t.p(record["answer"], classes="chat-text")
            elif admin_view:
                with t.label(classes="field"):
                    t.span("回答")
                    t.textarea(id="reply-" + key, classes="form-control", minlength=2, maxlength=2000)
                btn("回答を送信", reply, key, primary=True)
            else:
                t.small("回答待ち", classes="muted")
    offset = ctx.get("inquiry_offset", 0)
    with t.div(classes="chat-actions"):
        if offset:
            btn("前へ", move, admin_view, max(0, offset - 20))
        if len(entries) > 20:
            btn("次へ", move, admin_view, offset + 20)
