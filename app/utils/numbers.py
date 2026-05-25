from decimal import Decimal, ROUND_HALF_UP
from decimal import Decimal, InvalidOperation
from typing import Any


def to_decimal(valor: Any) -> Decimal:

    if valor is None:
        return Decimal("0")

    s = str(valor).strip()

    if not s:
        return Decimal("0")

    s = s.replace(".", "").replace(",", ".")

    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")

def dec_any(valor) -> Decimal:
    if valor is None:
        return Decimal("0")

    txt = str(valor).strip()

    if not txt:
        return Decimal("0")

    txt = txt.replace(".", "").replace(",", ".")

    try:
        return Decimal(txt)
    except Exception:
        return Decimal("0")


def q2(valor):
    return Decimal(valor).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )