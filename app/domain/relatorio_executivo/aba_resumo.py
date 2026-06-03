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
        categoria = item.get("categoria") or "NaoClassificado"
        valor = to_decimal(item.get("valor"))
        if valor > 0:
            por_categoria[categoria] += valor

    total_efd = to_decimal((ctx.get("resumo") or {}).get("total_efd_declarada"))

    total_despesa_geral = sum(por_categoria.values(), Decimal("0.00"))

    total_despesa_elegivel = sum(
        despesa
        for categoria, despesa in por_categoria.items()
        if categoria != "NaoClassificado"
    )

    total_ecd = Decimal("0.00")
    total_base = Decimal("0.00")
    total_gap = Decimal("0.00")
    total_pis = Decimal("0.00")
    total_cofins = Decimal("0.00")
    total_recuperavel = Decimal("0.00")

    for categoria, despesa in sorted(
            por_categoria.items(),
            key=lambda x: (x[0] == "NaoClassificado", -x[1]),

    ):
        gera_credito = categoria != "NaoClassificado"

        base_atribuida = Decimal("0.00")
        gap = Decimal("0.00")
        pis = Decimal("0.00")
        cofins = Decimal("0.00")
        recuperavel = Decimal("0.00")

        if gera_credito:
            if total_despesa_elegivel > 0 and total_efd > 0:
                base_atribuida = ((despesa / total_despesa_elegivel) * total_efd).quantize(Decimal("0.01"))

            gap = despesa - base_atribuida
            if gap < 0:
                gap = Decimal("0.00")

            pis = (gap * ALIQUOTA_PIS).quantize(Decimal("0.01"))
            cofins = (gap * ALIQUOTA_COFINS).quantize(Decimal("0.01"))
            recuperavel = pis + cofins

            total_base += base_atribuida
            total_gap += gap
            total_pis += pis
            total_cofins += cofins
            total_recuperavel += recuperavel

        total_ecd += despesa

        ws.append([
            categoria,
            despesa,
            base_atribuida if gera_credito else "",
            gap if gera_credito else "",
            pis if gera_credito else "",
            cofins if gera_credito else "",
            recuperavel if gera_credito else "",
        ])

    total_row = ws.max_row + 1

    ws.append([
        "TOTAL GERAL",
        total_ecd,
        total_base,
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

    alertas_omissao = ctx.get("alertas_efd_omissao") or []

    if alertas_omissao:
        meses = sorted({str(a.get("Período")) for a in alertas_omissao if a.get("Período")})
        credito_perdido = sum(to_decimal(a.get("GAP")) for a in alertas_omissao)

        texto_alerta = (
            f"⚠ ALERTA - {len(meses)} mês(es) com EFD entregue zerada e despesa elegível na ECD: "
            f"{', '.join(map(str, meses))}. "
            f"Crédito perdido estimado: R$ {credito_perdido:,.2f}. "
            f"Ver aba 'Alertas EFD Omissão'."
        )

        alerta_row = ws.max_row + 2
        ws.cell(row=alerta_row, column=1, value=texto_alerta)

        ws.merge_cells(
            start_row=alerta_row,
            start_column=1,
            end_row=alerta_row,
            end_column=7,
        )

        cell = ws.cell(row=alerta_row, column=1)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="C00000")

    for col in ["B", "C", "D", "E", "F", "G"]:
        for row in range(3, total_row + 1):
            ws[f"{col}{row}"].number_format = '#,##0.00'

    autosize_columns(ws)