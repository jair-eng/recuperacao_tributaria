from dataclasses import dataclass
from decimal import Decimal
from typing import List
from app.sped.blocoM.m_utils import _clean_sped_line, _d, _reg_of_line
from app.sped.bloco_1.reg1500 import linha_1500


@dataclass(frozen=True)
class Reg1500:
    periodo: str       # YYYYMM
    cod_cont: str
    valor: Decimal
    linha: str

def _parse_1500(linha: str):
    ln = _clean_sped_line(linha)
    parts = ln.strip("|").split("|")
    return parts[1:] if len(parts) > 1 else []


def yyyymm_to_mmyyyy(periodo: str) -> str:
    """
    Converte YYYYMM -> MMYYYY
    """
    if not periodo or len(periodo) != 6:
        raise ValueError(f"Período inválido: {periodo}")
    return periodo[4:6] + periodo[0:4]