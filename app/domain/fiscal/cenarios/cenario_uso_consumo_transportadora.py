from __future__ import annotations

from typing import Any, Dict


def cenario_uso_consumo_transportadora(
    meta: Dict[str, Any],
    classificacao: Dict[str, Any],
) -> Dict[str, Any]:

    dominio = meta.get("dominio")
    operacao = classificacao["operacao"]
    produto = classificacao["produto"]

    out = {
        "ativo": False,
        "cenario": "TRANSP_USO_CONSUMO",
        "fundamento_legal": [],
        "justificativa": [],
    }

    if dominio != "TRANSP":
        out["justificativa"].append("dominio_nao_transportadora")
        return out

    if not operacao["uso_consumo"]:
        out["justificativa"].append("nao_uso_consumo")
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
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_DIESEL"
        out["fundamento_legal"] = ["TRANSP_USO_CONSUMO_DIESEL"]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "diesel",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    if produto["gasolina"]:
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_GASOLINA"
        out["fundamento_legal"] = ["TRANSP_USO_CONSUMO_GASOLINA"]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "gasolina",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    if produto["etanol"]:
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_ETANOL"
        out["fundamento_legal"] = ["TRANSP_USO_CONSUMO_ETANOL"]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "etanol",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    if produto["arla32"]:
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_ARLA32"
        out["fundamento_legal"] = ["TRANSP_USO_CONSUMO_ARLA32"]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "arla32",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    if produto["lubrificante"]:
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_LUBRIFICANTE"
        out["fundamento_legal"] = ["TRANSP_USO_CONSUMO_LUBRIFICANTE"]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "lubrificante",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    if produto["pneu"]:
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_PNEU"
        out["fundamento_legal"] = ["TRANSP_USO_CONSUMO_PNEU"]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "pneu",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    if produto["filtro"]:
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_FILTRO"
        out["fundamento_legal"] = ["TRANSP_USO_CONSUMO_FILTRO"]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "filtro",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    if produto["manutencao_veicular"] or produto["autopeca"]:
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_MANUTENCAO_VEICULAR"
        out["fundamento_legal"] = [
            "TRANSP_USO_CONSUMO_MANUTENCAO_VEICULAR"
        ]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "manutencao_veicular",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    if produto["rastreamento_telemetria"]:
        out["ativo"] = True
        out["cenario"] = "TRANSP_USO_CONSUMO_RASTREAMENTO_TELEMETRIA"
        out["fundamento_legal"] = [
            "TRANSP_USO_CONSUMO_RASTREAMENTO_TELEMETRIA"
        ]
        out["justificativa"] = [
            "cfop_uso_consumo",
            "rastreamento_telemetria",
            "dominio_transportadora",
            "requer_analise_fiscal",
        ]
        return out

    out["justificativa"].append("produto_sem_tratamento_uso_consumo")
    return out