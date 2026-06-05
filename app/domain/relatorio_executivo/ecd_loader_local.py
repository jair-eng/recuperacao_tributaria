from __future__ import annotations

from pathlib import Path
from app.utils.numbers import to_decimal
from app.utils.sped import ler_linhas_sped, periodo_de_data_sped


def carregar_ecd_local(arquivos_ecd: list[Path]) -> dict:
    i050 = []
    i155 = []
    i355 = []
    i350 = []


    for arquivo in arquivos_ecd:
        i350_atual = None
        print(f"[ECD LOCAL] lendo: {arquivo}")

        for partes in ler_linhas_sped(arquivo):
            reg = partes[0] if partes else ""

            if reg == "I050":

                i050.append(
                    {
                        "arquivo": arquivo.name,
                        "dt_alt": partes[1] if len(partes) > 1 else None,
                        "cod_nat": partes[2] if len(partes) > 2 else None,
                        "ind_cta": partes[3] if len(partes) > 3 else None,
                        "nivel": partes[4] if len(partes) > 4 else None,
                        "cod_cta": partes[5] if len(partes) > 5 else None,
                        "cod_cta_sup": partes[6] if len(partes) > 6 else None,
                        "cta": partes[7] if len(partes) > 7 else None,
                    }
                )

            elif reg == "I155":
                i155.append(
                    {
                        "arquivo": arquivo.name,
                        "cod_cta": partes[1] if len(partes) > 1 else None,
                        "cod_ccus": partes[2] if len(partes) > 2 else None,
                        "vl_sld_ini": to_decimal(partes[3] if len(partes) > 3 else None),
                        "ind_dc_ini": partes[4] if len(partes) > 4 else None,
                        "vl_deb": to_decimal(partes[5] if len(partes) > 5 else None),
                        "vl_cred": to_decimal(partes[6] if len(partes) > 6 else None),
                        "vl_sld_fin": to_decimal(partes[7] if len(partes) > 7 else None),
                        "ind_dc_fin": partes[8] if len(partes) > 8 else None,
                    }
                )
            elif reg == "I350":
                i350_atual = {
                    "arquivo": arquivo.name,
                    "dt_res": partes[1] if len(partes) > 1 else None,
                }
                i350.append(i350_atual)

            elif reg == "I355":
                dt_res = i350_atual.get("dt_res") if i350_atual else None
                i355.append(
                    {
                        "arquivo": arquivo.name,
                        "dt_res": dt_res,
                        "periodo": periodo_de_data_sped(dt_res),
                        "cod_cta": partes[1] if len(partes) > 1 else None,
                        "cod_ccus": partes[2] if len(partes) > 2 else None,
                        "vl_cta": to_decimal(partes[3] if len(partes) > 3 else None),
                    }
                )

    print("[ECD LOCAL] I050:", len(i050))
    print("[ECD LOCAL] I155:", len(i155))
    print("[ECD LOCAL] I350:", len(i350))
    print("[ECD LOCAL] I355:", len(i355))

    return {
        "i050": i050,
        "i155": i155,
        "i350": i350,
        "i355": i355,
    }