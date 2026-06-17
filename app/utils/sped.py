
from pathlib import Path
from app.utils.strings import only_digits, s
from typing import Any, Dict


def split_linha_sped(linha: str) -> list[str]:
    return str(linha or "").strip().strip("|").split("|")

def get_sped_str(
    dados: list[Any],
    idx_map: dict[str, int],
    campo: str,
) -> str:
    idx = idx_map[campo]

    if idx >= len(dados):
        return ""

    return str(dados[idx] or "").strip()

def reg_linha_sped(linha: str) -> str:
    partes = (linha or "").strip().split("|")
    if len(partes) > 1:
        return partes[1].strip()
    return ""


def extrair_dados_sped(reg: Any) -> list[Any]:
    if hasattr(reg, "dados"):
        return list(reg.dados or [])

    conteudo_json = getattr(reg, "conteudo_json", None) or {}

    return list(conteudo_json.get("dados") or [])

def ler_linhas_sped(caminho: Path) -> list[list[str]]:
    linhas = []

    with open(caminho, "r", encoding="latin-1", errors="ignore") as f:
        for linha in f:

            if not linha.startswith("|"):
                continue

            dados = split_linha_sped(linha)

            if not dados:
                continue

            linhas.append(dados)

    return linhas

def listar_txt(pasta: Path) -> list[Path]:
    if not pasta.exists() or not pasta.is_dir():
        raise FileNotFoundError(f"Pasta não encontrada: {pasta}")

    return sorted(
        [p for p in pasta.glob("*.txt") if p.is_file()],
        key=lambda p: p.name.lower(),
    )

def periodo_por_i355(mov: dict, periodo: str | None = None) -> str | None:
    if periodo:
        return periodo

    for campo in ("periodo", "dt_ini", "dt_fin", "data"):
        valor = str(mov.get(campo) or "").strip()
        if len(valor) >= 6 and valor[:6].isdigit():
            return valor[:6]

    return None

def periodo_de_data_sped(data: str | None) -> str | None:
    data = str(data or "").strip()

    if len(data) != 8 or not data.isdigit():
        return None

    # DDMMAAAA -> AAAAMM
    return data[4:8] + data[2:4]

def chave_match_item(item):
    return (
        only_digits(item.get("chv_nfe")),
        str(item.get("cod_item") or "").strip(),
    )

def chave_match_num_item(item):
    return (
        only_digits(item.get("chv_nfe")),
        str(item.get("num_item") or "").strip(),
    )
def campo(partes: list[str], idx: int) -> str:
    return partes[idx] if len(partes) > idx else ""
