from __future__ import annotations

from openpyxl import Workbook

from app.utils.ecd_gap_status_utils import classificar_alerta, descricao_alerta, iter_items
from app.utils.excel import criar_aba_generica




def criar_aba_alertas_efd_omissao(
    wb: Workbook,
    ctx: dict,
) -> None:
    rows = []

    for item in iter_items(ctx.get("por_natureza")):
        tipo_alerta = classificar_alerta(item)

        if not tipo_alerta:
            continue

        rows.append(
            {
                "Período": item.get("periodo"),
                "Tipo Alerta": tipo_alerta,
                "NAT_BC_CRED": item.get("nat_bc_cred"),
                "Categoria": item.get("categoria"),
                "ECD Elegível": item.get("ecd_elegivel"),
                "EFD Declarada": item.get("efd_declarada"),
                "GAP": item.get("gap"),
                "Cobertura %": item.get("cobertura_pct"),
                "Status Natureza": item.get("status"),
                "Descrição": descricao_alerta(tipo_alerta),
            }
        )

    criar_aba_generica(
        wb,
        nome_aba="AlertasEfdOmissao",
        headers=[
            "Período",
            "Tipo Alerta",
            "NAT_BC_CRED",
            "Categoria",
            "ECD Elegível",
            "EFD Declarada",
            "GAP",
            "Cobertura %",
            "Status Natureza",
            "Descrição",
        ],
        rows=rows,
    )