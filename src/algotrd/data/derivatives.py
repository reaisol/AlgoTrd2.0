"""Provider-discovered NIFTY derivative contracts; never synthesize symbols."""
from dataclasses import dataclass
from datetime import date, datetime
import re
CONTRACT=re.compile(r"^NSE-NIFTY-(?P<expiry>\d{2}[A-Za-z]{3}\d{2})(?:-(?P<strike>\d+(?:\.\d+)?)-(?P<option>CE|PE)|-(?P<fut>FUT))$")
@dataclass(frozen=True)
class DerivativeContract:
 provider_symbol:str; expiry:date; asset_class:str; strike:float|None; option_type:str|None
 @property
 def instrument_id(self):
  suffix='FUT' if self.asset_class=='FUTURE' else f'{self.strike:g}-{self.option_type}'
  return f'NSE:FNO:NIFTY:{self.expiry.isoformat()}:{suffix}'
def parse_contract(symbol:str)->DerivativeContract:
 match=CONTRACT.match(symbol)
 if not match: raise ValueError(f'unsupported or malformed Groww NIFTY contract: {symbol}')
 expiry=datetime.strptime(match['expiry'],'%d%b%y').date()
 if match['fut']: return DerivativeContract(symbol,expiry,'FUTURE',None,None)
 return DerivativeContract(symbol,expiry,'OPTION',float(match['strike']),match['option'])
def extract_list(response:dict,key:str)->list:
 payload=response.get('payload',response); values=payload.get(key,[]) if isinstance(payload,dict) else []
 if not isinstance(values,list): raise ValueError(f'Groww response field {key} is not a list')
 return values
