from __future__ import annotations

from openpyxl import Workbook

from app.utils.ecd_observacao_utils import montar_observacao_detalhe
from app.utils.excel import criar_aba_generica
from app.utils.numbers import to_decimal


def criar_aba_investigar(
    wb: Workbook,
    ctx: dict,
) -> None:
    rows = []

    for item in ctx.get("linhas_ecd", []):
        categoria = item.get("categoria")
        fundamento = item.get("fundamento")
        nat = str(item.get("nat_bc_cred") or "").zfill(2)

        deve_investigar = (
            not categoria
            or categoria == "NaoClassificado"
            or fundamento == "Investigar"
            or nat == "00"
        )

        if not deve_investigar:
            continue

        rows.append(
            {
                "Período": item.get("periodo"),
                "Código Conta": item.get("cod_cta"),
                "Descrição": item.get("nome_cta"),
                "Despesa Contábil": to_decimal(item.get("valor")),
                "Categoria": categoria or "NaoClassificado",
                "Grupo": item.get("grupo") or "NAO_CLASSIFICADO",
                "Fundamento": fundamento or "Investigar",
                "Confiança": item.get("confianca") or 50,
                "Fonte": item.get("origem_classificacao") or "Heurística",
                "Origem Valor": item.get("origem_valor") or item.get("origem"),
                "Motivo": "Conta sem correspondência em categoria elegível do catálogo fiscal.",
                "Observação": montar_observacao_detalhe(item=item, status=None),
            }
        )

    criar_aba_generica(
        wb,
        nome_aba="Investigar",
        headers=[
            "Período",
            "Código Conta",
            "Descrição",
            "Despesa Contábil",
            "Categoria",
            "Grupo",
            "Fundamento",
            "Confiança",
            "Fonte",
            "Origem Valor",
            "Motivo",
            "Observação",
        ],
        rows=rows,
        money_cols=[
            "Despesa Contábil",
        ],
    )