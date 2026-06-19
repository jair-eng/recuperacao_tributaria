from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from app.utils.dates import agregar_trimestral
from app.utils.ecd_gap_utils import iter_items, ordem_categoria
from app.utils.excel import autosize_columns
from app.utils.numbers import to_decimal


def criar_aba_resumo(
    wb: Workbook,
    ctx: dict,
    *,
    titulo: str = "Revisão Fiscal PIS/COFINS - Sumário Executivo",
) -> None:
    ws = wb.create_sheet("Resumo")

    ws.merge_cells("A1:H1")
    ws["A1"] = titulo
    ws["A1"].font = Font(bold=True, color="FFFFFF", size=12)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws["A1"].fill = PatternFill("solid", fgColor="000080")

    headers = [
        "Categoria",
        "Despesa Contábil Total",
        "EFD Documentada",
        "Gap Identificado",
        "Base Recuperável C170",
        "PIS Recuperável C170",
        "COFINS Recuperável C170",
        "Crédito Recuperável C170",
    ]

    ws.append(headers)
    ws.freeze_panes = "A3"

    header_fill = PatternFill("solid", fgColor="D9D9D9")
    for cell in ws[2]:
        cell.font = Font(bold=True)
        cell.fill = header_fill

    por_categoria = defaultdict(lambda: {
        "despesa": Decimal("0.00"),
    })

    for item in iter_items(ctx.get("linhas_ecd")):
        categoria = item.get("categoria") or "NaoClassificado"
        valor = to_decimal(item.get("valor"))

        if valor <= 0:
            continue

        por_categoria[categoria]["despesa"] += valor

    documentado_por_categoria = defaultdict(lambda: Decimal("0.00"))

    agregado = agregar_trimestral(ctx)

    for item in agregado.values():
        categoria = item.get("categoria") or "NaoClassificado"

        total_creditado = (
                to_decimal(item.get("valor_creditado_c170"))
                + to_decimal(item.get("valor_creditado_f100"))
                + to_decimal(item.get("valor_creditado_a170"))
        )

        total_documentado = (
                total_creditado
                + to_decimal(item.get("valor_oportunidade_c170"))
                + to_decimal(item.get("valor_sem_credito_a170"))
        )

        documentado_por_categoria[categoria] += total_documentado

    oportunidades_por_categoria = defaultdict(lambda: {
        "base_c170": Decimal("0.00"),
        "pis_c170": Decimal("0.00"),
        "cofins_c170": Decimal("0.00"),
        "credito_c170": Decimal("0.00"),
    })

    for op in ctx.get("oportunidades_c170") or []:
        categoria = op.get("categoria") or "NaoClassificado"

        oportunidades_por_categoria[categoria]["base_c170"] += to_decimal(op.get("base_recuperavel"))
        oportunidades_por_categoria[categoria]["pis_c170"] += to_decimal(op.get("pis_recuperavel"))
        oportunidades_por_categoria[categoria]["cofins_c170"] += to_decimal(op.get("cofins_recuperavel"))
        oportunidades_por_categoria[categoria]["credito_c170"] += to_decimal(op.get("credito_recuperavel"))

    total_ecd = Decimal("0.00")
    total_documentado = Decimal("0.00")
    total_gap = Decimal("0.00")
    total_base_c170 = Decimal("0.00")
    total_pis_c170 = Decimal("0.00")
    total_cofins_c170 = Decimal("0.00")
    total_credito_c170 = Decimal("0.00")

    for categoria, dados in sorted(
            por_categoria.items(),
            key=lambda x: (
                    x[0] == "NaoClassificado",
                    -x[1]["despesa"],
            ),
    ):
        despesa = dados["despesa"]
        efd_documentado = documentado_por_categoria.get(categoria) or Decimal("0.00")
        gap = max(Decimal("0.00"), despesa - efd_documentado)

        c170 = oportunidades_por_categoria.get(categoria) or {}

        base_c170 = c170.get("base_c170") or Decimal("0.00")
        pis_c170 = c170.get("pis_c170") or Decimal("0.00")
        cofins_c170 = c170.get("cofins_c170") or Decimal("0.00")
        credito_c170 = c170.get("credito_c170") or Decimal("0.00")

        total_ecd += despesa
        total_documentado += efd_documentado
        total_gap += gap
        total_base_c170 += base_c170
        total_pis_c170 += pis_c170
        total_cofins_c170 += cofins_c170
        total_credito_c170 += credito_c170


        ws.append([
            categoria,
            despesa,
            efd_documentado if efd_documentado else "",
            gap if gap else "",
            base_c170 if base_c170 else "",
            pis_c170 if pis_c170 else "",
            cofins_c170 if cofins_c170 else "",
            credito_c170 if credito_c170 else "",
        ])

    total_row = ws.max_row + 1

    ws.append([
        "TOTAL GERAL",
        total_ecd,
        total_documentado,
        total_gap,
        total_base_c170,
        total_pis_c170,
        total_cofins_c170,
        total_credito_c170,
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

    ws.append(["1. Despesa Contábil Total representa os valores identificados na ECD por categoria fiscal."])
    ws.append(["2. Base Atribuída EFD representa a base declarada na EFD Contribuições vinculada às naturezas esperadas da categoria."])
    ws.append(["3. Gap Identificado representa diferença entre despesa elegível e base atribuída na EFD, sujeito à validação fiscal e documental."])
    ws.append(["4. Valores recuperáveis C170 representam oportunidades documentadas por item, nota fiscal e cenário fiscal."])
    ws.append(["5. Crédito Recuperável C170 não é estimativa teórica; decorre da aba 'Oportunidades C170'."])
    ws.append(["6. Itens sem lastro suficiente devem ser revisados nas abas específicas de investigação."])

    alertas_omissao = ctx.get("alertas_efd_omissao") or []

    meses = sorted({str(a.get("Período")) for a in alertas_omissao if a.get("Período")})
    gap_omissao = sum(to_decimal(a.get("GAP")) for a in alertas_omissao)

    if meses and gap_omissao > 0:
        texto_alerta = (
            f"⚠ ALERTA - {len(meses)} mês(es) com EFD entregue zerada "
            f"e despesa elegível na ECD: {', '.join(meses)}. "
            f"Gap identificado: R$ {gap_omissao:,.2f}. "
            f"Ver aba 'Alertas EFD Omissão'."
        )

        alerta_row = ws.max_row + 2
        ws.cell(row=alerta_row, column=1, value=texto_alerta)

        ws.merge_cells(
            start_row=alerta_row,
            start_column=1,
            end_row=alerta_row,
            end_column=8,
        )

        cell = ws.cell(row=alerta_row, column=1)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="C00000")

    for col in ["B", "C", "D", "E", "F", "G", "H"]:
        for row in range(3, total_row + 1):
            ws[f"{col}{row}"].number_format = '#,##0.00'

    autosize_columns(ws)
    larguras = {
        "A": 29,  # Categoria
        "B": 20,  # Despesa Contábil Total
        "C": 18,  # Base Atribuída EFD
        "D": 18,  # Gap Identificado
        "E": 21,  # Base Recuperável C170
        "F": 21,  # PIS Recuperável C170
        "G": 23,  # COFINS Recuperável C170
        "H": 23,  # Crédito Recuperável C170
    }

    for col, width in larguras.items():
        ws.column_dimensions[col].width = width