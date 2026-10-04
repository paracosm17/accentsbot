from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pytest

from infrastructure.database.repo.users import UserRepo


def test_calendar_window_preserves_legacy_day_semantics() -> None:
    assert UserRepo._calendar_window_start(1) == datetime.combine(date.today(), time.min)
    assert UserRepo._calendar_window_start(7) == datetime.combine(
        date.today() - timedelta(days=6), time.min
    )


def test_calendar_window_rejects_non_positive_days() -> None:
    with pytest.raises(ValueError, match="positive"):
        UserRepo._calendar_window_start(0)
