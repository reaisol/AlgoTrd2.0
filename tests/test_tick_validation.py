from algotrd.data.tick_validation import on_tick_grid
def test_option_tick_grid_decimal():
    assert all(on_tick_grid(v) for v in [100.00,100.05,100.10])
    assert not on_tick_grid(100.03) and not on_tick_grid(100.07)
    assert on_tick_grid(100.05000000000001) is False
