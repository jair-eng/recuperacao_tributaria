from __future__ import annotations

from pathlib import Path
from typing import Any
from app.utils.ecd_gap_utils import get
from app.utils.numbers import to_decimal
from app.utils.sped import ler_linhas_sped



def carregar_c170_local(
    arquivos_contrib: list[Path],
) -> list[dict[str, Any]]:
    registros = []

    periodo_atual = None
    mapa_0200 = {}

    for arquivo in arquivos_contrib:
        c100_atual = None

        for partes in ler_linhas_sped(arquivo):
            reg = get(partes, 0, "")

            if reg == "0000":
                dt_ini = get(partes, 6)
                if dt_ini and len(dt_ini) == 8:
                    periodo_atual = dt_ini[4:8] + dt_ini[2:4]

            elif reg == "0200":
                cod_item = get(partes, 1)
                if cod_item:
                    mapa_0200[cod_item] = {
                        "cod_item": cod_item,
                        "descr_item": get(partes, 2),
                        "cod_barra": get(partes, 3),
                        "cod_ant_item": get(partes, 4),
                        "unid_inv": get(partes, 5),
                        "tipo_item": get(partes, 6),
                        "cod_ncm": get(partes, 7),
                        "ex_ipi": get(partes, 8),
                        "cod_gen": get(partes, 9),
                        "cod_lst": get(partes, 10),
                        "aliq_icms": to_decimal(get(partes, 11)),
                    }

            elif reg == "C100":
                c100_atual = {
                    "arquivo": arquivo.name,
                    "ind_oper": get(partes, 1),
                    "ind_emit": get(partes, 2),
                    "cod_part": get(partes, 3),
                    "cod_mod": get(partes, 4),
                    "cod_sit": get(partes, 5),
                    "ser": get(partes, 6),
                    "num_doc": get(partes, 7),
                    "chv_nfe": get(partes, 8),
                    "dt_doc": get(partes, 9),
                    "dt_e_s": get(partes, 10),
                    "vl_doc": to_decimal(get(partes, 11)),
                }

            elif reg == "C170":
                if not c100_atual:
                    continue

                vl_pis = to_decimal(get(partes, 29))
                vl_cofins = to_decimal(get(partes, 35))
                cod_item = get(partes, 2)
                item_0200 = mapa_0200.get(cod_item) or {}

                registros.append({
                    "origem": "CONTRIB_C170",
                    "arquivo": arquivo.name,
                    "periodo": periodo_atual,

                    "ind_oper": c100_atual.get("ind_oper"),
                    "ind_emit": c100_atual.get("ind_emit"),
                    "cod_part": c100_atual.get("cod_part"),
                    "cod_mod": c100_atual.get("cod_mod"),
                    "cod_sit": c100_atual.get("cod_sit"),
                    "ser": c100_atual.get("ser"),
                    "num_doc": c100_atual.get("num_doc"),
                    "chv_nfe": c100_atual.get("chv_nfe"),
                    "dt_doc": c100_atual.get("dt_doc"),
                    "dt_e_s": c100_atual.get("dt_e_s"),
                    "vl_doc": c100_atual.get("vl_doc"),

                    "num_item": get(partes, 1),
                    "cod_item": cod_item,
                    "descr_item_0200": item_0200.get("descr_item"),
                    "ncm": item_0200.get("cod_ncm"),
                    "tipo_item": item_0200.get("tipo_item"),
                    "descr_compl": get(partes, 3),
                    "qtd": to_decimal(get(partes, 4)),
                    "unid": get(partes, 5),
                    "vl_item": to_decimal(get(partes, 6)),
                    "vl_desc": to_decimal(get(partes, 7)),
                    "ind_mov": get(partes, 8),

                    "cst_icms": get(partes, 9),
                    "cfop": get(partes, 10),
                    "cod_nat": get(partes, 11),

                    "cst_pis": get(partes, 24),
                    "vl_bc_pis": to_decimal(get(partes, 25)),
                    "aliq_pis": to_decimal(get(partes, 26)),
                    "quant_bc_pis": to_decimal(get(partes, 27)),
                    "aliq_pis_quant": to_decimal(get(partes, 28)),
                    "vl_pis": vl_pis,

                    "cst_cofins": get(partes, 30),
                    "vl_bc_cofins": to_decimal(get(partes, 31)),
                    "aliq_cofins": to_decimal(get(partes, 32)),
                    "quant_bc_cofins": to_decimal(get(partes, 33)),
                    "aliq_cofins_quant": to_decimal(get(partes, 34)),
                    "vl_cofins": vl_cofins,

                    "cod_cta": get(partes, 36),

                    "tem_credito_pis": vl_pis > 0,
                    "tem_credito_cofins": vl_cofins > 0,
                    "tem_credito": vl_pis > 0 or vl_cofins > 0,

                })

    return registros


def enriquecer_c170_com_ecd(
    c170: list[dict],
    linhas_ecd: list[dict],
) -> list[dict]:
    ecd_por_cod_cta = {
        str(l.get("cod_cta") or "").strip(): l
        for l in linhas_ecd
        if l.get("cod_cta")
    }

    enriquecidos = []

    for item in c170:
        cod_cta = str(item.get("cod_cta") or "").strip()
        ecd = ecd_por_cod_cta.get(cod_cta)

        novo = dict(item)

        if ecd:
            novo.update({
                "ecd_encontrada": True,
                "nome_conta_ecd": ecd.get("nome_cta") or ecd.get("descricao_conta"),
                "categoria_ecd": ecd.get("categoria"),
                "grupo_ecd": ecd.get("grupo"),
                "fundamento_ecd": ecd.get("fundamento"),
                "nat_bc_cred_esperada": ecd.get("nat_bc_cred"),
                "valor_ecd": ecd.get("valor"),
            })
        else:
            novo.update({
                "ecd_encontrada": False,
                "nome_conta_ecd": None,
                "categoria_ecd": None,
                "grupo_ecd": None,
                "fundamento_ecd": None,
                "nat_bc_cred_esperada": None,
                "valor_ecd": None,
            })

        enriquecidos.append(novo)

    return enriquecidos


