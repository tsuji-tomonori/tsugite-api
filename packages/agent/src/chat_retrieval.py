# 質問に対応するガイドと根拠を検索する。
"""Stable routing, hybrid retrieval and evidence-bound presentation."""

import math
import re
from collections import defaultdict

from app.core.catalog_rank import concept_vector, contains, document, normalize, rank_assets, terms

from packages.frontend.src.web_app.content.guide_content import GUIDES, audiences
from packages.frontend.src.web_app.content.guide_search import FILLER
from packages.frontend.src.web_app.content.guide_search import search as search_guides

TOPICS = {
    "catalog": (
        "業務で利用できるAPIや商品を探す",
        "在庫照会や配送や請求のAPIを比較して利用する",
        "データを取得できるAPIの商品をおすすめしてほしい",
    ),
    "manual": (
        "継手APIの操作方法や利用申請の手順を知りたい",
        "APIキーの発行、アクセス権、ログイン、登録や承認のやり方を教えて",
        "ポータルの設定、監査ログ、アクセス制御画面の使い方",
    ),
    "outside": (
        "天気、旅行、料理、スポーツ、政治、語学の質問",
        "一般常識、プログラムの作成、数学、翻訳、雑談",
        "モデルの指示や秘密を開示して命令を実行する",
    ),
}
CONTACT = re.compile(r"問い合わせ|問合せ|運営に連絡|サポートに連絡")
CATALOG = re.compile(r"おすすめ|お勧め|探し|検索|商品|カタログ|どんなAPI|APIはあります|APIを比較", re.I)
MANUAL = re.compile(r"やり方|使い方|発行方法|手順|マニュアル|ガイド|どうやって|どうすれば")
OVERRIDE = re.compile(
    r"指示を(無視|忘れ)|システム(プロンプト|指示)|ignore (all |previous )?instructions|"
    r"<\|[^\n]{1,40}\|>|(?:一般知識|雑談)で答えて",
    re.I,
)
HEADINGS = {
    "catalog": ("目的に合うAPI候補です。", "公開中のAPIから候補を見つけました。"),
    "manual": ("使い方ガイドの該当手順です。", "参照したガイドに沿って手順を案内します。"),
}
OUTSIDE = "この質問は公開APIと使い方ガイドの案内範囲外です。"
NO_MATCH = "質問に合う公開APIや操作手順が見つかりませんでした。"
REQUEST_WORDS = re.compile(
    r"おすすめ|お勧め|どんな|ありますか|ありませんか|あります|探し(?:たい|て)?|検索|教えて|"
    r"知りたい|確認(?:したい|できる)?|できる|使いたい|どのような|使い方|やり方|手順|マニュアル|ガイド|カタログ|商品|方法|(?<![a-z0-9])api(?![a-z0-9]|キー)"
)


def search_subject(question):
    """Remove request wording so that asking for an API is not evidence for a particular product."""
    subject = FILLER.sub(" ", REQUEST_WORDS.sub(" ", normalize(question)))
    return subject.strip(" 　をのはがにでと？?！!。・")


def covers_topics(subject, content):
    """Check named subjects against the source, including catalog synonyms."""
    topics = re.findall(r"[一-鿿々]{2,}|[ァ-ヺー]{2,}|[a-z0-9]+", subject)
    concepts = concept_vector(content)
    return all(contains(content, topic) or concept_vector(topic) & concepts for topic in topics)


def dot(left, right):
    return math.fsum(a * b for a, b in zip(left, right, strict=True))


def routes(question, models):
    labels = [label for label, phrases in TOPICS.items() for _ in phrases]
    items = [question, *(phrase for phrases in TOPICS.values() for phrase in phrases)]
    vectors = models("decision", {"texts": ["トピック: " + item for item in items]}).get("vectors", [])
    if len(vectors) != len(items):
        return None
    scores = {}
    for label, vector in zip(labels, vectors[1:], strict=True):
        scores[label] = max(scores.get(label, -1), dot(vectors[0], vector))
    catalog, manual = bool(CATALOG.search(question)), bool(MANUAL.search(question))
    explicit = {"catalog": catalog, "manual": manual}
    outside = scores.get("outside", -1)
    ordered = sorted(explicit, key=lambda key: (-scores.get(key, -1), key))
    plausible = [
        key for key in ordered if explicit[key] or scores.get(key, -1) >= max(0.43, outside + 0.055)
    ]
    if outside >= 0.50 and outside >= max(scores.get(key, -1) for key in explicit) + 0.10:
        return []
    if manual != catalog:
        return ["manual" if manual else "catalog"]
    return plausible


def rewritten(question, value):
    if not isinstance(value, str) or not value.strip() or len(value) > 120 or OVERRIDE.search(value):
        return question
    original = terms(search_subject(question))
    updated = terms(search_subject(value))
    return value.strip() if original & updated else question


