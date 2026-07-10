
from pathlib import Path

from app.icms_ipi.icms_0150_agregador import _fmt_campo
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert
from app.utils.strings import only_digits
from sqlalchemy.orm import Session
from decimal import Decimal
from typing import Any

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

def dec_sped_safe(raw: object) -> Decimal:
    s = str(raw or "").strip()
    if not s:
        return Decimal("0")
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")

def preview_linha_sped(linha: str, limite: int = 180) -> str:
    linha = str(linha or "").replace("\n", "\\n")
    return linha[:limite]

def join_sped_line(reg: str, dados: list[Any]) -> str:
    return "|" + "|".join([str(reg)] + ["" if x is None else str(x) for x in dados]) + "|"

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

def montar_cache_mestres_logicos(
    db: Session,
    *,
    versao_origem_id: int,
) -> dict:
    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=None,
    )

    cache = {
        "0150_cod_part": {},
        "0150_cnpj": {},
        "0190": set(),
        "0200": set(),
        "0500": set(),
        "ancora_0190": None,
        "ancora_0200": None,
    }

    for l in linhas:
        reg = str(getattr(l, "reg", "") or "").upper()
        dados = list(getattr(l, "dados", []) or [])

        if dados and str(dados[0]).upper() == reg:
            dados = dados[1:]

        if reg == "0150":
            cod_part = _fmt_campo(dados[0] if len(dados) > 0 else "")
            cnpj = only_digits(dados[3] if len(dados) > 3 else "")
            if cod_part:
                cache["0150_cod_part"][cod_part] = {"cod_part": cod_part, "cnpj": cnpj}
            if cnpj:
                cache["0150_cnpj"][cnpj] = {"cod_part": cod_part, "cnpj": cnpj}

        elif reg == "0190":
            unid = str(dados[0] if len(dados) > 0 else "").strip().upper()
            if unid:
                cache["0190"].add(unid)

        elif reg == "0200":
            cod_item = str(dados[0] if len(dados) > 0 else "").strip()
            if cod_item:
                cache["0200"].add(cod_item)

        elif reg == "0500":
            cod_cta = str(dados[5] if len(dados) > 5 else "").strip()
            if cod_cta:
                cache["0500"].add(cod_cta)

    print(
        "[CACHE_MESTRES]",
        {
            "0150": len(cache["0150_cod_part"]),
            "0190": len(cache["0190"]),
            "0200": len(cache["0200"]),
            "0500": len(cache["0500"]),
        },
        flush=True,
    )

    return cache