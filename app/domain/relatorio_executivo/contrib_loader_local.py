from __future__ import annotations

from pathlib import Path
from decimal import Decimal
from collections import defaultdict

from app.utils.numbers import to_decimal
from app.utils.sped import ler_linhas_sped


def carregar_contrib_local(arquivos_contrib: list[Path]) -> dict:
    m100 = []
    m105 = []
    m500 = []
    m505 = []

    m100_atual = None
    m500_atual = None
    periodo_atual = None

    for arquivo in arquivos_contrib:
        print(f"[CONTRIB LOCAL] lendo: {arquivo}")

        m100_atual = None
        m500_atual = None

        for partes in ler_linhas_sped(arquivo):
            reg = partes[0] if partes else ""

            if reg == "0000":
                dt_ini = partes[6] if len(partes) > 6 else None
                if dt_ini and len(dt_ini) == 8:
                    periodo_atual = dt_ini[4:8] + dt_ini[2:4]

            if reg == "M100":
                m100_atual = {
                    "arquivo": arquivo.name,
                    "cod_cred": partes[1] if len(partes) > 1 else None,
                    "ind_cred_ori": partes[2] if len(partes) > 2 else None,
                    "vl_bc_pis": to_decimal(partes[3] if len(partes) > 3 else None),
                    "aliq_pis": to_decimal(partes[4] if len(partes) > 4 else None),
                    "quant_bc_pis": to_decimal(partes[5] if len(partes) > 5 else None),
                    "aliq_pis_quant": to_decimal(partes[6] if len(partes) > 6 else None),
                    "vl_cred": to_decimal(partes[7] if len(partes) > 7 else None),
                }
                m100.append(m100_atual)


            elif reg == "M105":

                nat = partes[1] if len(partes) > 1 else None

                m105.append({
                    "arquivo": arquivo.name,
                    "cod_cred": m100_atual.get("cod_cred") if m100_atual else None,
                    "nat_bc_cred": str(nat or "00").zfill(2),
                    "cst_pis": partes[2] if len(partes) > 2 else None,
                    "vl_bc_pis_tot": to_decimal(partes[3] if len(partes) > 3 else None),
                    "vl_bc_pis": to_decimal(partes[5] if len(partes) > 5 else None),
                    "vl_bc_pis_cum": to_decimal(partes[6] if len(partes) > 6 else None),
                    "periodo": periodo_atual,
                })

            elif reg == "M500":
                m500_atual = {
                    "arquivo": arquivo.name,
                    "cod_cred": partes[1] if len(partes) > 1 else None,
                    "ind_cred_ori": partes[2] if len(partes) > 2 else None,
                    "vl_bc_cofins": to_decimal(partes[3] if len(partes) > 3 else None),
                    "aliq_cofins": to_decimal(partes[4] if len(partes) > 4 else None),
                    "quant_bc_cofins": to_decimal(partes[5] if len(partes) > 5 else None),
                    "aliq_cofins_quant": to_decimal(partes[6] if len(partes) > 6 else None),
                    "vl_cred": to_decimal(partes[7] if len(partes) > 7 else None),
                }
                m500.append(m500_atual)

            elif reg == "M505":

                nat = partes[1] if len(partes) > 1 else None

                m505.append({
                    "arquivo": arquivo.name,
                    "cod_cred": m500_atual.get("cod_cred") if m500_atual else None,
                    "nat_bc_cred": str(nat or "00").zfill(2),
                    "cst_cofins": partes[2] if len(partes) > 2 else None,
                    "vl_bc_cofins_tot": to_decimal(partes[3] if len(partes) > 3 else None),
                    "vl_bc_cofins": to_decimal(partes[5] if len(partes) > 5 else None),
                    "vl_bc_cofins_cum": to_decimal(partes[6] if len(partes) > 6 else None),
                    "periodo": periodo_atual,
                })

    return {
        "m100": m100,
        "m105": m105,
        "m500": m500,
        "m505": m505,
    }


def montar_efd_por_natureza_local(contrib_ctx: dict) -> dict:
    resultado = defaultdict(lambda: {
        "nat_bc_cred": None,
        "base_pis": Decimal("0.00"),
        "base_cofins": Decimal("0.00"),
        "pis": Decimal("0.00"),
        "cofins": Decimal("0.00"),
        "efd_declarada": Decimal("0.00"),
        "periodos": set(),
    })

    for item in contrib_ctx.get("m105") or []:


        nat = str(item.get("nat_bc_cred") or "00").zfill(2)
        d = resultado[nat]

        d["nat_bc_cred"] = nat
        d["base_pis"] += to_decimal(item.get("vl_bc_pis"))

        if item.get("periodo"):
            d["periodos"].add(item.get("periodo"))

    for item in contrib_ctx.get("m505") or []:
        nat = str(item.get("nat_bc_cred") or "00").zfill(2)
        d = resultado[nat]

        d["nat_bc_cred"] = nat
        d["base_cofins"] += to_decimal(item.get("vl_bc_cofins"))

        if item.get("periodo"):
            d["periodos"].add(item.get("periodo"))

    for nat, d in resultado.items():
        d["efd_declarada"] = max(
            to_decimal(d.get("base_pis")),
            to_decimal(d.get("base_cofins")),
        )
        d["periodo"] = ", ".join(sorted(d["periodos"]))

    return dict(resultado)