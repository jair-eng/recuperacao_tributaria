
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


def fmt_aliq_sped(v) -> str:
    if v is None or v == "":
        return ""

    s = str(v).strip().replace(",", ".")

    try:
        return f"{float(s):.4f}".replace(".", ",")
    except Exception:
        return str(v).replace(".", ",")


def to_decimal(valor: Any) -> Decimal:
    if valor is None:
        return Decimal("0")

    if isinstance(valor, Decimal):
        return valor

    if isinstance(valor, int):
        return Decimal(valor)

    if isinstance(valor, float):
        return Decimal(str(valor))

    s = str(valor).strip()

    if not s:
        return Decimal("0")

    s = s.replace("R$", "").replace(" ", "")

    if "," in s:
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

def somar_credito_base(registros: list[dict[str, Any]]) -> Decimal:
    total = Decimal("0.00")

    for item in registros:
        total += to_decimal(
            item.get("vl_bc_pis")
            or item.get("vl_bc_cofins")
            or item.get("vl_oper")
            or item.get("vl_item")
        )

    return total

def buscar_valor_bloco_m(ctx: dict, periodo: str, nat: str) -> Decimal:
    efd_por_mes_nat = ctx.get("efd_por_mes_nat") or {}

    item = efd_por_mes_nat.get(f"{periodo}|{nat}")

    if isinstance(item, dict):
        return to_decimal(item.get("efd_declarada") or 0)

    return to_decimal(item)