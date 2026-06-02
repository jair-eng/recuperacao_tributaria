from __future__ import annotations

from openpyxl import Workbook
from app.utils.excel import criar_aba_generica
from app.utils.ecd_gap_status_utils import (
    diagnostico_texto,
    prioridade_por_status, iter_items,
)


def criar_aba_investigar(
    wb: Workbook,
    ctx: dict,
) -> None:
    rows = []

    for item in iter_items(ctx.get("por_natureza")):
        status = item.get("status")

        if status not in {"SEM_EFD", "SEM_ECD", "PARCIAL", "EXCEDENTE_EFD"}:
            continue

        rows.append(
            {
                "Período": item.get("periodo"),
                "Prioridade": prioridade_por_status(status),
                "NAT_BC_CRED": item.get("nat_bc_cred"),
                "Categoria": item.get("categoria"),
                "Contas": item.get("contas_ecd"),
                "ECD Elegível": item.get("ecd_elegivel"),
                "EFD Declarada": item.get("efd_declarada"),
                "GAP": item.get("gap"),
                "Cobertura %": item.get("cobertura_pct"),
                "Status": status,
                "Diagnóstico": diagnostico_texto(status),
            }
        )

    criar_aba_generica(
        wb,
        nome_aba="Investigar",
        headers=[
            "Período",
            "Prioridade",
            "NAT_BC_CRED",
            "Categoria",
            "Contas",
            "ECD Elegível",
            "EFD Declarada",
            "GAP",
            "Cobertura %",
            "Status",
            "Diagnóstico",
        ],
        rows=rows,
    )