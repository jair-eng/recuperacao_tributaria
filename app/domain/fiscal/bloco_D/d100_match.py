from __future__ import annotations

from typing import Any
from app.utils.numbers import to_decimal
from app.utils.strings import only_digits, norm_str


def valor_d100(d100: dict[str, Any]):
    """
    Valor preferencial para match documental.
    No D100, usamos VL_SERV como principal.
    Se não existir, usamos VL_DOC.
    """
    return to_decimal(
        d100.get("vl_serv")
        or d100.get("vl_doc")
    )


def match_por_chave_cte(
    d100_icms: dict[str, Any],
    d100_contrib: dict[str, Any],
) -> bool:
    chave_icms = only_digits(d100_icms.get("chave_cte"))
    chave_contrib = only_digits(d100_contrib.get("chave_cte"))

    return bool(chave_icms and chave_contrib and chave_icms == chave_contrib)


def match_por_documento(
    d100_icms: dict[str, Any],
    d100_contrib: dict[str, Any],
) -> bool:
    num_icms = norm_str(d100_icms.get("num_doc"))
    num_contrib = norm_str(d100_contrib.get("num_doc"))

    serie_icms = norm_str(d100_icms.get("serie"))
    serie_contrib = norm_str(d100_contrib.get("serie"))

    dt_icms = only_digits(d100_icms.get("dt_doc"))
    dt_contrib = only_digits(d100_contrib.get("dt_doc"))

    valor_icms = valor_d100(d100_icms)
    valor_contrib = valor_d100(d100_contrib)

    return (
        bool(num_icms)
        and num_icms == num_contrib
        and serie_icms == serie_contrib
        and dt_icms == dt_contrib
        and valor_icms == valor_contrib
    )


def match_d100_icms_contrib(
    d100_icms: dict[str, Any],
    d100_contrib: dict[str, Any],
) -> bool:
    """
    Match entre D100 do ICMS/IPI e D100 da EFD Contribuições.

    Estratégia:
    1. Match principal por chave_cte.
    2. Fallback por composição documental:
       num_doc + serie + dt_doc + vl_serv/vl_doc.
    """

    if not isinstance(d100_icms, dict) or not isinstance(d100_contrib, dict):
        return False

    if match_por_chave_cte(d100_icms, d100_contrib):
        return True

    return match_por_documento(d100_icms, d100_contrib)