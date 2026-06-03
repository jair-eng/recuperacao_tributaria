from __future__ import annotations

from openpyxl import Workbook
from app.utils.excel import criar_aba_generica


def criar_aba_categoria(
    wb: Workbook,
    *,
    nome_aba: str,
    categoria: str,
    linhas: list[dict],
) -> None:
    rows = []

    for item in linhas:
        if item.get("categoria") != categoria:
            continue

        rows.append(
            {
                "Ano-Mês": item.get("periodo"),
                "Código Conta": item.get("cod_cta"),
                "Descrição": item.get("nome_cta"),
                "Categoria": item.get("categoria"),
                "Fundamento": item.get("fundamento"),
                "Despesa Contábil": item.get("valor"),
                "Base Atribuída": item.get("base_atribuida"),
                "Gap Atribuído": item.get("gap_atribuido"),
                "Crédito PIS": item.get("credito_pis"),
                "Crédito COFINS": item.get("credito_cofins"),
                "Total Recuperável": item.get("total_recuperavel"),
                "Fonte": item.get("origem_classificacao") or item.get("origem"),
                "Confiança": item.get("confianca"),
                "Observação": item.get("observacao"),
            }
        )

    if not rows:
        return

    criar_aba_generica(
        wb,
        nome_aba=nome_aba[:31],
        headers=[
            "Ano-Mês",
            "Código Conta",
            "Descrição",
            "Categoria",
            "Fundamento",
            "Despesa Contábil",
            "Base Atribuída",
            "Gap Atribuído",
            "Crédito PIS",
            "Crédito COFINS",
            "Total Recuperável",
            "Fonte",
            "Confiança",
            "Observação",
        ],
        rows=rows,
    )