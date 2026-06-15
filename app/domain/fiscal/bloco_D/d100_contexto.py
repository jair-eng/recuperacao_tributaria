from __future__ import annotations

from typing import Any
from app.domain.fiscal.bloco_D.d100_match import match_d100_icms_contrib
from app.utils.numbers import to_decimal


def soma_valor_d100(itens, lado: str):
    total = 0

    for item in itens:
        d100 = item.get(lado) or {}
        total += to_decimal(d100.get("vl_serv") or d100.get("vl_doc"))

    return total

def filtrar_d100_por_ind_oper(itens, lado: str, ind_oper: str):
    filtrados = []

    for item in itens:
        d100 = item.get(lado) or {}

        if str(d100.get("ind_oper") or "").strip() == ind_oper:
            filtrados.append(item)

    return filtrados

def montar_contexto_d100(
    d100_icms: list[dict[str, Any]],
    d100_contrib: list[dict[str, Any]],
    *,
    fonte: str = "LOCAL",
) -> dict[str, Any]:
    """
    Monta contexto D100 cruzando ICMS/IPI x EFD Contribuições.

    Primeira versão:
    - matches
    - sem_contrib
    - sem_icms
    """

    matches: list[dict[str, Any]] = []
    sem_contrib: list[dict[str, Any]] = []
    sem_icms: list[dict[str, Any]] = []

    usados_contrib: set[int] = set()

    for item_icms in d100_icms:
        encontrado_idx = None
        encontrado_contrib = None

        for idx, item_contrib in enumerate(d100_contrib):
            if idx in usados_contrib:
                continue

            if match_d100_icms_contrib(item_icms, item_contrib):
                encontrado_idx = idx
                encontrado_contrib = item_contrib
                break

        if encontrado_contrib is not None:
            usados_contrib.add(encontrado_idx)

            matches.append(
                {
                    "icms": item_icms,
                    "contrib": encontrado_contrib,
                    "status": "MATCH",
                }
            )
        else:
            sem_contrib.append(
                {
                    "icms": item_icms,
                    "status": "SEM_CONTRIB",
                }
            )

    for idx, item_contrib in enumerate(d100_contrib):
        if idx not in usados_contrib:
            sem_icms.append(
                {
                    "contrib": item_contrib,
                    "status": "SEM_ICMS",
                }
            )
    pct_match = (
        round((len(matches) / len(d100_icms)) * 100, 2)
        if d100_icms
        else 0
    )

    pct_sem_contrib = (
        round((len(sem_contrib) / len(d100_icms)) * 100, 2)
        if d100_icms
        else 0
    )

    pct_sem_icms = (
        round((len(sem_icms) / len(d100_contrib)) * 100, 2)
        if d100_contrib
        else 0
    )

    matches_entrada = filtrar_d100_por_ind_oper(matches, "contrib", "0")
    sem_icms_entrada = filtrar_d100_por_ind_oper(sem_icms, "contrib", "0")
    sem_contrib_entrada = filtrar_d100_por_ind_oper(sem_contrib, "icms", "0")

    vl_matches_contrib_entrada = soma_valor_d100(matches_entrada, "contrib")
    vl_sem_icms_contrib_entrada = soma_valor_d100(sem_icms_entrada, "contrib")
    vl_sem_contrib_icms_entrada = soma_valor_d100(sem_contrib_entrada, "icms")

    return {
        "fonte": fonte,
        "matches": matches,
        "sem_contrib": sem_contrib,
        "sem_icms": sem_icms,

        "qtd_icms": len(d100_icms),
        "qtd_contrib": len(d100_contrib),
        "qtd_matches": len(matches),
        "qtd_sem_contrib": len(sem_contrib),
        "qtd_sem_icms": len(sem_icms),

        "vl_matches_icms": soma_valor_d100(matches, "icms"),
        "vl_sem_contrib_icms": soma_valor_d100(sem_contrib, "icms"),
        "vl_sem_icms_contrib": soma_valor_d100(sem_icms, "contrib"),

        "entradas": {
            "qtd_matches": len(matches_entrada),
            "qtd_sem_icms": len(sem_icms_entrada),
            "qtd_sem_contrib": len(sem_contrib_entrada),

            # Base já escriturada na EFD Contribuições
            "vl_efd_contrib": (
                    vl_matches_contrib_entrada
                    + vl_sem_icms_contrib_entrada
            ),

            # Está no ICMS, mas não apareceu na EFD Contribuições
            "vl_icms_sem_contrib": vl_sem_contrib_icms_entrada,

            "vl_matches_contrib": vl_matches_contrib_entrada,
            "vl_sem_icms_contrib": vl_sem_icms_contrib_entrada,
            "vl_sem_contrib_icms": vl_sem_contrib_icms_entrada,
        },

        "indicadores": {
            "pct_match": pct_match,
            "pct_sem_contrib": pct_sem_contrib,
            "pct_sem_icms": pct_sem_icms,
        },

        "agregacoes": {
            "sem_contrib_por_participante": agregar_d100_por_participante(
                sem_contrib,
                "icms",
            ),
            "matches_por_participante": agregar_d100_por_participante(
                matches,
                "icms",
            ),
            "sem_icms_por_participante": agregar_d100_por_participante(
                sem_icms,
                "contrib",
            ),
        },
    }

def agregar_d100_por_participante(itens, lado: str):
    agg = {}

    for item in itens:
        d100 = item.get(lado) or {}

        cod_part = d100.get("cod_part") or "SEM_COD_PART"
        nome = d100.get("participante_nome") or "NÃO IDENTIFICADO"
        cnpj = d100.get("participante_cnpj") or ""
        cpf = d100.get("participante_cpf") or ""
        tipo = d100.get("participante_tipo") or "N/I"

        chave = f"{cod_part}|{cnpj}|{cpf}"

        if chave not in agg:
            agg[chave] = {
                "cod_part": cod_part,
                "participante_nome": nome,
                "participante_cnpj": cnpj,
                "participante_cpf": cpf,
                "participante_tipo": tipo,
                "qtd_d100": 0,
                "vl_total": 0,
            }

        agg[chave]["qtd_d100"] += 1
        agg[chave]["vl_total"] += to_decimal(
            d100.get("vl_serv") or d100.get("vl_doc")
        )

    return sorted(
        agg.values(),
        key=lambda x: x["vl_total"],
        reverse=True,
    )