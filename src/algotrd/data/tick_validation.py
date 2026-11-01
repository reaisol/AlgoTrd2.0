from decimal import Decimal, InvalidOperation
TICK=Decimal('0.05')
def on_tick_grid(value) -> bool:
    """Exact decimal check; never use float modulo for market tick validation."""
    try:
        return (Decimal(str(value)) / TICK) % 1 == 0
    except (InvalidOperation, ValueError): return False
