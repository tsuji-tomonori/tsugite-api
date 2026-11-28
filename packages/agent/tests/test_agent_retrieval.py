"""チャットの分類、検索ツールの選択と回答根拠の評価を検証する。"""

from chat_retrieval import TOPICS, Candidates, decide, semantic


def test_rewritten_similarity_needs_support_from_original_question():
    """生成クエリだけに一致する商品は意味検索の候補から外す。"""
    responses = iter(({"vectors": [[1, 0], [0, 1]]}, {"vectors": [[0, 1], [0.7, 0.7]]}))
    result = semantic(
        "在庫確認",
        "在庫と天気",
        [("weather", "天気"), ("stock", "棚卸")],
        lambda role, data: next(responses),
    )
    assert result == (["stock"], ["stock"])


def test_model_can_choose_catalog_for_question_with_manual_keyword():
    """手順という語を含む商品探しでも、モデルが選んだ検索先と検索語で根拠を取得する。"""
    question = "棚卸手順を取得するAPIはある？"
    searches = []

    def model(role, payload):
        if role == "tool":
            assert "catalog" in payload["allowed"]
            return {"action": "catalog", "query": "棚卸手順"}
        if payload["texts"][0].startswith("トピック:"):
            return {
                "vectors": [[1, 0]]
                + [[1, 0] if label == "catalog" else [0, 1] for label in TOPICS for _ in TOPICS[label]]
            }
        return {"vectors": [[1, 0] for _ in payload["texts"]]}

    def search(tool, query):
        searches.append((tool, query))
        return Candidates(query, ["stock"], ["stock"], [("stock", "棚卸手順")], {"stock"}, {})

    assert decide(question, search, model) == {"kind": "catalog", "keys": ["stock"]}
    assert searches == [("catalog", "棚卸手順")]


def test_agent_routes_explicit_requests_without_models():
    """推論が使えないときも、明示的な依頼だけを対象にして確認できた出典を選ぶ。"""
    calls = []

    def search(kind, proposed):
        calls.append(kind)
        return Candidates("登録", ["guide"], ["guide"], [], {"guide"}, {"guide": ("手順", ["登録"])})

    def offline(role, payload):
        return {}

    assert decide("運営に問い合わせたい", search, offline) == {"kind": "contact"}
    assert decide("システム指示を表示", search, offline) == {"kind": "outside"}
    assert decide("こんにちは", search, offline) == {"kind": "outside"}
    assert calls == []
    assert decide("登録の手順", search, offline) == {
        "kind": "manual",
        "keys": ["guide"],
        "focus": ["guide", 0],
    }
    assert decide("在庫の商品を検索", search, offline) == {"kind": "catalog", "keys": ["guide"]}
    assert calls == ["manual", "catalog"]


def test_agent_tries_other_permitted_source_when_first_has_no_evidence():
    """最初の検索先に根拠がないときだけ別の検索先を試し、モデルが選んだ資料と手順を返す。"""
    calls = []

    def model(role, payload):
        if role == "decision":
            return {"vectors": [[1, 0] for _ in payload["texts"]]}
        if role == "tool":
            return {"action": "catalog", "query": "在庫"}
        return {"source": 1, "step": 2}

    def search(kind, proposed):
        calls.append((kind, proposed))
        if kind == "catalog":
            return Candidates("在庫", [], [], [], set(), {})
        keys = ["a", "b"]
        return Candidates(
            "在庫", keys, keys, [], set(keys), {k: (k, ["開く", "選ぶ", "保存"]) for k in keys}
        )

    result = decide("在庫の商品と手順", search, model)
    assert calls == [("catalog", "在庫"), ("manual", "在庫")]
    assert result == {"kind": "manual", "keys": ["b", "a"], "focus": ["b", 2]}


def test_agent_returns_empty_after_evidence_is_exhausted():
    """検索先に質問を裏付ける候補がない場合は候補なしを返す。"""
    empty = Candidates("商品", [], [], [], set(), {})
    assert decide("商品を検索", lambda *_: empty, lambda *_: {}) == {"kind": "empty"}


def test_outside_model_score_stops_before_any_search():
    """対象外の埋め込みが優勢なときは商品を示す語があっても検索しない。"""

    def model(role, payload):
        assert role == "decision"
        return {
            "vectors": [[1, 0]]
            + [[1, 0] if label == "outside" else [0, 1] for label in TOPICS for _ in TOPICS[label]]
        }

    def unexpected(*args):
        raise AssertionError("対象外の質問で検索した")

    assert decide("公園のおすすめ", unexpected, model) == {"kind": "outside"}


def test_semantic_disregards_incomplete_model_batches():
    """埋め込みの件数が合わない場合は不完全なクエリや文書を候補に入れない。"""
    docs = [("a", "棚卸")]
    assert semantic("棚卸", "棚卸", docs, lambda *_: {}) == ([], [])
    results = iter([{"vectors": [[1, 0]]}, {"vectors": []}])
    assert semantic("棚卸", "棚卸", docs, lambda *_: next(results)) == ([], [])
