from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

from app.utils.dates import agregar_trimestral, periodo_fechamento_trimestre
from app.utils.excel import autosize_columns
from app.utils.numbers import to_decimal


def _media_decimal(valores: list[Decimal]) -> Decimal:
    if not valores:
        return Decimal("0.00")
    return (sum(valores, Decimal("0.00")) / Decimal(len(valores))).quantize(Decimal("0.01"))


def _pct(parte: int | Decimal, total: int | Decimal) -> Decimal:
    parte = Decimal(str(parte or 0))
    total = Decimal(str(total or 0))
    if total <= 0:
        return Decimal("0.00")
    return ((parte / total) * Decimal("100")).quantize(Decimal("0.01"))


def criar_aba_diagnostico_efd(
    wb: Workbook,
    ctx: dict,
) -> None:
    ws = wb.create_sheet("Diagnostico Entrada")

    linhas_ecd = ctx.get("linhas_ecd") or []
    por_natureza = ctx.get("por_natureza") or {}

    contas = {
        str(i.get("cod_cta"))
        for i in linhas_ecd
        if i.get("cod_cta")
    }

    contas_classificadas = {
        str(i.get("cod_cta"))
        for i in linhas_ecd
        if i.get("cod_cta")
        and i.get("categoria")
        and i.get("categoria") != "NaoClassificado"
        and i.get("fundamento") != "Investigar"
    }

    contas_investigar = {
        str(i.get("cod_cta"))
        for i in linhas_ecd
        if i.get("cod_cta")
        and (
            not i.get("categoria")
            or i.get("categoria") == "NaoClassificado"
            or i.get("fundamento") == "Investigar"
        )
    }

    linhas_geradas = len(linhas_ecd)

    confiancas = [
        to_decimal(i.get("confianca"))
        for i in linhas_ecd
        if i.get("categoria") != "NaoClassificado"
        and i.get("confianca") is not None
    ]

    contas_baixa_confianca = {
        str(i.get("cod_cta"))
        for i in linhas_ecd
        if i.get("cod_cta")
        and i.get("categoria") != "NaoClassificado"
        and to_decimal(i.get("confianca")) < Decimal("70")
    }

    trimestres_ecd = {
        periodo_fechamento_trimestre(str(i.get("periodo")))
        for i in linhas_ecd
        if i.get("periodo")
    }

    agregado = agregar_trimestral(ctx)

    trimestres_documentados = {
        item["trimestre"]
        for item in agregado.values()
        if (
                   to_decimal(item.get("valor_creditado_c170"))
                   + to_decimal(item.get("valor_creditado_f100"))
                   + to_decimal(item.get("valor_creditado_a170"))
                   + to_decimal(item.get("valor_sem_credito_a170"))
           ) > 0
    }

    qtd_contas = len(contas)
    qtd_classificadas = len(contas_classificadas)
    qtd_investigar = len(contas_investigar)

    metricas = [
        ("Contas com despesa no período", qtd_contas),
        ("Linhas geradas (conta x mês)", linhas_geradas),
        ("Contas classificadas", qtd_classificadas),
        ("Contas em 'Investigar' (sem match)", qtd_investigar),
        ("% de cobertura da classificação", f"{_pct(qtd_classificadas, qtd_contas)}%"),
        ("Confiança média da classificação", f"{_media_decimal(confiancas)}%"),
        ("Contas com confiança < 70% (revisar)", len(contas_baixa_confianca)),
        ("Trimestres com despesa ECD", len(trimestres_ecd)),
        ("Trimestres com documentação fiscal", len(trimestres_documentados)),
        ("Falhas de leitura de arquivos", 0),
    ]

    ws.merge_cells("A1:E1")
    ws["A1"] = "Distribuição por categoria — ECD x Documentação"
    ws["A1"].font = Font(bold=True, color="FFFFFF", size=12)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws["A1"].fill = PatternFill("solid", fgColor="000080")

    ws.append([])
    ws.append(["Métrica", "Valor"])

    for cell in ws[3]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D9D9D9")

    for metrica, valor in metricas:
        ws.append([metrica, valor])

    ws.append([])
    ws.append([])
    ws.append(["Distribuição por categoria"])

    titulo_row = ws.max_row
    ws[f"A{titulo_row}"].font = Font(bold=True)

    ws.append(
        ["Categoria", "Contas distintas", "Despesa ECD", "EFD Documentado", "GAP ECD x Documentação"])

    header_row = ws.max_row
    for cell in ws[header_row]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D9D9D9")

    por_categoria = defaultdict(
        lambda: {
            "contas": set(),
            "despesa_ecd": Decimal("0.00"),
            "total_documentado": Decimal("0.00"),
        }
    )

    # ECD por categoria
    for item in linhas_ecd:
        categoria = item.get("categoria") or "NaoClassificado"
        valor = to_decimal(item.get("valor"))
        cod_cta = item.get("cod_cta")

        por_categoria[categoria]["despesa_ecd"] += valor

        if cod_cta:
            por_categoria[categoria]["contas"].add(str(cod_cta))

    # Documentado por categoria — mesma base da aba Base por Categoria
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

        por_categoria[categoria]["total_documentado"] += total_documentado

    for categoria, dados in sorted(
            por_categoria.items(),
            key=lambda x: (x[0] == "NaoClassificado", -x[1]["despesa_ecd"]),
    ):
        despesa_ecd = dados["despesa_ecd"]
        total_documentado = dados["total_documentado"]
        gap_ecd = max(Decimal("0.00"), despesa_ecd - total_documentado)

        ws.append([
            categoria,
            len(dados["contas"]),
            despesa_ecd,
            total_documentado,
            gap_ecd,

        ])

    for row in range(header_row + 1, ws.max_row + 1):
        for col in ["C", "D", "E"]:
            ws[f"{col}{row}"].number_format = '#,##0.00'

    autosize_columns(ws)