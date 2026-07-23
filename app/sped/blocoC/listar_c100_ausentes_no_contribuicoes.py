from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from app.Legacy.fiscal.settings_fiscais import CFOPS_ELEGIVEIS, COD_SIT_SKIP_CONS
from app.icms_ipi.icms_helpers import _only_digits
from app.sped.blocoC.c100_utils import montar_linha_c100_de_icms
import logging

logger = logging.getLogger(__name__)


CFOPS_ELEGIVEIS_CREDITO = CFOPS_ELEGIVEIS
COD_SIT_SKIP = COD_SIT_SKIP_CONS


def _extrair_ind_oper_cod_sit_do_nf(nf: Any) -> tuple[str, str]:
    """
    Usa a mesma montagem do C100 que a correção usa hoje.
    Layout esperado:
    |C100|IND_OPER|IND_EMIT|COD_PART|COD_MOD|COD_SIT|...
    """
    try:
        linha_c100 = montar_linha_c100_de_icms(nf)
        partes = [p for p in str(linha_c100 or "").split("|") if p != ""]
        if not partes or partes[0].strip().upper() != "C100":
            return "", ""

        ind_oper = str(partes[1]).strip() if len(partes) > 1 else ""
        cod_sit = str(partes[5]).strip() if len(partes) > 5 else ""
        return ind_oper, cod_sit
    except Exception:
        return "", ""


def _nf_icms_pf_skip(nf: Any) -> bool:
    """
    Para C100 ausente não dá para usar eh_pf_por_c100().
    Então tentamos decidir PF/PJ pela base ICMS.
    """
    cnpj = _only_digits(
        getattr(nf, "cnpj_participante", None)
        or getattr(nf, "cnpj_cpf_part", None)
        or getattr(nf, "cnpj_cpf", None)
        or getattr(nf, "cnpj_emitente", None)
        or ""
    )
    cpf = _only_digits(
        getattr(nf, "cpf_participante", None)
        or getattr(nf, "cpf", None)
        or ""
    )
    if cnpj:
        return False

    return len(cpf) == 11
