from __future__ import annotations

from decimal import Decimal
from typing import Dict, List
from app.config.settings import ALIQUOTA_PIS, ALIQUOTA_COFINS, ALIQUOTA_PIS_PRESUMIDO, ALIQUOTA_COFINS_PRESUMIDO
from app.Legacy.fiscal.constants import REGS_M_RELEVANTES
from app.sped.blocoM.m_utils import _clean_sped_line, _reg_of_line, _fmt_br, _q2, sanitizar_bloco_m, _split_m, \
    _somar_campo, _join_m, _dec_m,  _ensure_len


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
    cod_cred: str,
) -> List[str]:

    cod_cred = str(cod_cred or "").strip()

    if not cod_cred:
        raise ValueError(
            "cod_cred obrigatório. O valor deve vir do enquadramento fiscal da V2."
        )

    linhas: List[str] = []

    for nat, por_cst in sorted((base_por_nat_cst or {}).items()):
        for cst, base in sorted((por_cst or {}).items()):

            base = _q2(Decimal(str(base or "0")))

            if base <= 0:
                continue

            # ------------------------------------------------
            # Alíquotas conforme CST
            # ------------------------------------------------
            if str(cst).strip() == "60":
                # PF
                aliq_pis = Decimal(str(ALIQUOTA_PIS_PRESUMIDO))
                aliq_cofins = Decimal(str(ALIQUOTA_COFINS_PRESUMIDO))

                aliq_pis_txt = "1,2375"
                aliq_cofins_txt = "5,7000"

            else:
                # Fluxo já existente
                aliq_pis = Decimal(str(ALIQUOTA_PIS))
                aliq_cofins = Decimal(str(ALIQUOTA_COFINS))

                aliq_pis_txt = "1,6500"
                aliq_cofins_txt = "7,6000"

            # ------------------------------------------------
            # Créditos
            # ------------------------------------------------
            pis = _q2(base * aliq_pis)
            cofins = _q2(base * aliq_cofins)

            linhas.append(
                f"|M100|{cod_cred}|0|{_fmt_br(base)}|{aliq_pis_txt}|||{_fmt_br(pis)}|"
                f"0|0|0|{_fmt_br(pis)}|1|0,00|{_fmt_br(pis)}|"
            )

            linhas.append(
                f"|M105|{nat}|{cst}|{_fmt_br(base)}||{_fmt_br(base)}|{_fmt_br(base)}||||"
            )

            linhas.append(
                f"|M500|{cod_cred}|0|{_fmt_br(base)}|{aliq_cofins_txt}|||{_fmt_br(cofins)}|"
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
    Preserva Bloco M original e mescla créditos delta.

    Regra:
      - Se já existir M100/M500 com mesmo COD_CRED, soma bases/créditos.
      - Se já existir M105/M505 com mesma NAT+CST, soma bases.
      - Só insere linhas novas quando a chave ainda não existe.
      - Recalcula M990.
    """
    if not linhas_m_originais:
        return sanitizar_bloco_m(linhas_append)

    linhas_m = [_clean_sped_line(x) for x in linhas_m_originais if _clean_sped_line(x)]
    linhas_append = [_clean_sped_line(x) for x in linhas_append if _clean_sped_line(x)]

    # -----------------------------
    # 1) Indexa deltas do append
    # -----------------------------
    delta_m100: Dict[tuple[str, Decimal], Dict[str, Decimal]] = {}
    delta_m500: Dict[tuple[str, Decimal], Dict[str, Decimal]] = {}
    delta_m105: Dict[tuple[str, str], Decimal] = {}
    delta_m505: Dict[tuple[str, str], Decimal] = {}

    linhas_append_restantes: List[str] = []

    for ln in linhas_append:
        reg, dados = _split_m(ln)

        if reg == "M100":
            cod_cred = str(dados[0] if len(dados) > 0 else "").strip()
            base = _dec_m(dados[2] if len(dados) > 2 else "0")
            aliq = _dec_m(dados[3] if len(dados) > 3 else "0")
            cred = _dec_m(dados[6] if len(dados) > 6 else "0")

            key = (cod_cred, aliq)

            if cod_cred:
                delta_m100.setdefault(
                    key,
                    {
                        "base": Decimal("0.00"),
                        "cred": Decimal("0.00"),
                    },
                )
                delta_m100[key]["base"] += base
                delta_m100[key]["cred"] += cred
            else:
                linhas_append_restantes.append(ln)


        elif reg == "M500":
            cod_cred = str(dados[0] if len(dados) > 0 else "").strip()
            base = _dec_m(dados[2] if len(dados) > 2 else "0")
            aliq = _dec_m(dados[3] if len(dados) > 3 else "0")
            cred = _dec_m(dados[6] if len(dados) > 6 else "0")
            key = (cod_cred, aliq)
            if cod_cred:
                delta_m500.setdefault(
                    key,
                    {
                        "base": Decimal("0.00"),
                        "cred": Decimal("0.00"),
                    },
                )
                delta_m500[key]["base"] += base
                delta_m500[key]["cred"] += cred
            else:
                linhas_append_restantes.append(ln)

        elif reg == "M105":
            nat = str(dados[0] if len(dados) > 0 else "").strip()
            cst = str(dados[1] if len(dados) > 1 else "").strip()
            base = _dec_m(dados[2] if len(dados) > 2 else "0")

            if nat and cst:
                delta_m105[(nat, cst)] = delta_m105.get((nat, cst), Decimal("0.00")) + base
            else:
                linhas_append_restantes.append(ln)

        elif reg == "M505":
            nat = str(dados[0] if len(dados) > 0 else "").strip()
            cst = str(dados[1] if len(dados) > 1 else "").strip()
            base = _dec_m(dados[2] if len(dados) > 2 else "0")

            if nat and cst:
                delta_m505[(nat, cst)] = delta_m505.get((nat, cst), Decimal("0.00")) + base
            else:
                linhas_append_restantes.append(ln)

        else:
            linhas_append_restantes.append(ln)

    # -----------------------------
    # 2) Mescla nas linhas originais
    # -----------------------------
    out: List[str] = []
    encontrou_m100: set[tuple[str, Decimal]] = set()
    encontrou_m500: set[tuple[str, Decimal]] = set()
    encontrou_m105: set[tuple[str, str]] = set()
    encontrou_m505: set[tuple[str, str]] = set()

    for ln in linhas_m:
        reg, dados = _split_m(ln)

        if reg == "M990":
            continue

        if reg == "M100":
            cod_cred = str(dados[0] if len(dados) > 0 else "").strip()
            aliq = _dec_m(dados[3] if len(dados) > 3 else "0")

            key = (cod_cred, aliq)
            delta = delta_m100.get(key)

            if delta:
                base = _q2(delta["base"])
                cred = _q2(delta["cred"])

                _somar_campo(dados, 2, base)
                _somar_campo(dados, 6, cred)
                _somar_campo(dados, 10, cred)

                _ensure_len(dados, 13)

                vl_desc_original = _q2(_dec_m(dados[12]))
                vl_cred_disp = _q2(_dec_m(dados[10]))
                sld = _q2(vl_cred_disp - vl_desc_original)

                if sld > 0:
                    dados[11] = "1"
                    dados[13] = _fmt_br(sld)
                else:
                    dados[11] = "0"
                    dados[12] = _fmt_br(vl_cred_disp)
                    dados[13] = "0,00"

                encontrou_m100.add(key)
                ln = _join_m("M100", dados)


        elif reg == "M500":
            cod_cred = str(dados[0] if len(dados) > 0 else "").strip()
            aliq = _dec_m(dados[3] if len(dados) > 3 else "0")
            key = (cod_cred, aliq)
            delta = delta_m500.get(key)

            if delta:
                base = _q2(delta["base"])
                cred = _q2(delta["cred"])

                _somar_campo(dados, 2, base)
                _somar_campo(dados, 6, cred)
                _somar_campo(dados, 10, cred)

                _ensure_len(dados, 13)

                vl_desc_original = _q2(_dec_m(dados[12]))
                vl_cred_disp = _q2(_dec_m(dados[10]))
                sld = _q2(vl_cred_disp - vl_desc_original)

                if sld > 0:
                    dados[11] = "1"
                    dados[13] = _fmt_br(sld)
                else:
                    dados[11] = "0"
                    dados[12] = _fmt_br(vl_cred_disp)
                    dados[13] = "0,00"

                encontrou_m500.add(key)
                ln = _join_m("M500", dados)

        elif reg == "M105":
            nat = str(dados[0] if len(dados) > 0 else "").strip()
            cst = str(dados[1] if len(dados) > 1 else "").strip()
            key = (nat, cst)
            delta = delta_m105.get(key)

            if delta:
                base = _q2(delta)

                # M105:
                # 2 VL_BC_PIS_TOT
                # 4 VL_BC_PIS_NC
                # 5 VL_BC_PIS
                _somar_campo(dados, 2, base)
                _somar_campo(dados, 4, base)
                _somar_campo(dados, 5, base)

                encontrou_m105.add(key)
                ln = _join_m("M105", dados)

        elif reg == "M505":
            nat = str(dados[0] if len(dados) > 0 else "").strip()
            cst = str(dados[1] if len(dados) > 1 else "").strip()
            key = (nat, cst)
            delta = delta_m505.get(key)

            if delta:
                base = _q2(delta)

                # M505:
                # 2 VL_BC_COFINS_TOT
                # 4 VL_BC_COFINS_NC
                # 5 VL_BC_COFINS
                _somar_campo(dados, 2, base)
                _somar_campo(dados, 4, base)
                _somar_campo(dados, 5, base)

                encontrou_m505.add(key)
                ln = _join_m("M505", dados)

        out.append(ln)

    # -----------------------------
    # 3) Insere apenas o que não encontrou
    # -----------------------------
    append_pis: List[str] = []
    append_cofins: List[str] = []

    for ln in linhas_append:
        reg, dados = _split_m(ln)

        if reg == "M100":
            cod_cred = str(dados[0] if len(dados) > 0 else "").strip()
            aliq = _dec_m(dados[3] if len(dados) > 3 else "0")
            key = (cod_cred, aliq)
            if cod_cred and key not in encontrou_m100:
                append_pis.append(ln)

        elif reg == "M105":
            nat = str(dados[0] if len(dados) > 0 else "").strip()
            cst = str(dados[1] if len(dados) > 1 else "").strip()
            if (nat, cst) not in encontrou_m105:
                append_pis.append(ln)

        elif reg == "M500":
            cod_cred = str(dados[0] if len(dados) > 0 else "").strip()
            aliq = _dec_m(dados[3] if len(dados) > 3 else "0")
            key = (cod_cred, aliq)
            if cod_cred and key not in encontrou_m500:
                append_cofins.append(ln)

        elif reg == "M505":
            nat = str(dados[0] if len(dados) > 0 else "").strip()
            cst = str(dados[1] if len(dados) > 1 else "").strip()
            if (nat, cst) not in encontrou_m505:
                append_cofins.append(ln)

        else:
            linhas_append_restantes.append(ln)

    # evita duplicidade exata
    append_pis = list(dict.fromkeys(append_pis))
    append_cofins = list(dict.fromkeys(append_cofins))

    # -----------------------------
    # 4) Se precisou criar chave nova, insere nos pontos corretos
    # -----------------------------
    final: List[str] = []
    inseriu_pis = False
    inseriu_cofins = False

    for ln in out:
        reg = _reg_of_line(ln)

        if reg == "M200" and append_pis and not inseriu_pis:
            final.extend(append_pis)
            inseriu_pis = True

        if reg == "M600" and append_cofins and not inseriu_cofins:
            final.extend(append_cofins)
            inseriu_cofins = True

        final.append(ln)

    if append_pis and not inseriu_pis:
        final.extend(append_pis)

    if append_cofins and not inseriu_cofins:
        final.extend(append_cofins)

    if not final or not final[0].startswith("|M001|"):
        final.insert(0, "|M001|0|")

    final.append(f"|M990|{len(final) + 1}|")
    return final