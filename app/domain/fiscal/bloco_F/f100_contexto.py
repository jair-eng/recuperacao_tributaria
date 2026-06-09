from __future__ import annotations

from typing import Any
from app.domain.ecd.ecd_conta_classificador_service import classificar_texto_por_natureza_esperada
from app.utils.numbers import to_decimal


def filtrar_f100(
    registros_f100: list[dict[str, Any]],
    *,
    participante_tipo: str | None = None,
    cst_pis: str | None = None,
    cst_cofins: str | None = None,
    nat_bc_cred: str | None = None,
) -> list[dict[str, Any]]:
    itens = registros_f100

    if participante_tipo:
        itens = [
            item for item in itens
            if str(item.get("participante_tipo") or "").upper() == participante_tipo.upper()
        ]

    if cst_pis:
        itens = [
            item for item in itens
            if str(item.get("cst_pis") or "").zfill(2) == str(cst_pis).zfill(2)
        ]

    if cst_cofins:
        itens = [
            item for item in itens
            if str(item.get("cst_cofins") or "").zfill(2) == str(cst_cofins).zfill(2)
        ]

    if nat_bc_cred:
        itens = [
            item for item in itens
            if str(item.get("nat_bc_cred") or "").zfill(2) == str(nat_bc_cred).zfill(2)
        ]

    return itens


def somar_f100(
    registros_f100: list[dict[str, Any]],
    campo: str = "vl_oper",
):
    total = 0

    for item in registros_f100:
        total += to_decimal(item.get(campo))

    return total


def agregar_f100_por_participante(
    registros_f100: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, Any]] = {}

    for item in registros_f100:
        cod_part = item.get("cod_part") or "SEM_COD_PART"
        nome = item.get("participante_nome") or "NÃO IDENTIFICADO"
        cnpj = item.get("participante_cnpj") or ""
        cpf = item.get("participante_cpf") or ""
        tipo = item.get("participante_tipo") or "N/I"

        chave = f"{cod_part}|{cnpj}|{cpf}"

        if chave not in agg:
            agg[chave] = {
                "cod_part": cod_part,
                "participante_nome": nome,
                "participante_cnpj": cnpj,
                "participante_cpf": cpf,
                "participante_tipo": tipo,
                "qtd_f100": 0,
                "vl_oper": 0,
                "vl_bc_pis": 0,
                "vl_pis": 0,
                "vl_bc_cofins": 0,
                "vl_cofins": 0,
            }

        agg[chave]["qtd_f100"] += 1
        agg[chave]["vl_oper"] += to_decimal(item.get("vl_oper"))
        agg[chave]["vl_bc_pis"] += to_decimal(item.get("vl_bc_pis"))
        agg[chave]["vl_pis"] += to_decimal(item.get("vl_pis"))
        agg[chave]["vl_bc_cofins"] += to_decimal(item.get("vl_bc_cofins"))
        agg[chave]["vl_cofins"] += to_decimal(item.get("vl_cofins"))

    return sorted(
        agg.values(),
        key=lambda x: x["vl_oper"],
        reverse=True,
    )

def classificar_registro_f100_por_natureza(
    *,
    db,
    item: dict,
) -> dict:
    texto = " ".join([
        str(item.get("desc_doc_oper") or ""),
        str(item.get("participante_nome") or ""),
        str(item.get("participante_tipo") or ""),
    ])

    classificacao = classificar_texto_por_natureza_esperada(
        db=db,
        texto=texto,
        cod_nat="",
        participante_tipo=item.get("participante_tipo"),
        nat_bc_cred=item.get("nat_bc_cred"),
    )

    return {
        **item,
        "classificacao_natureza": classificacao,
        "categoria": classificacao.get("categoria"),
        "grupo": classificacao.get("grupo"),
        "naturezas_esperadas": classificacao.get("naturezas_esperadas") or [],
        "fundamento": classificacao.get("fundamento"),
        "confianca": classificacao.get("confianca"),
    }


def montar_contexto_f100(
    registros_f100: list[dict[str, Any]],
    *,
    db=None,
    fonte: str = "LOCAL",
) -> dict[str, Any]:
    f100_pf = filtrar_f100(registros_f100, participante_tipo="PF")
    f100_pj = filtrar_f100(registros_f100, participante_tipo="PJ")
    f100_ni = filtrar_f100(registros_f100, participante_tipo="N/I")

    if db:
        registros_f100 = [
            classificar_registro_f100_por_natureza(
                db=db,
                item=item,
            )
            for item in registros_f100
        ]

    f100_cst60_nat14 = filtrar_f100(
        registros_f100,
        cst_pis="60",
        cst_cofins="60",
        nat_bc_cred="14",
    )

    f100_pf_cst60_nat14 = filtrar_f100(
        f100_pf,
        cst_pis="60",
        cst_cofins="60",
        nat_bc_cred="14",
    )

    f100_pj_cst60_nat14 = filtrar_f100(
        f100_pj,
        cst_pis="60",
        cst_cofins="60",
        nat_bc_cred="14",
    )

    return {
        "fonte": fonte,
        "registros": registros_f100,

        "qtd_f100": len(registros_f100),
        "qtd_pf": len(f100_pf),
        "qtd_pj": len(f100_pj),
        "qtd_ni": len(f100_ni),

        "vl_total": somar_f100(registros_f100, "vl_oper"),
        "vl_pf": somar_f100(f100_pf, "vl_oper"),
        "vl_pj": somar_f100(f100_pj, "vl_oper"),
        "vl_ni": somar_f100(f100_ni, "vl_oper"),

        "cst60_nat14": {
            "qtd": len(f100_cst60_nat14),
            "vl_oper": somar_f100(f100_cst60_nat14, "vl_oper"),
            "vl_bc_pis": somar_f100(f100_cst60_nat14, "vl_bc_pis"),
            "vl_pis": somar_f100(f100_cst60_nat14, "vl_pis"),
            "vl_bc_cofins": somar_f100(f100_cst60_nat14, "vl_bc_cofins"),
            "vl_cofins": somar_f100(f100_cst60_nat14, "vl_cofins"),

            "pf": {
                "qtd": len(f100_pf_cst60_nat14),
                "vl_oper": somar_f100(f100_pf_cst60_nat14, "vl_oper"),
                "vl_pis": somar_f100(f100_pf_cst60_nat14, "vl_pis"),
                "vl_cofins": somar_f100(f100_pf_cst60_nat14, "vl_cofins"),
            },

            "pj": {
                "qtd": len(f100_pj_cst60_nat14),
                "vl_oper": somar_f100(f100_pj_cst60_nat14, "vl_oper"),
                "vl_pis": somar_f100(f100_pj_cst60_nat14, "vl_pis"),
                "vl_cofins": somar_f100(f100_pj_cst60_nat14, "vl_cofins"),
            },
        },

        "top_participantes": agregar_f100_por_participante(registros_f100),
        "top_pf": agregar_f100_por_participante(f100_pf),
        "top_pj": agregar_f100_por_participante(f100_pj),
    }