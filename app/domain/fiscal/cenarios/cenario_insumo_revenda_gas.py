from __future__ import annotations

from typing import Any, Dict


def cenario_insumo_revenda_gas(
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

    if dominio != "REVENDA_GAS":
        out["justificativa"].append("dominio_nao_revenda_gas")
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

    # GLP fica fora daqui
    if produto["glp"]:
        out["justificativa"].append("glp_tratado_em_cenario_proprio")
        return out

    if produto["combustivel"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["REVENDA_GAS_INSUMO_COMBUSTIVEL"]
        out["justificativa"] = [
            "entrada_insumo",
            "combustivel_exceto_glp",
            "dominio_revenda_gas",
        ]
        return out

    if produto["lubrificante"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["REVENDA_GAS_INSUMO_LUBRIFICANTE"]
        out["justificativa"] = [
            "entrada_insumo",
            "lubrificante",
            "dominio_revenda_gas",
        ]
        return out

    if produto["pneu"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["REVENDA_GAS_INSUMO_PNEU"]
        out["justificativa"] = [
            "entrada_insumo",
            "pneu",
            "dominio_revenda_gas",
        ]
        return out

    if produto["filtro"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["REVENDA_GAS_INSUMO_FILTRO"]
        out["justificativa"] = [
            "entrada_insumo",
            "filtro",
            "dominio_revenda_gas",
        ]
        return out

    if produto["arla32"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["REVENDA_GAS_INSUMO_ARLA32"]
        out["justificativa"] = [
            "entrada_insumo",
            "arla32",
            "dominio_revenda_gas",
        ]
        return out

    if produto["manutencao_veicular"] or produto["autopeca"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["REVENDA_GAS_INSUMO_MANUTENCAO_VEICULAR"]
        out["justificativa"] = [
            "entrada_insumo",
            "manutencao_veicular",
            "dominio_revenda_gas",
        ]
        return out

    return out