from typing import Any

from openpyxl import Workbook
from app.domain.relatorio_executivo.estilos_excel import apply_table_style, style_header, write_rows, autosize_columns
from openpyxl.utils import get_column_letter
from typing import Any, Dict, List

def remover_aba_padrao(wb: Workbook) -> None:
    if "Sheet" in wb.sheetnames:
        ws = wb["Sheet"]
        wb.remove(ws)



def criar_aba_generica(
    wb: Workbook,
    *,
    nome_aba: str,
    headers: list[str],
    rows: list[dict[str, Any]],
    money_cols: set[str] | list[str] | None = None,
) -> None:
    ws = wb.create_sheet(nome_aba)

    write_rows(
        ws,
        rows,
        headers,
        list(money_cols or []),
    )
    return ws



