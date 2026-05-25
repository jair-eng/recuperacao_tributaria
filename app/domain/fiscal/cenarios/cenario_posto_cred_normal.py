# app/fiscal/cenarios/cenario_posto_credito_normal.py

from __future__ import annotations

from typing import Any, Dict

def cenario_posto_credito_normal(
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

    if dominio != "POSTO":
        out["justificativa"].append("dominio_nao_posto")
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

    # combustível normal do posto fica fora daqui
    # diesel/gasolina/etanol/glp podem ter tratamento próprio, LC192, monofásico etc.
    if produto["diesel"] or produto["gasolina"] or produto["etanol"] or produto["glp"]:
        out["justificativa"].append("combustivel_tratado_em_cenario_proprio")
        return out

    # No futuro, quando o contexto tiver saída tributada:
    # tributa_saida = bool(meta.get("tributa_saida_produto"))
    # if not tributa_saida:
    #     out["justificativa"].append("sem_evidencia_saida_tributada")
    #     return out

    if produto["lubrificante"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["POSTO_CREDITO_NORMAL_LUBRIFICANTE"]
        out["justificativa"] = [
            "entrada_credito_normal",
            "lubrificante",
            "dominio_posto",
        ]
        return out

    if produto["pneu"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["POSTO_CREDITO_NORMAL_PNEU"]
        out["justificativa"] = [
            "entrada_credito_normal",
            "pneu",
            "dominio_posto",
        ]
        return out

    if produto["filtro"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["POSTO_CREDITO_NORMAL_FILTRO"]
        out["justificativa"] = [
            "entrada_credito_normal",
            "filtro",
            "dominio_posto",
        ]
        return out

    if produto["arla32"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["POSTO_CREDITO_NORMAL_ARLA32"]
        out["justificativa"] = [
            "entrada_credito_normal",
            "arla32",
            "dominio_posto",
        ]
        return out

    if produto["aditivo_fluido"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["POSTO_CREDITO_NORMAL_ADITIVO_FLUIDO"]
        out["justificativa"] = [
            "entrada_credito_normal",
            "aditivo_fluido",
            "dominio_posto",
        ]
        return out

    if produto["manutencao_veicular"] or produto["autopeca"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["POSTO_CREDITO_NORMAL_MANUTENCAO_VEICULAR"]
        out["justificativa"] = [
            "entrada_credito_normal",
            "manutencao_veicular",
            "dominio_posto",
        ]
        return out

    if produto["posto_geral"]:
        out["ativo"] = True
        out["fundamento_legal"] = ["POSTO_CREDITO_NORMAL_GERAL"]
        out["justificativa"] = [
            "entrada_credito_normal",
            "posto_geral",
            "dominio_posto",
        ]
        return out

    return out