from typing import Any

from app.utils.strings import only_digits



def normalizar_periodo_aaaamm(valor: Any) -> str:
    """
    Aceita:
    - 202203
    - 2022-03
    - 20220311
    - 11/03/2022
    - 032022

    Retorna AAAAMM ou vazio.
    """

    s = str(valor or "").strip()
    if not s:
        return ""

    dig = only_digits(s)

    if len(dig) == 6:
        # AAAAMM
        if dig[:4].startswith("20"):
            return dig

        # MMAAAA
        if dig[-4:].startswith("20"):
            return dig[-4:] + dig[:2]

    if len(dig) >= 8:
        # AAAAMMDD
        if dig[:4].startswith("20"):
            return dig[:6]

        # DDMMAAAA
        if dig[-4:].startswith("20"):
            return dig[-4:] + dig[2:4]

    return ""


def periodo_aaaamm_para_data_min(periodo: Any) -> str:
    periodo = normalizar_periodo_aaaamm(periodo)
    if len(periodo) != 6:
        return ""

    return f"{periodo}01"


def periodo_entre(valor_periodo: Any, inicio_aaaamm: str, fim_aaaamm: str) -> bool:
    periodo = normalizar_periodo_aaaamm(valor_periodo)

    if len(periodo) != 6:
        return False

    return inicio_aaaamm <= periodo <= fim_aaaamm


def eh_periodo_lc192(valor_periodo: Any) -> bool:
    """
    Janela LC192 usada no motor:
    202203 até 202208.
    """

    return periodo_entre(valor_periodo, "202203", "202208")