from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from app.config.settings import ALIQUOTA_PIS, ALIQUOTA_COFINS
from app.utils.ecd_gap_status_utils import iter_items
from app.utils.excel import autosize_columns
from app.utils.numbers import to_decimal


def criar_aba_resumo(
    wb: Workbook,
    ctx: dict,
    *,
    titulo: str = "Revisão Fiscal PIS/COFINS - Sumário Executivo",
) -> None:
    ws = wb.create_sheet("Resumo")


    ws.merge_cells("A1:G1")
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, color="FFFFFF", size=12)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws["A1"].fill = PatternFill("solid", fgColor="000080")

    headers = [
        "Categoria",
        "Despesa Contábil Total",
        "Base Atribuída EFD",
        "Gap Identificado",
        "Crédito Potencial PIS",
        "Crédito Potencial COFINS",
        "Total Recuperável",
    ]

    ws.append(headers)
    ws.freeze_panes = "A3"

    header_fill = PatternFill("solid", fgColor="D9D9D9")
    for cell in ws[2]:
        cell.font = Font(bold=True)
        cell.fill = header_fill

    por_categoria = defaultdict(lambda: Decimal("0.00"))

    for item in iter_items(ctx.get("linhas_ecd")):
        categoria = item.get("categoria") or "Investigar"
        valor = to_decimal(item.get("valor"))
        if valor > 0:
            por_categoria[categoria] += valor

    total_efd = to_decimal((ctx.get("resumo") or {}).get("total_efd_declarada"))
    total_despesa_categoria = sum(por_categoria.values(), Decimal("0.00"))

    total_ecd = Decimal("0.00")
    total_gap = Decimal("0.00")
    total_pis = Decimal("0.00")
    total_cofins = Decimal("0.00")
    total_recuperavel = Decimal("0.00")

    for categoria, despesa in sorted(por_categoria.items(), key=lambda x: x[1], reverse=True,):
        # primeira versão: gap por categoria = despesa contábil elegível
        # depois podemos ratear a EFD declarada por natureza/categoria
        base_atribuida = Decimal("0.00")
        if total_despesa_categoria > 0 and total_efd > 0:
            base_atribuida = ((despesa / total_despesa_categoria) * total_efd).quantize(Decimal("0.01"))

        gap = despesa - base_atribuida
        if gap < 0:
            gap = Decimal("0.00")

        pis = (gap * ALIQUOTA_PIS).quantize(Decimal("0.01"))
        cofins = (gap * ALIQUOTA_COFINS).quantize(Decimal("0.01"))
        recuperavel = pis + cofins

        ws.append([
            categoria,
            despesa,
            base_atribuida,
            gap,
            pis,
            cofins,
            recuperavel,
        ])

        total_ecd += despesa
        total_gap += gap
        total_pis += pis
        total_cofins += cofins
        total_recuperavel += recuperavel

    total_row = ws.max_row + 1

    total_gap = total_ecd - total_efd
    if total_gap < 0:
        total_gap = Decimal("0.00")

    ws.append([
        "TOTAL GERAL",
        total_ecd,
        total_efd,
        total_gap,
        total_pis,
        total_cofins,
        total_recuperavel,
    ])

    for cell in ws[total_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="FFF2CC")

    thin = Side(style="thin", color="000000")
    for cell in ws[total_row]:
        cell.border = Border(top=thin)

    ws.append([])
    ws.append(["Notas Metodológicas"])
    ws[f"A{ws.max_row}"].font = Font(bold=True)

    ws.append(["1. Base ECD representa despesas elegíveis classificadas por categoria contábil."])
    ws.append(["2. Gap Identificado representa potencial ainda sujeito à validação fiscal."])
    ws.append(["3. Crédito potencial calculado com PIS 1,65% e COFINS 7,60% nesta versão inicial."])
    ws.append(["4. Bases por natureza e divergências técnicas constam nas abas específicas."])
    ws.append(["5. Itens sem lastro suficiente devem ser revisados na aba Investigar."])
    ws.append(["6. A Base Atribuída EFD é rateada proporcionalmente entre as categorias elegíveis para fins de estimativa executiva."])

    cobertura_pct = Decimal("0.00")
    if total_ecd > 0:
        cobertura_pct = ((total_efd / total_ecd) * Decimal("100")).quantize(Decimal("0.01"))

    ws.append([])
    alerta_row = ws.max_row + 1
    ws.append([
        f"ALERTA - Apenas {cobertura_pct}% da despesa elegível identificada na ECD possui lastro declarado na EFD-Contribuições."
    ])

    ws.merge_cells(start_row=alerta_row, start_column=1, end_row=alerta_row, end_column=7)
    ws[f"A{alerta_row}"].font = Font(bold=True, color="FFFFFF")
    ws[f"A{alerta_row}"].fill = PatternFill("solid", fgColor="C00000")

    for col in ["B", "C", "D", "E", "F", "G"]:
        for row in range(3, total_row + 1):
            ws[f"{col}{row}"].number_format = '#,##0.00'

    autosize_columns(ws)