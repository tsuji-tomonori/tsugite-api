from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Env = Literal["sandbox", "staging", "production"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


FieldLabel = Annotated[str, Field(min_length=1, max_length=100)]
Answer = Annotated[str, Field(min_length=1, max_length=500)]
Route = Literal["legacy", "auto", "provider", "department", "department_provider", "custom"]


class ApplicationField(Input):
    label: FieldLabel
    required: bool = True
    allowed_values: list[Answer] = Field(default_factory=list, max_length=100)


class Offer(Input):
    instructions: str = Field("", max_length=4000)
    terms: str = Field("", max_length=8000)
    route: Route = "provider"
    steps: list[Annotated[str, Field(pattern=r"^(provider|department|unit/[a-z][a-z0-9-]{0,62})$")]] = (
        Field(default_factory=list[str], max_length=12)
    )
    fields: list[ApplicationField] = Field(default_factory=list[ApplicationField], max_length=20)

    @model_validator(mode="after")
    def unique_labels(self) -> Self:
        if (self.route == "custom") != bool(self.steps):
            raise ValueError("カスタム承認には承認者を1段階以上設定してください")
        if len({f.label for f in self.fields}) != len(self.fields):
            raise ValueError("申請項目の名前が重複しています")
        return self


class Register(Input):
    owner: str = Field(min_length=1, max_length=63)
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1000)
    targets: dict[Env, str] = Field(min_length=1, max_length=3)
    base_path: str = Field("", pattern=r"^(?:/[A-Za-z0-9_-]+)*$", max_length=300)
    spec: dict[str, Any]
    offers: dict[Env, Offer] | None = None
    release_note: str = Field("", max_length=2000)


class Listing(BaseModel):
    id: str
    name: str
    owner: str
    summary: str
    environments: list[Env]
    published: bool
    revision: int


class CatalogPage(BaseModel):
    items: list[Listing]
    page: int
    page_size: int
    total: int


class Detail(Listing):
    offers: dict[str, Any] = Field(default_factory=dict)
    releases: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])
    release_note: str = ""
    allowed_operations: list[str] | None = None
    base_path: str = ""
    bindings: dict[str, str] = Field(default_factory=dict)
    spec: dict[str, Any]


class Apply(Input):
    terms_accepted: bool = False
    offer_version: str = ""
    answers: dict[FieldLabel, Answer] = Field(default_factory=dict, max_length=20)
    personal: bool = False
    project: str = Field(pattern=r"^[a-z][a-z0-9-]{0,62}$")
    environment: Env
    reason: str = Field(min_length=1, max_length=1000)


class Decision(Input):
    action: Literal["approve", "reject", "revoke", "withdraw"]
    revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class Right(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    asset_id: str
    project: str
    environment: Env
    reason: str
    subject: str | None = None
    applicant: str | None = None
    asset_name: str = ""
    decision_reason: str | None = None
    application: dict[str, Any] = Field(default_factory=dict)
    stage: str | None = None
    status: Literal["pending", "approved", "rejected", "revoked", "withdrawn"]
    revision: int


class Audit(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    at: datetime
    actor: str
    project: str
    owner: str
    asset_id: str
    environment: str
    action: str
    detail: str
    request_id: str
