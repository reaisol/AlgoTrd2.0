from datetime import date

from algotrd.data.collectors.windows import iter_one_minute_windows


def test_one_minute_windows_are_below_provider_limit_and_contiguous():
    windows = iter_one_minute_windows(date(2025, 11, 1), date(2025, 12, 1))
    assert len(windows) == 2
    assert (windows[0].end.date() - windows[0].start.date()).days == 27
    assert windows[0].end.date().fromordinal(windows[0].end.date().toordinal() + 1) == windows[1].start.date()
    assert windows[0].start.hour == 9 and windows[0].start.minute == 15
    assert windows[0].end.hour == 15 and windows[0].end.minute == 30
