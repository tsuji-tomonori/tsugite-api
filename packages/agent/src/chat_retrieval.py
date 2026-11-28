"""質問に応じて検索ツールを選び、取得した根拠をモデルで評価する。"""

import math
import re
from collections import defaultdict
from dataclasses import dataclass

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


@dataclass
class Candidates:
    query: str
    raw: list[str]
    edited: list[str]
    documents: list[tuple[str, str]]
    direct: set[str]
    steps: dict[str, tuple[str, list[str]]]


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
    ordered = sorted(explicit, key=lambda key: (-scores.get(key, -1), not explicit[key], key))
    plausible = [
        key for key in ordered if explicit[key] or scores.get(key, -1) >= max(0.43, outside + 0.055)
    ]
    if outside >= 0.50 and outside >= max(scores.get(key, -1) for key in explicit) + 0.10:
        return []
    return plausible


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


def decide(question, search, models):
    if OVERRIDE.search(question):
        return {"kind": "outside"}
    if CONTACT.search(question) and not MANUAL.search(question):
        return {"kind": "contact"}
    allowed = routes(question, models)
    if allowed is None:
        # 判定モデルが利用できない場合も、明示された検索先で出典を照合する。
        allowed = (
            ["manual"] if MANUAL.search(question) else ["catalog"] if CATALOG.search(question) else []
        )
    if not allowed:
        return {"kind": "outside"}
    plan = models("tool", {"question": question, "allowed": allowed})
    tool = plan.get("action")
    if tool not in allowed:
        tool = allowed[0]
    kinds = [tool, *(kind for kind in allowed if kind != tool)]
    for kind in kinds:
        found = search(kind, plan.get("query"))
        raw_semantic, edited_semantic = (
            semantic(question, found.query, found.documents[:240], models)
            if found.documents
            else ([], [])
        )
        grounded = found.direct | ((set(found.edited) - set(found.raw)) & set(raw_semantic))
        ranked = fuse(found.raw, raw_semantic, found.edited, edited_semantic)
        keys = [key for key in ranked if key in grounded][:3]
        if not keys:
            continue
        if kind == "catalog":
            return {"kind": kind, "keys": keys}
        evidence = [found.steps[key] for key in keys]
        generated = models(
            "generate", {"question": question, "evidence": evidence, "headings": ["手順"]}
        )
        index = generated.get("source")
        index = index if type(index) is int and 0 <= index < len(keys) else 0
        key = keys[index]
        step = generated.get("step")
        return {
            "kind": kind,
            "keys": [key, *(item for item in keys if item != key)],
            "focus": [key, step if type(step) is int else 0],
        }
    return {"kind": "empty"}
