from __future__ import annotations

from typing import Optional


def normalizar_periodo(periodo: Optional[str]) -> Optional[str]:
    """
    Normaliza período para formato YYYYMM.

    Aceita:
    - YYYYMM
    - MMYYYY
    """

    if not periodo:
        return None

    periodo = str(periodo).strip()

    if len(periodo) != 6 or not periodo.isdigit():
        return None

    # já YYYYMM
    ano = int(periodo[:4])
    mes = int(periodo[4:])

    if 1900 <= ano <= 2100 and 1 <= mes <= 12:
        return periodo

    # tenta MMYYYY
    mes = int(periodo[:2])
    ano = int(periodo[2:])

    if 1 <= mes <= 12 and 1900 <= ano <= 2100:
        return f"{ano}{mes:02d}"

    return None