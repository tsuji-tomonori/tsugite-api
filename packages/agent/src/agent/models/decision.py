"""Japanese topic and retrieval embeddings with a warm content cache."""

from collections import OrderedDict
from functools import cache

import numpy as np
import onnxruntime as ort
from runtime import logged_model, model_file
from tokenizers import Tokenizer


@cache
def load():
    options = ort.SessionOptions()
    options.inter_op_num_threads = 1
    options.intra_op_num_threads = 2
    session = ort.InferenceSession(
        model_file("decision", "model.onnx"), sess_options=options, providers=["CPUExecutionProvider"]
    )
    tokenizer = Tokenizer.from_file(model_file("decision", "tokenizer.json"))
    tokenizer.enable_truncation(max_length=192)
    tokenizer.enable_padding(pad_id=3, pad_token="[PAD]")
    return session, tokenizer


def encode(texts):
    session, tokenizer = load()
    content = tokenizer.encode_batch(texts)
    ids = np.array([item.ids for item in content], dtype=np.int64)
    mask = np.array([item.attention_mask for item in content], dtype=np.int64)
    available = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
    values = session.run(None, {item.name: available[item.name] for item in session.get_inputs()})[0]
    if not isinstance(values, np.ndarray):
        raise ValueError("Expected dense embedding output from the decision model")
    if values.ndim == 3:
        values = (values * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1, keepdims=True).clip(1)
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return (values / norms.clip(1e-12)).astype(np.float32)


vectors = OrderedDict()


def encode_cached(texts):
    missing = [text for text in dict.fromkeys(texts) if text not in vectors]
    if missing:
        vectors.update(zip(missing, encode(missing).tolist(), strict=True))
    result = []
    for text in texts:
        result.append(vectors[text])
        vectors.move_to_end(text)
    while len(vectors) > 512:
        vectors.popitem(last=False)
    return result


@logged_model
def handler(event, context):
    texts = event["texts"]
    if not 1 <= len(texts) <= 24 or any(not isinstance(text, str) or len(text) > 500 for text in texts):
        raise ValueError("Invalid embedding batch")
    return {"vectors": encode_cached(texts)}
