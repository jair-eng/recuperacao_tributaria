from __future__ import annotations

from decimal import Decimal
from typing import Dict, List
from app.config.settings import ALIQUOTA_PIS, ALIQUOTA_COFINS
from app.fiscal.constants import REGS_M_RELEVANTES
from app.sped.blocoM.m_utils import _clean_sped_line, _reg_of_line, _fmt_br, _q2, sanitizar_bloco_m


def bloco_m_tem_valor_relevante(linhas_m: List[str]) -> bool:
    """
    Retorna True se o Bloco M original tem apuração/crédito/débito real.
    Se estiver zerado ou inexistente, o export pode seguir o fluxo atual.
    """
    for ln in linhas_m or []:
        s = _clean_sped_line(ln)
        reg = _reg_of_line(s)

        if reg not in REGS_M_RELEVANTES:
            continue

        partes = s.strip("|").split("|")[1:]  # remove REG

        for campo in partes:
            txt = str(campo or "").strip()
            if not txt:
                continue

            try:
                valor = Decimal(txt.replace(".", "").replace(",", "."))
            except Exception:
                continue

            if valor != Decimal("0"):
                return True

    return False


def gerar_linhas_m_credito_append(
    base_por_nat_cst: Dict[str, Dict[str, Decimal]],
    *,
    cod_cred: str = "201",
) -> List[str]:
    """
    Gera somente linhas novas de crédito:
    M100/M105 para PIS
    M500/M505 para COFINS

    Padrão compatível com construir_bloco_m_v3:
      M100/M500 usam cod_cred
      M105/M505 usam nat/cst

    Não gera M001/M990.
    Não mexe em M200/M600.
    """
    linhas: List[str] = []

    for nat, por_cst in sorted((base_por_nat_cst or {}).items()):
        for cst, base in sorted((por_cst or {}).items()):
            base = _q2(Decimal(str(base or "0")))
            if base <= 0:
                continue

            pis = _q2(base * Decimal(str(ALIQUOTA_PIS)))
            cofins = _q2(base * Decimal(str(ALIQUOTA_COFINS)))

            linhas.append(
                f"|M100|{cod_cred}|0|{_fmt_br(base)}|1,6500|||{_fmt_br(pis)}|"
                f"0|0|0|{_fmt_br(pis)}|1|0,00|{_fmt_br(pis)}|"
            )
            linhas.append(
                f"|M105|{nat}|{cst}|{_fmt_br(base)}||{_fmt_br(base)}|{_fmt_br(base)}||||"
            )

            linhas.append(
                f"|M500|{cod_cred}|0|{_fmt_br(base)}|7,6000|||{_fmt_br(cofins)}|"
                f"0|0|0|{_fmt_br(cofins)}|1|0,00|{_fmt_br(cofins)}|"
            )
            linhas.append(
                f"|M505|{nat}|{cst}|{_fmt_br(base)}||{_fmt_br(base)}|{_fmt_br(base)}||||"
            )

    return linhas


def inserir_creditos_no_bloco_m_original(
    linhas_m_originais: List[str],
    linhas_append: List[str],
) -> List[str]:
    """
    Preserva Bloco M original e insere:
      - M100/M105 novos antes do primeiro M200
      - M500/M505 novos antes do primeiro M600
    Recalcula M990.
    """
    if not linhas_m_originais:
        return sanitizar_bloco_m(linhas_append)

    linhas_m = [_clean_sped_line(x) for x in linhas_m_originais if _clean_sped_line(x)]
    linhas_append = [_clean_sped_line(x) for x in linhas_append if _clean_sped_line(x)]

    append_pis = [x for x in linhas_append if _reg_of_line(x) in {"M100", "M105"}]
    append_cofins = [x for x in linhas_append if _reg_of_line(x) in {"M500", "M505"}]

    out: List[str] = []
    inseriu_pis = False
    inseriu_cofins = False

    for ln in linhas_m:
        reg = _reg_of_line(ln)

        if reg == "M990":
            continue

        if reg == "M200" and not inseriu_pis:
            out.extend(append_pis)
            inseriu_pis = True

        if reg == "M600" and not inseriu_cofins:
            out.extend(append_cofins)
            inseriu_cofins = True

        out.append(ln)

    if not inseriu_pis:
        out.extend(append_pis)

    if not inseriu_cofins:
        out.extend(append_cofins)

    if not out or not out[0].startswith("|M001|"):
        out.insert(0, "|M001|0|")

    out.append(f"|M990|{len(out) + 1}|")
    return out