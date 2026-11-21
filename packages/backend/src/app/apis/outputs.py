"""Response contracts for handlers that build JSON dictionaries directly."""

from datetime import datetime
from typing import Literal, NotRequired, TypedDict


class Health(TypedDict):
    status: str


class PortalConfig(TypedDict):
    demo: bool
    domain: str
    client_id: str


class DemoToken(TypedDict):
    access_token: str


class VisibleTarget(TypedDict):
    owner: str
    environment: str


class Profile(TypedDict):
    known_projects: list[str]
    personal_project: str
    leads: list[str]
    departments: list[str]
    titles: list[str]
    admin: bool
    subject: str
    projects: list[str]
    owners: list[str]
    auditor: bool
    targets: dict[str, VisibleTarget]


class Identifier(TypedDict):
    id: str


class Deleted(TypedDict):
    deleted: bool


class Removed(TypedDict):
    removed: bool


class Revoked(TypedDict):
    revoked: bool


class Read(TypedDict):
    read: bool


class Unread(TypedDict):
    unread: int


class Person(TypedDict):
    subject: str
    username: str


class Member(Person):
    role: str
    project: NotRequired[str]
    deleted: NotRequired[bool]


class MemberPage(TypedDict):
    items: list[Member]
    next: str
    projects: list[str]


class Unit(TypedDict):
    id: str
    kind: Literal["department", "project"]
    name: str
    parent: str
    stopped: bool


class Affiliation(Person):
    unit_id: str
    title: str
    leader: bool
    active: NotRequired[bool]


class Workspace(TypedDict):
    admin: bool
    units: list[Unit]
    leads: list[str]
    my_units: list[str]
    memberships: list[Affiliation]
    users: list[Person]
    titles: list[str]


class ByProject(TypedDict):
    project: str
    calls: int


class ByAPI(TypedDict):
    asset_id: str
    name: str
    calls: int


class Usage(TypedDict):
    unit_id: str
    members: list[Affiliation]
    calls: int
    errors: int
    by_project: list[ByProject]
    by_api: list[ByAPI]


class KeyMetadata(TypedDict):
    mode: Literal["legacy", "bearer", "app", "system"]
    ttl_minutes: NotRequired[int]
    refresh_minutes: NotRequired[int]
    operations: NotRequired[dict[str, list[str]]]
    users: NotRequired[list[str]]
    can_portal_exchange: NotRequired[bool]
    id: str
    name: str
    project: str
    kind: Literal["personal", "shared"]
    creator: str
    api_ids: list[str]
    revoked: bool


class IssuedKey(KeyMetadata):
    secret: str


class Notice(TypedDict):
    id: str
    title: str
    body: str
    project: str
    sender: str
    at: datetime
    unread: bool


class Inbox(Unread):
    items: list[Notice]


class AccessLog(TypedDict):
    at: datetime
    request_id: str
    actor: str
    key_id: str | None
    owner: str
    project: str
    asset_id: str
    environment: str
    method: str
    operation: str
    status: int
    duration_ms: int


class MetricPoint(TypedDict):
    at: datetime
    calls: int
    success: int
    errors: int
    denied: int
    max_ms: int
    avg_ms: float


class Metrics(TypedDict):
    start: datetime
    end: datetime
    minutes: int
    points: list[MetricPoint]


class Dashboard(Unread):
    published: int
    inventory: int
    pending: int
    approved: int
    calls: int
    errors: int


class Dimension(TypedDict):
    asset_id: str
    name: str
    project: str


class ManagementTarget(Dimension):
    id: str
    environment: str


class Token(TypedDict):
    access_token: str
    token_type: Literal["Bearer"]
    expires_in: int
    refresh_after: int
    expires_at: int
    refresh_at: int


class ClientCredential(TypedDict):
    client_id: str
    client_secret: str


class IssuedBearer(KeyMetadata, Token):
    pass


class IssuedClient(KeyMetadata, ClientCredential):
    pass


class OperationPolicy(TypedDict):
    operations: list[str]
    members: list[Person]
    permissions: dict[str, list[str]]


class Limit(TypedDict):
    inherited_minutes: int
    max_minutes: int | None


class CredentialAsset(TypedDict):
    id: str
    name: str
    operations: list[str]
    max_minutes: int


class UnitLimit(TypedDict):
    name: str
    minutes: int


class CredentialOptions(TypedDict):
    assets: list[CredentialAsset]
    members: list[Person]
    limits: list[UnitLimit]
    max_minutes: int
    may_manage: bool
