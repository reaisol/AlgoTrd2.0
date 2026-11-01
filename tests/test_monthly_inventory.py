from datetime import date

from algotrd.data.monthly_inventory import expected_weekdays


def test_september_2026_holiday_is_not_a_trading_session():
    sessions = expected_weekdays(date(2026, 9, 1), date(2026, 9, 30), {date(2026, 9, 14)})
    assert len(sessions) == 21
    assert date(2026, 9, 14) not in sessions
