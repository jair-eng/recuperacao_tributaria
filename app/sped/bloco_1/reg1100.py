from decimal import Decimal

from app.sped.blocoM.m_utils import _fmt_br, _clean_sped_line

def linha_1100(
    *,
    periodo: str,
    cod_cont: str,
    valor: Decimal,
    orig_cred: str = "01",
) -> str:
    """
    Gera registro 1100 no formato aceito pelo PVA.

    Para V2:
      - orig_cred normalmente = 01
      - valor entra como crédito apurado, disponível e saldo final
      - sem utilização no mês
    """
    v = _fmt_br(valor)

    return _clean_sped_line(
        f"|1100|{periodo}|{orig_cred}||{cod_cont}|"
        f"{v}|0,00|{v}|0,00|0,00|0,00|{v}|"
        f"0,00|0,00|0,00|0,00|0,00|{v}|"
    )