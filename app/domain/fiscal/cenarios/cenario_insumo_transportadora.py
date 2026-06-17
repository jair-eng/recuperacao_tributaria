
from __future__ import annotations

from typing import Any, Dict
from app.utils.lc192_utils import eh_periodo_lc192


def cenario_insumo_transportadora(
    meta: Dict[str, Any],
    classificacao: Dict[str, Any],
) -> Dict[str, Any]:

    dominio = meta.get("dominio")
    operacao = classificacao["operacao"]
    produto = classificacao["produto"]

    out = {
        "ativo": False,
        "fundamento_legal": [],
        "justificativa": [],
    }

    if dominio != "TRANSP":
        out["justificativa"].append("dominio_nao_transportadora")
        return out

    if not operacao["entrada"]:
        out["justificativa"].append("nao_entrada")
        return out

    if operacao["transferencia"]:
        out["justificativa"].append("transferencia")
        return out

    if operacao["imobilizado"]:
        out["justificativa"].append("imobilizado")
        return out

    if operacao["servico"]:
        out["justificativa"].append("servico")
        return out

    if produto["diesel"]:

        periodo = (
                meta.get("periodo")
                or meta.get("dt_ini")
                or meta.get("dt_doc")
                or meta.get("data_doc")
        )

        if eh_periodo_lc192(periodo):
            out["justificativa"].append("diesel_tratado_pela_lc192")
            return out

        out["ativo"] = True
        out["fundamento_legal"] = ["TRANSP_INSUMO_DIESEL"]
        out["justificativa"] = [
            "entrada_insumo",
            "diesel",
            "dominio_transportadora",
        ]
        return out

    if produto["gasolina"]:

        periodo = (
                meta.get("periodo")
                or meta.get("dt_ini")
                or meta.get("dt_doc")
                or meta.get("data_doc")
        )

        if eh_periodo_lc192(periodo):
            out["justificativa"].append("gasolina_tratado_pela_lc192")
            return out

        out["ativo"] = True
        out["fundamento_legal"] = ["TRANSP_INSUMO_GASOLINA"]
        out["justificativa"] = [
            "entrada_insumo",
            "gasolina",
            "dominio_transportadora",
        ]
        return out

    if produto["lubrificante"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["TRANSP_INSUMO_LUBRIFICANTE"]
        out["justificativa"] = [
            "entrada_insumo",
            "lubrificante",
            "dominio_transportadora",
        ]
        return out

    if produto["pneu"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["TRANSP_INSUMO_PNEU"]
        out["justificativa"] = [
            "entrada_insumo",
            "pneu",
            "dominio_transportadora",
        ]
        return out

    if produto["filtro"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["TRANSP_INSUMO_FILTRO"]
        out["justificativa"] = [
            "entrada_insumo",
            "filtro",
            "dominio_transportadora",
        ]
        return out

    if produto["arla32"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["TRANSP_INSUMO_ARLA32"]
        out["justificativa"] = [
            "entrada_insumo",
            "arla32",
            "dominio_transportadora",
        ]
        return out

    if produto["manutencao_veicular"] or produto["autopeca"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["TRANSP_INSUMO_MANUTENCAO_VEICULAR"]
        out["justificativa"] = [
            "entrada_insumo",
            "manutencao_veicular",
            "dominio_transportadora",
        ]
        return out

    return out