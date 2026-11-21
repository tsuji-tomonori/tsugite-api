"""Hybrid retrieval over portal text and a local vocabulary of task intents."""

import math
import re
import unicodedata
from collections import Counter

from guide_content import GUIDES, audiences


def normalize(text):
    return unicodedata.normalize("NFKC", text).casefold()


def words(text):
    terms = set()
    for chunk in re.findall(r"[a-z0-9]+|[ぁ-ヿ一-鿿々]+", normalize(text)):
        if chunk.isascii() or len(chunk) == 1:
            terms.add(chunk)
        else:
            terms.update(chunk[i : i + 2] for i in range(len(chunk) - 1))
    return terms


INDEX = {g.id: words(" ".join((g.title, g.prerequisite, *g.steps, g.result, g.caption))) for g in GUIDES}
FREQUENCY = Counter(term for terms in INDEX.values() for term in terms)
TITLE = {g.id: words(g.title) for g in GUIDES}
FILLER = re.compile(
    r"どうすればいい|どうしたらいい|どうやって|どうすれば|したいです|したい|したら|するには|の仕方|の方法|について|教えて|ください|ですか|ませんか|って何"
)

# Each axis represents a task. Phrases such as 夜間バッチ and 無人ジョブ
# share an axis even when they have no wording in common with the article.
# Keep separate phrase vectors so a long question can also match a partial paraphrase.
PHRASES = {g.id: [(normalize(p), words(p)) for p in g.intents] for g in GUIDES}


def intent_vector(query, terms):
    vector = {}
    for key, phrases in PHRASES.items():
        strength = 0
        for phrase, tokens in phrases:
            if phrase in query:
                strength = max(strength, 1 + min(8, len(phrase)) / 12)
            elif terms and tokens:
                shared = len(terms & tokens)
                similarity = shared / math.sqrt(len(terms) * len(tokens))
                if shared >= 2 and similarity >= 0.5:
                    strength = max(strength, similarity)
        if strength:
            vector[key] = strength
    norm = math.hypot(*vector.values())
    return {key: value / norm for key, value in vector.items()}


def search(query, role="すべて"):
    guides = [g for g in GUIDES if role == "すべて" or role in audiences(g)]
    query = normalize(query).strip()
    if not query:
        return guides
    terms = words(FILLER.sub(" ", query))
    semantic = intent_vector(query, terms)
    weights = {t: math.log(1 + (len(GUIDES) + 1) / (FREQUENCY[t] + 1)) for t in terms}
    weight = sum(weights.values())
    scores = {}
    for g in guides:
        lexical = 0
        if weight:
            coverage = sum(weights[t] for t in terms & INDEX[g.id]) / weight
            if coverage >= 0.29:
                title = sum(weights[t] for t in terms & TITLE[g.id]) / weight
                lexical = coverage * (1 + title)
        score = lexical + 2 * semantic.get(g.id, 0)
        if score:
            scores[g.id] = score
    return sorted((g for g in guides if g.id in scores), key=lambda g: -scores[g.id])
