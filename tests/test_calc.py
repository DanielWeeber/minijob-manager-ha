"""Tests for the pure calculation helpers (anonymized data)."""

from datetime import date

from custom_components.minijob_manager.calc import current_monthly, next_due, yearly_earnings

ENTGELTE = [{"from": "2024-12-01", "to": None, "entgelt": 240.0}]


def test_yearly_open_ended():
    assert yearly_earnings(ENTGELTE, 2026) == 2880.0


def test_yearly_started_mid_year():
    e = [{"from": "2026-03-15", "to": None, "entgelt": 100.0}]
    assert yearly_earnings(e, 2026) == 1000.0


def test_yearly_change_of_wage():
    e = [
        {"from": "2026-01-01", "to": "2026-06-30", "entgelt": 200.0},
        {"from": "2026-07-01", "to": None, "entgelt": 300.0},
    ]
    assert yearly_earnings(e, 2026) == 6 * 200 + 6 * 300


def test_current_monthly():
    assert current_monthly(ENTGELTE, date(2026, 9, 30)) == 240.0
    assert current_monthly(ENTGELTE, date(2024, 1, 1)) is None


def test_next_due_skips_paid_and_past():
    rows = [
        {"beitraege": 210.53, "zahlungen": 0.0, "nettoFaelligkeit": "2026-07-31"},
        {"beitraege": 0.0, "zahlungen": -210.53, "nettoFaelligkeit": "2026-07-31"},
        {"beitraege": 220.0, "zahlungen": 0.0, "nettoFaelligkeit": "2027-02-01"},
    ]
    assert next_due(rows, date(2026, 9, 30)) == (date(2027, 2, 1), 220.0)
    assert next_due(rows[:2], date(2026, 7, 1)) is None
