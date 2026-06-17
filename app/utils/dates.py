from __future__ import annotations

from typing import Optional
from decimal import Decimal
from app.utils.numbers import buscar_valor_bloco_m, to_decimal


def normalizar_periodo(periodo: Optional[str]) -> Optional[str]:
    """
    Normaliza período para formato YYYYMM.

    Aceita:
    - YYYYMM
    - MMYYYY
    """

    if not periodo:
        return None

    periodo = str(periodo).strip()

    if len(periodo) != 6 or not periodo.isdigit():
        return None

    # já YYYYMM
    ano = int(periodo[:4])
    mes = int(periodo[4:])

    if 1900 <= ano <= 2100 and 1 <= mes <= 12:
        return periodo

    # tenta MMYYYY
    mes = int(periodo[:2])
    ano = int(periodo[2:])

    if 1 <= mes <= 12 and 1900 <= ano <= 2100:
        return f"{ano}{mes:02d}"

    return None

def periodo_fechamento_trimestre(periodo: str | None) -> str:
    periodo = str(periodo or "")

    if len(periodo) != 6:
        return periodo

    ano = periodo[:4]
    mes = int(periodo[4:6])

    if mes <= 3:
        return f"{ano}03"
    if mes <= 6:
        return f"{ano}06"
    if mes <= 9:
        return f"{ano}09"

    return f"{ano}12"


def meses_do_trimestre(periodo_trim: str) -> list[str]:
    periodo_trim = str(periodo_trim or "")

    if len(periodo_trim) != 6:
        return [periodo_trim]

    ano = periodo_trim[:4]
    mes = int(periodo_trim[4:6])

    if mes <= 3:
        return [f"{ano}01", f"{ano}02", f"{ano}03"]
    if mes <= 6:
        return [f"{ano}04", f"{ano}05", f"{ano}06"]
    if mes <= 9:
        return [f"{ano}07", f"{ano}08", f"{ano}09"]

    return [f"{ano}10", f"{ano}11", f"{ano}12"]


def buscar_bloco_m_trimestre(ctx: dict, periodo_trim: str, nat: str) -> Decimal:
    total = Decimal("0.00")

    for periodo_mes in meses_do_trimestre(periodo_trim):
        total += buscar_valor_bloco_m(
            ctx=ctx,
            periodo=periodo_mes,
            nat=nat,
        )

    return total

def agregar_trimestral(ctx: dict) -> dict[str, dict]:
    por_chave = ctx.get("por_periodo_chave") or ctx.get("por_chave") or {}
    agregado = {}

    for item in por_chave.values():
        periodo = str(item.get("periodo") or "")
        trimestre = periodo_fechamento_trimestre(periodo)

        nat = str(item.get("nat_bc_cred") or "").zfill(2)
        categoria = item.get("categoria") or "NaoClassificado"


        chave = f"{trimestre}|{nat}|{categoria}"

        if chave not in agregado:
            agregado[chave] = {
                "trimestre": trimestre,
                "nat_bc_cred": nat,
                "categoria": categoria,
                "valor_ecd": Decimal("0.00"),
                "valor_creditado_c170": Decimal("0.00"),
                "valor_oportunidade_c170": Decimal("0.00"),
                "valor_creditado_f100": Decimal("0.00"),
                "valor_creditado_a170": Decimal("0.00"),
                "valor_sem_credito_a170": Decimal("0.00"),
                "qtd_contas": 0,
                "qtd_c170": 0,
                "qtd_f100": 0,
                "qtd_a170": 0,
                "exemplo_descricao": "",
                "exemplo_participante": "",
                "exemplo_cod_cta": "",
                "exemplo_cod_item": "",
                "exemplo_ncm": "",
                "exemplo_cfop": "",
            }

        agg = agregado[chave]

        for campo in [
            "exemplo_descricao",
            "exemplo_participante",
            "exemplo_cod_cta",
            "exemplo_cod_item",
            "exemplo_ncm",
            "exemplo_cfop",
        ]:
            if not agg.get(campo):
                agg[campo] = item.get(campo) or ""

        # ECD já vem no fechamento do trimestre. Evita triplicar.
        if periodo == trimestre:
            agg["valor_ecd"] += to_decimal(item.get("valor_ecd"))
            agg["qtd_contas"] += int(item.get("qtd_contas") or 0)

        agg["valor_creditado_c170"] += to_decimal(item.get("valor_creditado_c170"))
        agg["valor_oportunidade_c170"] += to_decimal(item.get("valor_oportunidade_c170"))
        agg["valor_creditado_f100"] += to_decimal(item.get("valor_creditado_f100"))
        agg["valor_creditado_a170"] += to_decimal(item.get("valor_creditado_a170"))
        agg["valor_sem_credito_a170"] += to_decimal(item.get("valor_sem_credito_a170"))

        agg["qtd_c170"] += int(item.get("qtd_c170") or 0)
        agg["qtd_f100"] += int(item.get("qtd_f100") or 0)
        agg["qtd_a170"] += int(item.get("qtd_a170") or 0)

    return agregado
