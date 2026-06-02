from __future__ import annotations

from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import PatternFill

from app.utils.excel import criar_aba_generica
from app.utils.numbers import to_decimal


def criar_aba_cobertura_por_mes(
    wb: Workbook,
    ctx: dict,
) -> None:
    resumo = ctx.get("resumo") or {}

    periodo = ctx.get("periodo") or resumo.get("periodo")

    ecd = to_decimal(resumo.get("total_ecd_elegivel"))
    efd = to_decimal(resumo.get("total_efd_declarada"))
    gap = to_decimal(resumo.get("total_gap"))

    cobertura_pct = Decimal("0.00")
    if ecd > 0:
        cobertura_pct = ((efd / ecd) * Decimal("100")).quantize(Decimal("0.01"))

    status = "OK"
    if ecd > 0 and efd == 0:
        status = "SEM_EFD"
    elif ecd == 0 and efd > 0:
        status = "SEM_ECD"
    elif cobertura_pct < Decimal("70"):
        status = "BAIXA_COBERTURA"

    rows = [
        {
            "Período": periodo,
            "ECD Elegível": ecd,
            "EFD Declarada": efd,
            "GAP": gap,
            "Cobertura %": cobertura_pct,
            "Status": status,
            "Interpretação": (
                f"A EFD declarou {cobertura_pct}% da despesa elegível identificada na ECD."
            ),
        }
    ]

    ws = criar_aba_generica(
        wb,
        nome_aba = "CoberturaPorMes",
        headers = [
            "Período",
            "ECD Elegível",
            "EFD Declarada",
            "GAP",
            "Cobertura %",
            "Status",
            "Interpretação",
        ],
        rows = rows,
        money_cols = [
            "ECD Elegível",
            "EFD Declarada",
            "GAP",
        ],
    )

    fill_alerta = PatternFill("solid", fgColor="FFF2CC")  # amarelo claro

    for row in range(2, ws.max_row + 1):
        cobertura = ws.cell(row=row, column=5).value

        try:
            cobertura = float(cobertura or 0)
        except Exception:
            cobertura = 0

        if cobertura == 0:
            for col in range(1, ws.max_column + 1):
                ws.cell(row=row, column=col).fill = fill_alerta