from __future__ import annotations

from typing import Any, Dict

def cenario_ativo_imobilizado(
    meta: Dict[str, Any],
    classificacao: Dict[str, Any],
) -> Dict[str, Any]:

    operacao = classificacao["operacao"]
    produto = classificacao["produto"]

    out = {
        "ativo": False,
        "fundamento_legal": [],
        "justificativa": [],
    }

    if operacao["transferencia"]:
        out["justificativa"].append("transferencia")
        return out

    if not operacao["imobilizado"]:
        out["justificativa"].append("nao_imobilizado")
        return out

    if not produto["ativo_imobilizado"]:
        out["justificativa"].append("produto_nao_imobilizado")
        return out

    out["ativo"] = True
    out["fundamento_legal"] = ["ATIVO_IMOBILIZADO"]
    out["justificativa"] = [
        "entrada_imobilizado",
        "produto_ativo_imobilizado",
    ]

    return out