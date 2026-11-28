"""集計期間の選択肢と、日付を直接入力できる月間カレンダーを表示する。"""

from __future__ import annotations

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from functools import partial
from typing import Any

from js import document
from puepy import t
from puepy.core import Component

PERIODS = {"1": "過去1時間", "24": "過去24時間", "168": "過去7日", "720": "過去30日"}


@t.component()
class PeriodCalendar(Component):
    props = ["prefix", "label", "selected"]
    prefix: str
    label: str
    selected: str

    def initial(self) -> dict[str, str]:
        """選択済みの日付から表示月を決める。"""
        return {"month": self.selected[:7], "day": self.selected}

    def _move(self, offset: int, event: Any) -> None:
        month = date.fromisoformat(self.state["month"] + "-01")
        adjacent = month + timedelta(days=32 if offset > 0 else -1)
        self.state["month"] = adjacent.isoformat()[:7]

    def _select(self, day: str) -> None:
        document.getElementById(self.prefix + "-date").value = day
        self.state["day"] = day
        if day:
            self.state["month"] = day[:7]

    def _pick_day(self, event: Any) -> None:
        day = event.target.getAttribute("data-date")
        if day:
            self._select(str(day))

    def populate(self) -> None:
        """前後の月に移動できる日付一覧と、選択日を編集する入力欄を描画する。"""
        month = date.fromisoformat(self.state["month"] + "-01")
        weekday, days = monthrange(month.year, month.month)

        def month_button(label: str, offset: int, disabled: bool) -> None:
            t.button(
                label,
                type="button",
                aria_label=self.label + "の" + label,
                on_click=partial(self._move, offset),
                disabled=disabled,
            )

        with t.div(classes="calendar-heading"):
            month_button("前月", -1, month == date.min)
            t.strong(f"{month.year}年{month.month}月", aria_live="polite")
            month_button("翌月", 1, month == date.max.replace(day=1))
        with t.div(classes="calendar-days", on_click=self._pick_day):
            for heading in "月火水木金土日":
                t.small(heading)
            for _ in range(weekday):
                t.span()
            for number in range(1, days + 1):
                day = month.replace(day=number).isoformat()
                t.button(
                    str(number),
                    type="button",
                    aria_label=f"{self.label} {day}",
                    aria_pressed=str(day == self.state["day"]).lower(),
                    data_date=day,
                )
        with t.label(classes="field"):
            t.span(self.label + "日")
            t.input(
                type="date",
                id=self.prefix + "-date",
                value=self.state["day"],
                required=True,
                classes="form-control",
                max="9999-12-31",
                on_change=lambda event: (
                    self._select(str(event.target.value))
                    if not event.target.validity.rangeOverflow
                    else None
                ),
            )


def _switch_period(event: Any) -> None:
    panel = event.target.form.querySelector(".absolute-period")
    panel.hidden = panel.disabled = event.target.value != "custom"


def period_choice(filters: dict[str, str]) -> None:
    """相対期間と日時指定を一つの選択欄で切り替える。"""
    selected = "custom" if filters["start"] or filters["end"] else filters["hours"]
    with t.label(classes="field"):
        t.span("期間", id="f-hours-label")
        with t.select(
            id="f-hours",
            aria_labelledby="f-hours-label",
            classes="form-select",
            on_change=_switch_period,
        ):
            for key, label in (*PERIODS.items(), ("custom", "日時指定（UTC）")):
                t.option(label, value=key, selected=key == selected)


def absolute_period(filters: dict[str, str]) -> None:
    """開始・終了のカレンダーとUTC時刻を表示する。"""
    custom = bool(filters["start"] or filters["end"])
    end = datetime.now(UTC).replace(second=0, microsecond=0)
    start = end - timedelta(hours=int(filters["hours"]))
    with t.fieldset(classes="absolute-period", hidden=not custom, disabled=not custom):
        t.legend("日時指定（UTC）")
        with t.div(classes="period-columns"):
            for key, label, default in (("start", "開始", start), ("end", "終了", end)):
                instant = (
                    datetime.fromisoformat(filters[key]).astimezone(UTC) if filters[key] else default
                )
                prefix = "f-" + key
                with t.div(classes="period-endpoint"):
                    t.strong(label + "日時")
                    t.period_calendar(prefix=prefix, label=label, selected=instant.date().isoformat())
                    with t.label(classes="field"):
                        t.span(label + "時刻（UTC）")
                        t.input(
                            type="time",
                            id=prefix + "-time",
                            value=instant.time().isoformat(),
                            step="any",
                            required=True,
                            classes="form-control",
                        )
