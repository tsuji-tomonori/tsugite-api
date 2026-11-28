"""サンプル商品のLambdaハンドラーをテストするたびに、実行環境のイベントループを整える。"""

import asyncio

import pytest


@pytest.fixture
def lambda_event_loop():
    try:
        current = asyncio.get_event_loop()
    except RuntimeError:
        current = None
    if current is not None and not current.is_closed():
        yield
        return
    with asyncio.Runner() as runner:
        runner.get_loop()
        yield
