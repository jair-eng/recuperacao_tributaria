from __future__ import annotations

from pathlib import Path
from typing import Any
from app.utils.ecd_gap_utils import get
from app.utils.numbers import to_decimal
from app.utils.sped import ler_linhas_sped


def carregar_a170_local(
    arquivos_contrib: list[Path],
) -> list[dict[str, Any]]:
    registros: list[dict[str, Any]] = []

    periodo_atual = None
    a100_atual = None

    for arquivo in arquivos_contrib:
        a100_atual = None

        for partes in ler_linhas_sped(arquivo):
            reg = get(partes, 0, "")

            if reg == "0000":
                dt_ini = get(partes, 6)
                if dt_ini and len(dt_ini) == 8:
                    periodo_atual = dt_ini[4:8] + dt_ini[2:4]

            elif reg == "A100":
                a100_atual = {
                    "arquivo": arquivo.name,
                    "ind_oper": get(partes, 1),
                    "ind_emit": get(partes, 2),
                    "cod_part": get(partes, 3),
                    "cod_sit": get(partes, 4),
                    "ser": get(partes, 5),
                    "sub": get(partes, 6),
                    "num_doc": get(partes, 7),
                    "chv_nfse": get(partes, 8),
                    "dt_doc": get(partes, 9),
                    "dt_exe_serv": get(partes, 10),
                    "vl_doc": to_decimal(get(partes, 11)),
                    "ind_pgto": get(partes, 12),
                    "vl_desc": to_decimal(get(partes, 13)),
                    "vl_bc_pis": to_decimal(get(partes, 14)),
                    "vl_pis": to_decimal(get(partes, 15)),
                    "vl_bc_cofins": to_decimal(get(partes, 16)),
                    "vl_cofins": to_decimal(get(partes, 17)),
                    "vl_pis_ret": to_decimal(get(partes, 18)),
                    "vl_cofins_ret": to_decimal(get(partes, 19)),
                    "vl_iss": to_decimal(get(partes, 20)),
                }

            elif reg == "A170":
                if not a100_atual:
                    continue

                vl_pis = to_decimal(get(partes, 11))
                vl_cofins = to_decimal(get(partes, 15))

                registros.append({
                    "origem": "CONTRIB_A170",
                    "arquivo": arquivo.name,
                    "periodo": periodo_atual,

                    "ind_oper": a100_atual.get("ind_oper"),
                    "ind_emit": a100_atual.get("ind_emit"),
                    "cod_part": a100_atual.get("cod_part"),
                    "cod_sit": a100_atual.get("cod_sit"),
                    "ser": a100_atual.get("ser"),
                    "sub": a100_atual.get("sub"),
                    "num_doc": a100_atual.get("num_doc"),
                    "chv_nfse": a100_atual.get("chv_nfse"),
                    "dt_doc": a100_atual.get("dt_doc"),
                    "dt_exe_serv": a100_atual.get("dt_exe_serv"),
                    "vl_doc": a100_atual.get("vl_doc"),

                    "num_item": get(partes, 1),
                    "cod_item": get(partes, 2),
                    "descr_compl": get(partes, 3),
                    "vl_item": to_decimal(get(partes, 4)),
                    "vl_desc": to_decimal(get(partes, 5)),
                    "nat_bc_cred": str(get(partes, 6) or "").zfill(2) if get(partes, 6) else "",
                    "ind_orig_cred": get(partes, 7),

                    "cst_pis": get(partes, 8),
                    "vl_bc_pis": to_decimal(get(partes, 9)),
                    "aliq_pis": to_decimal(get(partes, 10)),
                    "vl_pis": vl_pis,

                    "cst_cofins": get(partes, 12),
                    "vl_bc_cofins": to_decimal(get(partes, 13)),
                    "aliq_cofins": to_decimal(get(partes, 14)),
                    "vl_cofins": vl_cofins,

                    "cod_cta": get(partes, 16),
                    "cod_ccus": get(partes, 17),

                    "tem_credito_pis": vl_pis > 0,
                    "tem_credito_cofins": vl_cofins > 0,
                    "tem_credito": vl_pis > 0 or vl_cofins > 0,
                })

    return registros