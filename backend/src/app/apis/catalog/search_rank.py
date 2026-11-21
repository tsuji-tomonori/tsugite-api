"""Hybrid ranking over the listings the caller is already allowed to discover."""

import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from app.db.models import Asset

# Each axis describes a business concept. OpenAPI tags extend these axes with
# domain-specific descriptions from the permitted catalog at query time.
CONCEPTS = (
    ("在庫", "棚卸", "引当", "残数", "ストック", "inventory", "stock", "sku"),
    ("配送", "配達", "荷物", "送り状", "宅配", "delivery", "shipping", "parcel", "parcels", "shipment"),
    ("為替", "両替", "通貨", "円換算", "外貨", "exchange", "currency", "forex"),
    ("店舗", "支店", "営業所", "store", "stores", "branch", "outlet"),
    ("発注", "注文", "購買", "仕入", "purchase", "procurement", "orders"),
    ("営業日", "稼働日", "休業日", "休日", "カレンダー", "calendar", "holiday", "workday"),
    ("請求", "売掛", "インボイス", "invoice", "billing", "receivable"),
    ("従業員", "社員", "人事", "employee", "personnel", "staff"),
    ("顧客", "得意先", "取引先", "customer", "client"),
)
WORDS = re.compile(r"[a-z0-9]+|[\u3040-\u30ff\u3400-\u9fff々ー]+|[^\W_]+", re.UNICODE)
JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff々ー]")
METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
STOP = {
    "api",
    "the",
    "of",
    "and",
    "する",
    "ます",
    "です",
    "から",
    "して",
    "にて",
    "一覧",
    "取得",
    "照会",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text).casefold().strip()


def terms(text: str) -> set[str]:
    result = set()
    for word in WORDS.findall(text):
        if JAPANESE.match(word) and len(word) > 1:
            result.update(word[i : i + 2] for i in range(len(word) - 1))
        else:
            result.add(word)
    return result - STOP


def contains(text: str, term: str) -> bool:
    if term.isascii() and term.isalnum():
        return bool(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text))
    return term in text


@dataclass
class Document:
    asset: Asset
    fields: tuple[str, ...]
    words: set[str]
    tags: set[str]
    tag_definitions: dict[str, str]


def document(asset: Asset) -> Document:
    spec = json.loads(asset.spec)
    ops = [spec["info"].get("title", ""), spec["info"].get("description", "")]
    definitions = {
        normalize(t["name"]): normalize(t.get("description", "")) for t in spec.get("tags", [])
    }
    tags = set()
    for path, item in spec.get("paths", {}).items():
        if not path.startswith("/"):
            continue
        ops.append(path)
        for method, op in item.items():
            if method not in METHODS:
                continue
            ops.extend(op.get(k, "") for k in ("summary", "description", "operationId"))
            tags.update(normalize(tag) for tag in op.get("tags", []))
    fields = tuple(
        normalize(field)
        for field in (asset.name, asset.summary, asset.owner, " ".join(ops + sorted(tags)))
    )
    return Document(asset, fields, terms(" ".join(fields)), tags, definitions)


def concept_vector(text: str) -> set[str]:
    return {
        f"concept:{i}"
        for i, aliases in enumerate(CONCEPTS)
        if any(contains(text, alias) for alias in aliases)
    }


def rank_assets(
    visible_assets: Iterable[Asset],
    query: str,
    mode: Literal["hybrid", "lexical", "semantic"] = "hybrid",
) -> list[Asset]:
    """Use term coverage and concept-vector cosine, combined with reciprocal rank fusion."""
    query = normalize(query)
    ordered = sorted(visible_assets, key=lambda a: (a.name, a.id))
    if not query or not ordered:
        return ordered
    docs = [document(a) for a in ordered]
    query_terms = terms(query)
    # Rare words carry more weight. Statistics and tag descriptions are gathered
    # only from records which survive visibility and environment filtering.
    frequency = Counter(word for d in docs for word in d.words & query_terms)
    weight = {word: 1 + math.log((len(docs) + 1) / (frequency[word] + 1)) for word in query_terms}
    total = math.fsum(weight.values())
    lexical = {}
    for d in docs:
        exact = max(
            (bonus for field, bonus in zip(d.fields, (4, 2, 1, 1)) if contains(field, query)), default=0
        )
        coverage = math.fsum(weight[w] for w in d.words & query_terms) / total if total else 0.0
        if exact or coverage >= 0.55:
            lexical[d.asset.id] = exact + coverage

    query_vector = concept_vector(query)
    for d in docs:
        for tag, definition in d.tag_definitions.items():
            if contains(query, tag) or contains(definition, query):
                query_vector.add("tag:" + tag)
        for tag in d.tags:
            if contains(query, tag):
                query_vector.add("tag:" + tag)
    semantic = {}
    if query_vector:
        for d in docs:
            vector = concept_vector(" ".join(d.fields)) | {"tag:" + tag for tag in d.tags}
            shared = query_vector & vector
            if shared:
                semantic[d.asset.id] = len(shared) / math.sqrt(len(vector) * len(query_vector))

    branches = {"lexical": (lexical,), "semantic": (semantic,), "hybrid": (lexical, semantic)}
    fused: dict[str, float] = defaultdict(float)
    for scores in branches[mode]:
        # Equal evidence receives equal rank, even when dozens of branch offices
        # share identical descriptions. The final name/ID order breaks ties.
        ranks = {score: i for i, score in enumerate(sorted(set(scores.values()), reverse=True), start=1)}
        for key, score in scores.items():
            fused[key] += 1 / (60 + ranks[score])
    return sorted((a for a in ordered if a.id in fused), key=lambda a: -fused[a.id])
