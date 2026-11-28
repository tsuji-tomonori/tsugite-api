"""閲覧できる商品とガイドからチャットの検索候補と根拠を取得する。"""

import re

from app.core.catalog_rank import concept_vector, contains, document, normalize, rank_assets, terms
from chat_retrieval import OVERRIDE, Candidates, decide, fuse

from packages.frontend.src.web_app.content.guide_content import GUIDES, audiences
from packages.frontend.src.web_app.content.guide_search import FILLER
from packages.frontend.src.web_app.content.guide_search import search as search_guides

NO_MATCH = "質問に合う公開APIや操作手順が見つかりませんでした。"
REQUEST_WORDS = re.compile(
    r"おすすめ|お勧め|どんな|ありますか|ありませんか|あります|探し(?:たい|て)?|検索|教えて|"
    r"知りたい|確認(?:したい|できる)?|できる|使いたい|どのような|使い方|やり方|手順|マニュアル|ガイド|カタログ|商品|方法|(?<![a-z0-9])api(?![a-z0-9]|キー)"
)


def search_subject(question):
    """依頼表現を除き、商品や操作を表す語を取り出す。"""
    subject = FILLER.sub(" ", REQUEST_WORDS.sub(" ", normalize(question)))
    return subject.strip(" 　をのはがにでと？?！!。・")


def covers_topics(subject, content):
    """質問に含まれる各用語を同義語も含めて出典と照合する。"""
    topics = re.findall(r"[一-鿿々]{2,}|[ァ-ヺー]{2,}|[a-z0-9]+", subject)
    concepts = concept_vector(content)
    return all(contains(content, topic) or concept_vector(topic) & concepts for topic in topics)


def rewritten(question, value):
    if not isinstance(value, str) or not value.strip() or len(value) > 120 or OVERRIDE.search(value):
        return question
    original = terms(search_subject(question))
    updated = terms(search_subject(value))
    return value.strip() if original & updated else question


def manual_sources(actor):
    roles = {"利用者"}
    if actor.owners or actor.leads:
        roles.add("提供者")
    if actor.admin:
        roles.update(("提供者", "管理者"))
    return {guide.id: guide for guide in GUIDES if roles.intersection(audiences(guide))}


def candidates(question, proposed, kind, products, actor):
    query = rewritten(question, proposed)
    use_manual = kind == "manual"
    subject = search_subject(question)
    if not terms(subject) or not re.search(r"[一-鿿ァ-ヺa-z0-9]|[ぁ-ゖ]{2}", subject):
        return Candidates(query, [], [], [], set(), {})
    edited_subject = search_subject(query)
    sources = manual_sources(actor) if use_manual else {}
    if use_manual:
        raw = [g.id for g in search_guides(subject, min_coverage=0.55) if g.id in sources]
        edited = (
            [g.id for g in search_guides(edited_subject, min_coverage=0.55) if g.id in sources]
            if edited_subject and edited_subject != subject
            else raw
        )
        documents = [
            (g.id, " ".join((g.title, *g.intents, g.prerequisite, *g.steps))) for g in sources.values()
        ]
        evidence = {key: normalize(content) for key, content in documents if key in raw}
    else:
        assets = products()
        raw = [asset.id for asset in rank_assets(assets, subject)]
        edited = (
            [asset.id for asset in rank_assets(assets, edited_subject)]
            if edited_subject and edited_subject != subject
            else raw
        )
        source_order = fuse(raw, edited)
        order = {key: index for index, key in enumerate(source_order)}
        documents = [
            (asset.id, f"{asset.name} {asset.summary}")
            for asset in sorted(assets, key=lambda a: (order.get(a.id, len(order)), a.id))
        ]
        raw_keys = set(raw)
        evidence = {
            asset.id: " ".join(document(asset).fields) for asset in assets if asset.id in raw_keys
        }
    direct = {key for key in raw if covers_topics(subject, evidence[key])}
    steps = {key: (g.title, [*g.steps, g.result]) for key, g in sources.items()}
    return Candidates(query, raw, edited, documents, direct, steps)


ANSWERS = {
    "outside": "この質問は公開APIと使い方ガイドの案内範囲外です。",
    "contact": "問い合わせの内容を入力し、送信してください。",
    "catalog": "目的に合うAPI候補です。",
    "manual": "使い方ガイドの該当手順です。",
    "empty": NO_MATCH,
}


def ask(question, products, actor, models):
    def search(kind, proposed):
        return candidates(question, proposed, kind, products, actor)

    result = decide(question, search, models)
    return {**result, "answer": ANSWERS[result["kind"]]}
