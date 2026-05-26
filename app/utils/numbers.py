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

    if isinstance(valor, Decimal):
        return valor

    txt = str(valor).strip()

    if not txt:
        return Decimal("0")

    # formato BR: 44.044,80
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")

    # formato US/Python: 44044.80
    # não remove ponto

    try:
        return Decimal(txt)

    except Exception:
        return Decimal("0")


def q2(valor):
    return Decimal(valor).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )

def calcular_impacto_estimado(
    *,
    vl_item,
    vl_desc,
    vl_icms,
    aliq_pis,
    aliq_cofins,
):
    vl_item = dec_any(vl_item)
    vl_desc = dec_any(vl_desc)
    vl_icms = dec_any(vl_icms)

    aliq_pis = dec_any(aliq_pis)
    aliq_cofins = dec_any(aliq_cofins)

    base = vl_item - vl_desc - vl_icms

    if base <= 0:
        return q2(0)

    impacto = base * ((aliq_pis + aliq_cofins) / 100)

    return q2(impacto)