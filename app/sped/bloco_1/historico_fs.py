from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple
import re


@dataclass(frozen=True)
class SpedInfo:
    path: Path
    cnpj: Optional[str]
    periodo: Optional[int]  # YYYYMM
    mtime: float


def extrair_cnpj_periodo_do_0000(linhas: list[str]) -> Tuple[Optional[str], Optional[int]]:
    """
    Extrai CNPJ e período (YYYYMM) do 0000 a partir das linhas do arquivo.
    Observação: no seu layout você já tinha DT_INI em DDMMAAAA em parts[5].
    """
    for ln in linhas or []:
        ln = (ln or "").strip()
        if not ln.startswith("|0000|"):
            continue

        parts = ln.strip("|").split("|")

        # CNPJ = primeiro token com 14 dígitos
        cnpj = None
        for tok in parts:
            t = re.sub(r"\D+", "", tok or "")
            if len(t) == 14:
                cnpj = t
                break

        # período por DT_INI (DDMMAAAA) no parts[5]
        periodo = None
        dt_ini = parts[5] if len(parts) > 5 else ""
        dt = re.sub(r"\D+", "", dt_ini or "")
        if len(dt) == 8 and dt.isdigit():
            dd = int(dt[0:2])
            mm = int(dt[2:4])
            yyyy = int(dt[4:8])
            if 1 <= dd <= 31 and 1 <= mm <= 12 and 1900 <= yyyy <= 2100:
                periodo = yyyy * 100 + mm

        return cnpj, periodo

    return None, None
