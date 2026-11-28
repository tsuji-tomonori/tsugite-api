"""定期点検計画の商品別APIと見本データを定義する。"""

from fastapi import Query
from pydantic import BaseModel

from sample_api.database import MissingRecord, SampleDatabase


class ServicePlan(BaseModel):
    plan_id: str
    workshop: str
    part_number: str
    remaining_hours: int


class ServicePlanCount(BaseModel):
    workshop: str
    count: int


class ServicePlanRange(BaseModel):
    minimum_remaining_hours: int
    maximum_remaining_hours: int


db = SampleDatabase(
    "CREATE TABLE records (plan_id TEXT PRIMARY KEY, workshop TEXT NOT NULL, "
    "part_number TEXT NOT NULL, remaining_hours INTEGER NOT NULL)",
    [("M01", "整備一課", "BR-80", 12), ("M02", "整備二課", "VL-02", 220)],
)
app = db.app("定期点検計画", "設備の点検周期と次回交換までの残り運転時間を確認します。")


@app.get("/service-plans", summary="定期点検計画を一覧で取得")
def list_service_plans() -> list[ServicePlan]:
    return db.all("SELECT * FROM records ORDER BY plan_id")


@app.get(
    "/service-plans/{plan_id}",
    summary="定期点検計画の明細を照会",
    responses={404: {"model": MissingRecord, "description": "該当なし"}},
)
def detail(plan_id: str) -> ServicePlan:
    return db.one("SELECT * FROM records WHERE plan_id = ?", plan_id)


@app.get("/service-workshops", summary="定期点検計画を整備部署別に集計")
def by_workshop() -> list[ServicePlanCount]:
    return db.all("SELECT workshop, COUNT(*) AS count FROM records GROUP BY workshop ORDER BY workshop")


@app.get("/upcoming-services", summary="交換までの運転時間が指定値以下の定期点検計画を取得")
def below_limit(maximum: int = Query(12, description="交換までの運転時間の上限")) -> list[ServicePlan]:
    return db.all(
        "SELECT * FROM records WHERE remaining_hours <= ? ORDER BY remaining_hours, plan_id", maximum
    )


@app.get("/service-interval-range", summary="交換までの運転時間の最小値と最大値を取得")
def remaining_hours_summary() -> ServicePlanRange:
    return db.one(
        "SELECT MIN(remaining_hours) AS minimum_remaining_hours, "
        "MAX(remaining_hours) AS maximum_remaining_hours FROM records"
    )
