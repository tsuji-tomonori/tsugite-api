"""OpenAPI shapes for product details serialized as flexible JSON, including older grants."""

from typing import NotRequired, TypedDict

from pydantic import TypeAdapter


class PublishedQuestion(TypedDict):
    label: str
    required: bool
    allowed_values: NotRequired[list[str]]


class PublishedOffer(TypedDict, total=False):
    instructions: str
    terms: str
    route: str
    steps: list[str]
    fields: list[PublishedQuestion]
    version: str


class ReleaseEntry(TypedDict):
    number: int
    published_at: str
    api_version: str
    openapi: str
    note: str
    added: list[str]
    removed: list[str]
    changed: list[str]


class ReviewStep(TypedDict):
    at: str
    stage: str
    actor: str
    reason: str
    action: str


class ApplicationEvidence(TypedDict, total=False):
    route: str
    steps: list[str]
    decisions: list[ReviewStep]
    departments: list[str]
    terms: str
    submitted_at: str
    terms_accepted: bool
    version: str
    answers: dict[str, str]


def describe_product_fields(schemas):
    for model, key, adapter in (
        ("Detail", "offers", TypeAdapter(dict[str, PublishedOffer])),
        ("Detail", "releases", TypeAdapter(list[ReleaseEntry])),
        ("Right", "application", TypeAdapter(ApplicationEvidence)),
    ):
        if model in schemas:
            shape = adapter.json_schema(ref_template="#/components/schemas/{model}")
            schemas.update(shape.pop("$defs", {}))
            # A standalone TypedDict is inlined by Pydantic.
            if shape.get("title") == "ApplicationEvidence":
                schemas["ApplicationEvidence"] = shape
                shape = {"$ref": "#/components/schemas/ApplicationEvidence"}
            schemas[model]["properties"][key].update(shape)
