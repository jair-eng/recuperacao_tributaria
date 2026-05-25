
from __future__ import annotations

from typing import Any, Dict


def cenario_cafe(
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

    if not produto.get("cafe"):
        out["justificativa"].append("produto_nao_cafe")
        return out

    if not operacao.get("entrada_cafe"):
        out["justificativa"].append("operacao_nao_entrada_cafe")
        return out

    if operacao.get("transferencia"):
        out["justificativa"].append("transferencia")
        return out

    if operacao.get("entrada_imobilizado") or operacao.get("imobilizado"):
        out["justificativa"].append("imobilizado")
        return out

    if operacao.get("servico"):
        out["justificativa"].append("servico")
        return out

    # -----------------------------------
    # Cenário ativo
    # -----------------------------------

    out["ativo"] = True

    out["fundamento_legal"] = [
        "CAFE_OPERACAO_PRINCIPAL",
    ]

    out["justificativa"] = [
        "dominio_cafe",
        "produto_cafe",
        "entrada_cafe",
    ]

    return out