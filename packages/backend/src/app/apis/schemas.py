from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Env = Literal["sandbox", "production"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Register(Input):
    owner: str = Field(min_length=1, max_length=63)
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1000)
    targets: dict[Env, str] = Field(min_length=1, max_length=2)
    base_path: str = Field("", pattern=r"^(?:/[A-Za-z0-9_-]+)*$", max_length=300)
    spec: dict[str, Any]


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
    allowed_operations: list[str] | None = None
    base_path: str = ""
    bindings: dict[str, str] = Field(default_factory=dict)
    spec: dict[str, Any]


class Apply(Input):
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