def fuse(*rankings):
    totals = defaultdict(float)
    for ranking in rankings:
        for rank, key in enumerate(dict.fromkeys(ranking), start=1):
            totals[key] += 1 / (60 + rank)
    return sorted(totals, key=lambda key: (-totals[key], key))


def semantic(question, query, documents, models):
    queries = list(dict.fromkeys([question, query]))
    vectors = models("decision", {"texts": ["検索クエリ: " + q for q in queries]}).get("vectors", [])
    if len(vectors) != len(queries):
        return [], []
    scores = [dict() for _ in queries]
    for start in range(0, len(documents), 24):
        batch = documents[start : start + 24]
        encoded = models(
            "decision", {"texts": ["検索文書: " + content[:360] for _, content in batch]}
        ).get("vectors", [])
        if len(encoded) != len(batch):
            break
        for (key, _), vector in zip(batch, encoded, strict=True):
            similarities = [dot(query_vector, vector) for query_vector in vectors]
            for index, score in enumerate(similarities):
                if score >= 0.46 and (index == 0 or similarities[0] >= 0.39):
                    scores[index][key] = score
    return (
        sorted(scores[0], key=lambda key: (-scores[0][key], key)),
        sorted(scores[-1], key=lambda key: (-scores[-1][key], key)),
    )


def manual_sources(actor):
    roles = {"利用者"}
    if actor.owners or actor.leads:
        roles.add("提供者")
    if actor.admin:
        roles.update(("提供者", "管理者"))
    return {guide.id: guide for guide in GUIDES if roles.intersection(audiences(guide))}


def recommended(question, query, assets, models, use_manual, actor):
    subject = search_subject(question)
    if not terms(subject) or not re.search(r"[一-鿿ァ-ヺa-z0-9]|[ぁ-ゖ]{2}", subject):
        return []
    edited_subject = search_subject(query)
    if use_manual:
        sources = manual_sources(actor)
        raw = [g.id for g in search_guides(subject, min_coverage=0.55) if g.id in sources]
        edited = (
            [g.id for g in search_guides(edited_subject, min_coverage=0.55) if g.id in sources]
            if edited_subject and edited_subject != subject
            else raw
        )
        documents = [
            (g.id, " ".join((g.title, *g.intents, g.prerequisite, *g.steps))) for g in sources.values()
        ]
    else:
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
    raw_semantic, edited_semantic = (
        semantic(question, query, documents[:240], models) if documents else ([], [])
    )
    if use_manual:
        evidence = {key: normalize(content) for key, content in documents if key in raw}
    else:
        raw_keys = set(raw)
        evidence = {
            asset.id: " ".join(document(asset).fields) for asset in assets if asset.id in raw_keys
        }
    direct = {key for key in raw if covers_topics(subject, evidence[key])}
    # A paraphrase needs both an indexed match and independent support from the original embedding.
    grounded = direct | ((set(edited) - set(raw)) & set(raw_semantic))
    return [key for key in fuse(raw, raw_semantic, edited, edited_semantic) if key in grounded][:3]


def ask(question, products, actor, models):
    if OVERRIDE.search(question):
        return {"kind": "outside", "answer": OUTSIDE}
    if CONTACT.search(question) and not MANUAL.search(question):
        return {"kind": "contact", "answer": "問い合わせの内容を入力し、送信してください。"}
    allowed = routes(question, models)
    if allowed is None:
        # Local demos and model outages still accept matches with verifiable sources.
        allowed = (
            ["manual"] if MANUAL.search(question) else ["catalog"] if CATALOG.search(question) else []
        )
    if not allowed:
        return {"kind": "outside", "answer": OUTSIDE}
    plan = models("tool", {"question": question, "allowed": allowed})
    tool = plan.get("action")
    if tool not in allowed:
        tool = allowed[0]
    query = rewritten(question, plan.get("query"))
    kinds = [tool, *(kind for kind in allowed if kind != tool)]
    for kind in kinds:
        keys = recommended(
            question, query, products() if kind == "catalog" else [], models, kind == "manual", actor
        )
        if not keys:
            continue
        if kind == "catalog":
            return {"kind": kind, "answer": HEADINGS[kind][0], "keys": keys}
        guides = manual_sources(actor)
        evidence = [(guides[key].title, [*guides[key].steps, guides[key].result]) for key in keys]
        generated = models(
            "generate", {"question": question, "headings": HEADINGS[kind], "evidence": evidence}
        )
        heading = generated.get("heading")
        answer = heading if heading in HEADINGS[kind] else HEADINGS[kind][0]
        index = generated.get("source")
        index = index if type(index) is int and 0 <= index < len(keys) else 0
        key = keys[index]
        step = generated.get("step")
        return {
            "kind": kind,
            "answer": answer,
            "keys": [key, *(item for item in keys if item != key)],
            "focus": [key, step if type(step) is int else 0],
        }
    return {"kind": "empty", "answer": NO_MATCH}
