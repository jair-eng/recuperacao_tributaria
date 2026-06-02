from __future__ import annotations

from openpyxl import Workbook

from app.utils.ecd_gap_status_utils import prioridade_por_status, diagnostico_texto, iter_items, categoria_diagnostico
from app.utils.excel import criar_aba_generica

def criar_aba_diagnostico_efd(
    wb: Workbook,
    ctx: dict,
) -> None:
    rows = []

    for item in iter_items(ctx.get("por_natureza")):
        status = item.get("status")

        rows.append(
            {
                "Período": item.get("periodo"),
                "NAT_BC_CRED": item.get("nat_bc_cred"),
                "Categoria": categoria_diagnostico(item),
                "ECD Elegível": item.get("ecd_elegivel"),
                "EFD Declarada": item.get("efd_declarada"),
                "GAP": item.get("gap"),
                "Cobertura %": item.get("cobertura_pct"),
                "Status": status,
                "Prioridade": prioridade_por_status(status),
                "Diagnóstico": diagnostico_texto(status),
            }
        )

    criar_aba_generica(
        wb,
        nome_aba="DiagnosticoEfd-ECD",
        headers=[
            "Período",
            "NAT_BC_CRED",
            "Categoria",
            "ECD Elegível",
            "EFD Declarada",
            "GAP",
            "Cobertura %",
            "Status",
            "Prioridade",
            "Diagnóstico",
        ],
        rows=rows,
    )