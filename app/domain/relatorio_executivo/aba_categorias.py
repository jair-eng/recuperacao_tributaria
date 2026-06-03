from collections import defaultdict
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from app.config.settings import ALIQUOTA_PIS, ALIQUOTA_COFINS
from app.utils.excel import criar_aba_generica
from app.utils.numbers import to_decimal
import re
from openpyxl.styles import Font, PatternFill, Alignment


def _nome_aba_categoria(categoria: str) -> str:
    nome = str(categoria or "").strip()
    nome = nome.replace("/", "-").replace("\\", "-")
    return f"CAT_{nome[:25]}"

def categoria_legivel(categoria: str) -> str:
    if not categoria:
        return ""

    texto = re.sub(r"([a-z])([A-Z])", r"\1 \2", categoria)

    ajustes = {
        "PJ": "PJ",
        "PF": "PF",
        "MOPP": "MOPP",
    }

    partes = []
    for p in texto.split():
        partes.append(ajustes.get(p, p))

    return " ".join(partes)

def criar_abas_por_categoria(
    wb: Workbook,
    ctx: dict,
) -> None:
    por_categoria = defaultdict(list)

    for item in ctx.get("linhas_ecd", []):
        categoria = item.get("categoria")

        if not categoria or categoria == "NaoClassificado":
            continue

        if item.get("fundamento") == "Investigar":
            continue

        por_categoria[categoria].append(item)


    for categoria, itens in por_categoria.items():
        rows = []

        for item in itens:
            valor = to_decimal(item.get("valor"))
            base = valor
            gap = valor

            credito_pis = (gap * ALIQUOTA_PIS).quantize(Decimal("0.01"))
            credito_cofins = (gap * ALIQUOTA_COFINS).quantize(Decimal("0.01"))

            rows.append(
                {
                    "Período": item.get("periodo"),
                    "Código Conta": item.get("cod_cta"),
                    "Descrição": item.get("nome_cta"),
                    "Grupo": item.get("grupo"),
                    "Fundamento": item.get("fundamento"),
                    "Naturezas Esperadas": item.get("naturezas_esperadas"),
                    "Despesa Contábil": valor,
                    "Base": base,
                    "Gap": gap,
                    "Crédito PIS": credito_pis,
                    "Crédito COFINS": credito_cofins,
                    "Fonte": item.get("origem_classificacao") or "Heurística",
                    "Confiança": item.get("confianca"),
                    "Observação": item.get("observacao"),
                }
            )

        criar_aba_generica(
            wb,
            nome_aba=_nome_aba_categoria(categoria),
            headers=[
                "Período",
                "Código Conta",
                "Descrição",
                "Grupo",
                "Fundamento",
                "Naturezas Esperadas",
                "Despesa Contábil",
                "Base",
                "Gap",
                "Crédito PIS",
                "Crédito COFINS",
                "Fonte",
                "Confiança",
                "Observação",
            ],
            rows=rows,
            money_cols=[
                "Despesa Contábil",
                "Base",
                "Gap",
                "Crédito PIS",
                "Crédito COFINS",
            ],
        )


        ws = wb[_nome_aba_categoria(categoria)]

        ws.insert_rows(1, amount=2)

        ultima_coluna = ws.max_column

        ws.merge_cells(
            start_row=1,
            start_column=1,
            end_row=1,
            end_column=ultima_coluna,
        )

        ws.merge_cells(
            start_row=2,
            start_column=1,
            end_row=2,
            end_column=ultima_coluna,
        )

        ws["A1"] = f"Categoria: {categoria_legivel(categoria)}"

        ws["A2"] = (
            f"Fundamento: {itens[0].get('fundamento')} | "
            f"Naturezas Esperadas: "
            f"{', '.join(map(str, itens[0].get('naturezas_esperadas') or []))}"
        )
        ultima_coluna = ws.max_column
        ultima_linha = ws.max_row

        ws.auto_filter.ref = f"A3:{get_column_letter(ultima_coluna)}{ultima_linha}"
        ws.freeze_panes = "A4"

        fill = PatternFill(
            fill_type="solid",
            fgColor="E7E6E6",  # ajuste para o mesmo azul do seu cabeçalho
        )

        font = Font(
            color="000000",
            bold=True,
        )

        align = Alignment(
            horizontal="center",
            vertical="center",
        )

        for celula in ("A1", "A2"):
            ws[celula].fill = fill
            ws[celula].font = font
            ws[celula].alignment = align