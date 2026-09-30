"""Pure helpers (no Home Assistant imports) for earnings and due dates."""

from __future__ import annotations

from datetime import date
from typing import Any


def _month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


def yearly_earnings(entgelte: list[dict[str, Any]], year: int) -> float:
    """Sum monthly earnings for `year` (month granularity, open end = ongoing)."""
    total = 0.0
    y_start, y_end = year * 12, year * 12 + 11
    for period in entgelte:
        start = _month_index(date.fromisoformat(period["from"][:10]))
        end_raw = period.get("to")
        end = _month_index(date.fromisoformat(end_raw[:10])) if end_raw else y_end
        months = min(end, y_end) - max(start, y_start) + 1
        if months > 0:
            total += months * float(period["entgelt"])
    return round(total, 2)


def current_monthly(entgelte: list[dict[str, Any]], today: date) -> float | None:
    """Monthly earnings valid today."""
    for period in entgelte:
        start = date.fromisoformat(period["from"][:10])
        end_raw = period.get("to")
        end = date.fromisoformat(end_raw[:10]) if end_raw else None
        if start <= today and (end is None or today <= end):
            return float(period["entgelt"])
    return None


def next_due(rows: list[dict[str, Any]], today: date) -> tuple[date, float] | None:
    """Earliest upcoming contribution due date and amount."""
    upcoming: dict[date, float] = {}
    for row in rows:
        due = row.get("nettoFaelligkeit")
        if not due:
            continue
        due_date = date.fromisoformat(due[:10])
        if due_date >= today:
            # contributions positive, payments negative -> net still open
            net = float(row.get("beitraege") or 0) + float(row.get("zahlungen") or 0)
            upcoming[due_date] = upcoming.get(due_date, 0.0) + net
    upcoming = {d: v for d, v in upcoming.items() if v > 0.005}
    if not upcoming:
        return None
    first = min(upcoming)
    return first, round(upcoming[first], 2)
