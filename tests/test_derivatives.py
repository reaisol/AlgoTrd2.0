import pytest
from algotrd.data.derivatives import parse_contract
from algotrd.data.atm_mapper import map_atm
def test_parses_actual_provider_symbol_shapes():
    fut=parse_contract('NSE-NIFTY-30Sep26-FUT'); call=parse_contract('NSE-NIFTY-30Sep26-25000-CE')
    assert fut.asset_class=='FUTURE' and call.option_type=='CE' and call.strike==25000
    assert fut.instrument_id != call.instrument_id
def test_rejects_invented_symbol():
    with pytest.raises(ValueError): parse_contract('NIFTY25000CE')
def test_atm_reference_precedes_decision():
    from datetime import UTC,datetime,timedelta
    c=[parse_contract(f'NSE-NIFTY-08Sep26-{s}-CE') for s in range(24500,24851,50)]
    t=datetime(2026,9,1,4,0,tzinfo=UTC); result=map_atm([{'timestamp_utc':t,'close':24620}],t+timedelta(minutes=1),c)
    assert result['reference_timestamp_utc'] < t+timedelta(minutes=1) and result['atm_strike']==24600
