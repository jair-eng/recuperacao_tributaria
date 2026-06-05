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
    rows = []
    mapa_nat = ctx.get("mapa_nat_bc_cred") or {}

    for nat, dados in sorted((ctx.get("por_natureza") or {}).items()):
        periodo = dados.get("periodo")
        ecd = to_decimal(dados.get("ecd_elegivel"))
        efd = to_decimal(dados.get("efd_declarada"))
        gap = to_decimal(dados.get("gap"))
        status = dados.get("status")

        cobertura_pct = Decimal("0.00")
        if ecd > 0:
            cobertura_pct = ((efd / ecd) * Decimal("100")).quantize(Decimal("0.01"))

        if not status:
            if ecd > 0 and efd == 0:
                status = "SEM_EFD"
            elif ecd == 0 and efd > 0:
                status = "SEM_ECD"
            elif ecd > 0 and efd < ecd:
                status = "BAIXA_COBERTURA"
            else:
                status = "OK"

        rows.append({
            "Período": periodo,
            "NAT_BC_CRED": nat,
            "Categoria": dados.get("categoria") or mapa_nat.get(nat, ""),
            "ECD Elegível": ecd,
            "EFD Declarada": efd,
            "GAP": gap,
            "Cobertura %": cobertura_pct,
            "Status": status,
            "Interpretação": (
                f"A EFD declarou {cobertura_pct}% da despesa elegível identificada na ECD para a natureza {nat}."
                if ecd > 0
                else "Existe base declarada na EFD sem despesa elegível ECD correspondente para esta natureza."
            ),
        })

    ws = criar_aba_generica(
        wb,
        nome_aba="Cobertura Por Mes",
        headers=[
            "Período",
            "NAT_BC_CRED",
            "Categoria",
            "ECD Elegível",
            "EFD Declarada",
            "GAP",
            "Cobertura %",
            "Status",
            "Interpretação",
        ],
        rows=rows,
        money_cols=[
            "ECD Elegível",
            "EFD Declarada",
            "GAP",
        ],
    )