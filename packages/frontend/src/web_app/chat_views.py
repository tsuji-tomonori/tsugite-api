"""The signed-in chat, sources and private inquiry controls."""

import asyncio
from urllib.parse import quote

import client
from access_log_display import LOG_QUESTIONS, answer_log_question
from inquiry_form import inquiry_form, post_inquiry
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


def home(ctx, render, *, log=None, path="home", inquiry_only=False):
    state_key = "log_chat" if log else "chat"
    key = log["request_id"] if log else None
    if ctx.get(state_key, {}).get("request_id") != key:
        ctx.pop(state_key, None)
    state = ctx.setdefault(state_key, {"turns": [], "busy": False, "contact": False, "request_id": key})
    prefix = f"リクエストID　{key}\n" if log else ""
    turns = state["turns"]

    async def ask(question):
        if len(question) < 2 or state["busy"]:
            return
        state["busy"] = True
        state["question_text"] = ""
        turn = {"question": question}
        turns.append(turn)
        del turns[:-12]
        refresh(render, path)
        try:
            if log:
                reply = {"kind": "log", "answer": answer_log_question(log, question)}
            else:
                job_id = uuid()
                await client.api("/chat", "POST", {"job_id": job_id, "question": question})
                reply = await wait_for_result(job_id)
        except Exception as exc:
            client.report(exc, "ask", route="/api/chat")
            reply = {"kind": "error", "answer": str(exc)}
        if ctx.get(state_key) is state:
            turn["reply"] = reply
            state["busy"] = False
            if reply["kind"] == "contact":
                state["contact"] = True
            refresh(render, path)

    def submit(event):
        event.preventDefault()
        element = document.getElementById("chat-question")
        asyncio.ensure_future(ask(str(element.value).strip()))

    def remember_question(event):
        state["question_text"] = str(event.target.value)

    def suggestion(question):
        def submit_suggestion(event):
            asyncio.ensure_future(ask(question))

        return submit_suggestion

    def contact(event):
        state["contact"] = not state["contact"]
        refresh(render, path)
        if state["contact"]:
            document.getElementById("inquiry-question").focus()

    async def send_inquiry(question):
        if state.get("sending"):
            return
        state["sending"] = True
        refresh(render, path)
        try:
            receipt = await post_inquiry(state, prefix + question)
        except Exception as exc:
            client.report(exc, "send_inquiry", route="/api/inquiries")
            state["inquiry_error"] = str(exc)
        else:
            state.update(contact=False, receipt=receipt)
            turns.append(
                {
                    "question": question,
                    "reply": {
                        "kind": "receipt",
                        "answer": "問い合わせを受け付けました。受付番号 " + receipt,
                    },
                }
            )
            del turns[:-12]
        finally:
            state["sending"] = False
        if ctx.get(state_key) is state:
            refresh(render, path)

    def submit_inquiry(event):
        event.preventDefault()
        question = str(document.getElementById("inquiry-question").value).strip()
        asyncio.ensure_future(send_inquiry(question))

    if inquiry_only:
        with t.section(classes="box"):
            t.h2("この呼び出しについて問い合わせる")
            t.p(prefix, classes="mono")
            if receipt := state.get("receipt"):
                t.p("受付番号 " + receipt, role="status")
                t.a("自分の問い合わせ", href="#/inquiries")
            inquiry_form(state, submit_inquiry, max_length=2000 - len(prefix))
        return

    with t.section(classes="chat box", aria_label="継手APIのチャット"):
        if log:
            t.h2("この呼び出しについて質問する")
            t.p(prefix, classes="mono")
        if not turns:
            with t.div(classes="chat-welcome"):
                if not log:
                    t.h2("どのAPIをお探しですか？")
                    t.p("利用目的からAPIを探したり、使い方ガイドの手順を確認したりできます。")
                with t.div(classes="chat-actions"):
                    for question in LOG_QUESTIONS if log else SUGGESTIONS:
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
                    placeholder="この呼び出しについて質問を入力" if log else "利用目的や操作名を入力",
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
            inquiry_form(state, submit_inquiry, max_length=2000 - len(prefix))
