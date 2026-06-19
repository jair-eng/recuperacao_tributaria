from __future__ import annotations

from decimal import Decimal
from openpyxl import Workbook

from app.utils.dates import agregar_trimestral
from app.utils.excel import criar_aba_generica
from app.utils.numbers import to_decimal


def criar_aba_investigar(
    wb: Workbook,
    ctx: dict,
) -> None:
    rows = []

    mapa_nat = ctx.get("mapa_nat_bc_cred") or {}
    agregado = agregar_trimestral(ctx)

    for item in sorted(
        agregado.values(),
        key=lambda x: (
            x.get("trimestre") or "",
            x.get("nat_bc_cred") or "",
            x.get("categoria") or "",
        ),
    ):
        categoria = item.get("categoria") or "NaoClassificado"

        if categoria != "NaoClassificado":
            continue

        nat = str(item.get("nat_bc_cred") or "00").zfill(2)

        valor_c170 = to_decimal(item.get("valor_creditado_c170"))
        valor_oportunidade_c170 = to_decimal(item.get("valor_oportunidade_c170"))
        valor_f100 = to_decimal(item.get("valor_creditado_f100"))
        valor_a170 = to_decimal(item.get("valor_creditado_a170"))
        valor_sem_credito_a170 = to_decimal(item.get("valor_sem_credito_a170"))

        total_creditado = valor_c170 + valor_f100 + valor_a170
        total_documentado = (
            total_creditado
            + valor_oportunidade_c170
            + valor_sem_credito_a170
        )

        rows.append(
            {
                "Ano-Trimestre": item.get("trimestre"),
                "Cód. Nat.": nat,
                "Natureza": mapa_nat.get(nat, ""),
                "Categoria": categoria,
                "C170 Creditado": valor_c170,
                "C170 Oportunidade": valor_oportunidade_c170,
                "F100 Creditado": valor_f100,
                "A170 Creditado": valor_a170,
                "Total Creditado": total_creditado,
                "Total Documentado": total_documentado,
                "Qtd Contas": int(item.get("qtd_contas") or 0),
                "Qtd C170": int(item.get("qtd_c170") or 0),
                "Qtd F100": int(item.get("qtd_f100") or 0),
                "Qtd A170": int(item.get("qtd_a170") or 0),
                "Motivo": "Valores agregados sem categoria fiscal classificada.",
                "Exemplo Descrição": item.get("exemplo_descricao") or "",
                "Exemplo Participante": item.get("exemplo_participante") or "",
                "Exemplo Conta": item.get("exemplo_cod_cta") or "",
                "Exemplo Item": item.get("exemplo_cod_item") or "",
                "Exemplo NCM": item.get("exemplo_ncm") or "",
                "Exemplo CFOP": item.get("exemplo_cfop") or "",
            }
        )

    criar_aba_generica(
        wb,
        nome_aba="Investigar",
        headers=[
            "Ano-Trimestre",
            "Cód. Nat.",
            "Categoria",
            "C170 Creditado",
            "F100 Creditado",
            "A170 Creditado",
            "Total Documentado",
            "Exemplo Descrição",
            "Exemplo Conta",
            "Exemplo NCM",
            "Motivo",
        ],
        rows=rows,
        money_cols=[

            "C170 Creditado",
            "C170 Oportunidade",
            "F100 Creditado",
            "A170 Creditado",
            "Total Creditado",
            "Total Documentado",
        ],

    )