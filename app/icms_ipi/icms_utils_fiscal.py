from __future__ import annotations

from app.db.models.nf_icms_item import NfIcmsItem
from app.Legacy.fiscal.constants import DOM_GERAL, DOM_CAFE, DOM_AGRO, DOM_SUP, DOM_POSTO, DOM_TRANSP, DOM_REVENDA_GAS

from app.Legacy.fiscal.settings_fiscais import CFOPS_ELEGIVEIS, CFOPS_TRANSP_SUBCONTRATACAO, CFOPS_TRANSP_IMOBILIZADO, \
    CFOPS_POSTO_COMBUSTIVEL, CFOPS_REVENDA_GAS
from app.icms_ipi.icms_helpers import _only_digits, _norm_str


CFOPS_ENTRADA_CREDITO = CFOPS_ELEGIVEIS


def _cfop_item_icms(item: NfIcmsItem) -> str:
    for attr in ("cfop", "cod_cfop"):
        if hasattr(item, attr):
            v = getattr(item, attr)
            if v:
                return _only_digits(v)
    return ""


def _cfop_elegivel_por_dominio(item: NfIcmsItem | str, *, dominio: str) -> bool:
    if isinstance(item, str):
        cfop = item.strip()
    else:
        cfop = _cfop_item_icms(item)
    dom = _norm_str(dominio).upper()

    if not cfop:
        return False

    if dom == DOM_TRANSP:
        if cfop in CFOPS_TRANSP_SUBCONTRATACAO:
            return False
        if cfop in CFOPS_TRANSP_IMOBILIZADO:
            return False
        return True
    if dom == DOM_POSTO:
        return cfop in CFOPS_POSTO_COMBUSTIVEL
    if dom == DOM_REVENDA_GAS:
        return cfop in CFOPS_REVENDA_GAS

    if dom in {DOM_CAFE, DOM_AGRO}:
        return cfop in CFOPS_ELEGIVEIS

    return cfop in CFOPS_ELEGIVEIS







