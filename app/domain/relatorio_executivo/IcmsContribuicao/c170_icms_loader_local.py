from __future__ import annotations

from pathlib import Path
from typing import Any
from app.utils.numbers import to_decimal
from app.utils.sped import ler_linhas_sped, campo

IDX_C100 = {
    "ind_oper": 1,
    "ind_emit": 2,
    "cod_part": 3,
    "cod_mod": 4,
    "cod_sit": 5,
    "ser": 6,
    "num_doc": 7,
    "chv_nfe": 8,
    "dt_doc": 9,
    "dt_e_s": 10,
    "vl_doc": 11,
}

IDX_C170_ICMS = {
    "num_item": 1,
    "cod_item": 2,
    "descr_compl": 3,
    "qtd": 4,
    "unid": 5,
    "vl_item": 6,
    "vl_desc": 7,
    "ind_mov": 8,
    "cst_icms": 9,
    "cfop": 10,
    "cod_nat": 11,
    "vl_bc_icms": 12,
    "aliq_icms": 13,
    "vl_icms": 14,
    "vl_bc_icms_st": 15,
    "aliq_st": 16,
    "vl_icms_st": 17,
    "vl_ipi": 23,

    # PIS
    "cst_pis": 24,
    "vl_bc_pis": 25,
    "aliq_pis": 26,
    "vl_pis": 29,

    # COFINS
    "cst_cofins": 30,
    "vl_bc_cofins": 31,
    "aliq_cofins": 32,
    "vl_cofins": 35,
}

def normalizar_cod_item(valor: Any) -> str:
    return (
        str(valor or "")
        .replace("\ufeff", "")
        .strip()
        .upper()
    )
