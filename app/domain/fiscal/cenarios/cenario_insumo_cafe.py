
from __future__ import annotations

from typing import Any, Dict


def cenario_insumo_cafe(
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

    # -----------------------------------
    # Gates básicos
    # -----------------------------------

    if dominio != "CAFE":
        out["justificativa"].append("dominio_nao_cafe")
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

    # -----------------------------------
    # Fertilizante
    # -----------------------------------

    if produto["fertilizante"]:

        out["ativo"] = True

        out["fundamento_legal"] = [
            "CAFE_INSUMO_FERTILIZANTE",
        ]

        out["justificativa"] = [
            "entrada_insumo",
            "fertilizante",
            "dominio_cafe",
        ]

        return out

    # -----------------------------------
    # Combustível
    # -----------------------------------

    if produto["combustivel"]:

        out["ativo"] = True

        out["fundamento_legal"] = [
            "CAFE_INSUMO_COMBUSTIVEL",
        ]

        out["justificativa"] = [
            "entrada_insumo",
            "combustivel",
            "dominio_cafe",
        ]

        return out

    # -----------------------------------
    # Embalagem
    # -----------------------------------

    if produto["embalagem"]:

        out["ativo"] = True

        out["fundamento_legal"] = [
            "CAFE_INSUMO_EMBALAGEM",
        ]

        out["justificativa"] = [
            "entrada_insumo",
            "embalagem",
            "dominio_cafe",
        ]

        return out

    return out