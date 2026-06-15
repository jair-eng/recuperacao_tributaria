

from app.utils.numbers import to_decimal
from decimal import Decimal
from typing import Any


def buscar_efd_m_por_periodo_natureza(
    ctx: dict[str, Any],
    *,
    periodo: str,
    nat: str,
) -> Decimal:
    efd_por_mes_nat = ctx.get("efd_por_mes_nat") or {}

    periodo = str(periodo or "")
    nat = str(nat or "00").zfill(2)

    valor = (
        efd_por_mes_nat.get(f"{periodo}|{nat}")
        or efd_por_mes_nat.get((periodo, nat))
        or efd_por_mes_nat.get(periodo, {}).get(nat)
        or 0
    )

    if isinstance(valor, dict):
        return to_decimal(
            valor.get("efd_declarada")
            or valor.get("valor_efd")
            or valor.get("base_declarada")
            or valor.get("vl_bc_cred")
            or 0
        )

    return to_decimal(valor)


def somar_f100_por_categorias(
    ctx: dict,
    categorias: list[str],
) -> Decimal:
    por_categoria = (
        (ctx.get("f100") or {})
        .get("por_categoria")
        or {}
    )

    total = Decimal("0.00")

    for categoria in categorias:
        dados = por_categoria.get(categoria) or {}
        total += to_decimal(dados.get("vl_oper"))

    return total