def carregar_c170_icms_local(
    arquivos_icms: list[Path],
) -> list[dict[str, Any]]:
    itens: list[dict[str, Any]] = []

    for arquivo in arquivos_icms:
        mapa_0200: dict[str, dict[str, Any]] = {}

        # --------------------------------------------------
        # 1ª passada: carrega o 0200 deste arquivo
        # --------------------------------------------------
        for partes in ler_linhas_sped(arquivo):
            reg = partes[0] if partes else ""

            if reg != "0200":
                continue

            cod_item = normalizar_cod_item(
                campo(partes, 1)
            )

            if not cod_item:
                continue

            novo_0200 = {
                "descr_item_0200": campo(partes, 2),
                "cod_barra": campo(partes, 3),
                "cod_ant_item": campo(partes, 4),
                "unid_inv": campo(partes, 5),
                "tipo_item": campo(partes, 6),
                "cod_ncm": campo(partes, 7),
                "ex_ipi": campo(partes, 8),
                "cod_gen": campo(partes, 9),
                "cod_lst": campo(partes, 10),
                "aliq_icms_0200": to_decimal(
                    campo(partes, 11)
                ),
                "cest": campo(partes, 12),
            }

            anterior = mapa_0200.get(cod_item) or {}

            mapa_0200[cod_item] = {
                chave: anterior.get(chave) or novo_0200.get(chave)
                for chave in novo_0200
            }

        periodo_atual: str | None = None
        c100_atual: dict[str, Any] | None = None

        # --------------------------------------------------
        # 2ª passada: lê 0000, C100 e C170 do mesmo arquivo
        # --------------------------------------------------
        for partes in ler_linhas_sped(arquivo):
            reg = partes[0] if partes else ""

            if reg == "0000":
                dt_ini = campo(partes, 4)

                periodo_atual = (
                    dt_ini[4:8] + dt_ini[2:4]
                    if len(dt_ini) == 8
                    else None
                )

            elif reg == "C100":
                cod_mod = campo(
                    partes,
                    IDX_C100["cod_mod"],
                )

                if str(cod_mod or "").zfill(2) != "55":
                    c100_atual = None
                    continue

                c100_atual = {
                    "periodo": periodo_atual,
                    "arquivo": arquivo.name,
                    "ind_oper": campo(partes, IDX_C100["ind_oper"]),
                    "ind_emit": campo(partes, IDX_C100["ind_emit"]),
                    "cod_part": campo(partes, IDX_C100["cod_part"]),
                    "cod_mod": cod_mod,
                    "cod_sit": campo(partes, IDX_C100["cod_sit"]),
                    "ser": campo(partes, IDX_C100["ser"]),
                    "num_doc": campo(partes, IDX_C100["num_doc"]),
                    "chv_nfe": campo(partes, IDX_C100["chv_nfe"]),
                    "dt_doc": campo(partes, IDX_C100["dt_doc"]),
                    "dt_e_s": campo(partes, IDX_C100["dt_e_s"]),
                    "vl_doc": to_decimal(
                        campo(partes, IDX_C100["vl_doc"])
                    ),
                }

            elif reg == "C170" and c100_atual:
                cod_item = normalizar_cod_item(
                    campo(
                        partes,
                        IDX_C170_ICMS["cod_item"],
                    )
                )

                item_0200 = mapa_0200.get(cod_item) or {}

                cst_icms = campo(
                    partes,
                    IDX_C170_ICMS["cst_icms"],
                )

                item = {
                    **c100_atual,

                    "num_item": campo(
                        partes,
                        IDX_C170_ICMS["num_item"],
                    ),
                    "cod_item": cod_item,
                    "descr_compl": campo(
                        partes,
                        IDX_C170_ICMS["descr_compl"],
                    ),

                    "descr_item": (
                        item_0200.get("descr_item_0200")
                        or campo(
                            partes,
                            IDX_C170_ICMS["descr_compl"],
                        )
                    ),
                    "ncm": item_0200.get("cod_ncm") or "",
                    "cod_ncm": item_0200.get("cod_ncm") or "",
                    "tipo_item": item_0200.get("tipo_item") or "",
                    "unid_inv": item_0200.get("unid_inv") or "",
                    "cest": item_0200.get("cest") or "",

                    "qtd": to_decimal(
                        campo(partes, IDX_C170_ICMS["qtd"])
                    ),
                    "unid": campo(
                        partes,
                        IDX_C170_ICMS["unid"],
                    ),
                    "vl_item": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_item"])
                    ),
                    "vl_desc": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_desc"])
                    ),
                    "ind_mov": campo(
                        partes,
                        IDX_C170_ICMS["ind_mov"],
                    ),
                    "cst_icms": cst_icms,
                    "origem_mercadoria": (
                        cst_icms[:-2]
                        if len(cst_icms) >= 3
                        else ""
                    ),
                    "cst_icms_codigo": (
                        cst_icms[-2:]
                        if len(cst_icms) >= 2
                        else cst_icms
                    ),
                    "cfop": campo(
                        partes,
                        IDX_C170_ICMS["cfop"],
                    ),
                    "cod_nat": campo(
                        partes,
                        IDX_C170_ICMS["cod_nat"],
                    ),
                    "vl_bc_icms": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_bc_icms"])
                    ),
                    "aliq_icms": to_decimal(
                        campo(partes, IDX_C170_ICMS["aliq_icms"])
                    ),
                    "vl_icms": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_icms"])
                    ),
                    "vl_bc_icms_st": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_bc_icms_st"])
                    ),
                    "vl_icms_st": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_icms_st"])
                    ),
                    "vl_ipi": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_ipi"])
                    ),

                    "cst_pis": campo(
                        partes,
                        IDX_C170_ICMS["cst_pis"],
                    ),
                    "vl_bc_pis": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_bc_pis"])
                    ),
                    "aliq_pis": to_decimal(
                        campo(partes, IDX_C170_ICMS["aliq_pis"])
                    ),
                    "vl_pis": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_pis"])
                    ),

                    "cst_cofins": campo(
                        partes,
                        IDX_C170_ICMS["cst_cofins"],
                    ),
                    "vl_bc_cofins": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_bc_cofins"])
                    ),
                    "aliq_cofins": to_decimal(
                        campo(partes, IDX_C170_ICMS["aliq_cofins"])
                    ),
                    "vl_cofins": to_decimal(
                        campo(partes, IDX_C170_ICMS["vl_cofins"])
                    ),

                    "origem": "ICMS_IPI_C170",
                }

                itens.append(item)

    return itens