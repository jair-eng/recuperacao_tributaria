from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Dict, Optional, List
from decimal import Decimal, ROUND_HALF_UP

from app.fiscal.cat_fiscal import CatalogoFiscal
from app.fiscal.constants import DOM_AGRO, DOM_GERAL, DOM_CAFE, DOM_TRANSP, DOM_REVENDA_GAS, DOM_POSTO
from app.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.fiscal.settings_fiscais import CFOPS_ELEGIVEIS, TRANSP_NCM_SLUGS, TRANSP_DESC_SLUGS, \
    grupos_posto_credito_normal


# ============================================================
# Helpers
# ============================================================


def _match_dominio_transp_catalogo(
    *,
    ncm: str,
    desc: str,
    catalogo: CatalogoFiscal,
) -> bool:
    ncm = str(ncm or "").strip()
    desc = _norm_str(desc).upper()

    for slug in TRANSP_NCM_SLUGS:
        if catalogo.ncm_match(slug, ncm):
            return True

    for slug in TRANSP_DESC_SLUGS:
        for termo in catalogo.codigos(slug):
            termo_norm = _norm_str(str(termo or "")).upper()
            if termo_norm and termo_norm in desc:
                return True

    return False


def fmt_sped_num(v, casas=2) -> str:
    dec = Decimal(str(v or 0))

    if casas == 2:
        dec = dec.quantize(Decimal("0.01"))
    elif casas == 4:
        dec = dec.quantize(Decimal("0.0001"))

    txt = f"{dec:.{casas}f}"

    return txt.replace(".", ",")

def fmt_sped_qtd(v) -> str:
    if v in (None, ""):
        return "0"

    txt = str(v).strip().replace(",", ".")
    try:
        dec = Decimal(txt)
    except (InvalidOperation, ValueError):
        return str(v).strip()

    s = format(dec.normalize(), "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")

def _s(v: Any) -> str:
    return _norm_str(v)

def _as_decimal(v: Any) -> Decimal:
    if isinstance(v, Decimal):
        return v
    if v in (None, "", False):
        return Decimal("0")
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _as_date_str(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    s = str(v).strip()
    return s or None
def _only_digits(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\D+", "", str(value))


def _norm_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _norm_num_nf(value: Any) -> str:
    s = _only_digits(value)
    if not s:
        return ""
    # remove zeros à esquerda para aumentar chance de match
    s = s.lstrip("0")
    return s or "0"


def _norm_serie(value: Any) -> str:
    s = _only_digits(value)
    if not s:
        s = _norm_str(value)
    s = s.lstrip("0")
    return s or "0"


def _norm_chave(value: Any) -> str:
    s = _only_digits(value)
    return s if len(s) == 44 else ""


def _to_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    s = str(value).strip()

    # formatos comuns
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d%m%Y", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass

    return None


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")

    if isinstance(value, Decimal):
        return value

    s = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


def _dec_to_str(value: Any) -> str:
    return f"{_to_decimal(value):f}"

def _norm_cod_item(value: Any) -> str:
    s = _norm_str(value)
    if not s:
        return ""
    return s.lstrip("0") or s


def _campo(dados: list[Any], idx: int) -> str:
    if idx < 0 or idx >= len(dados):
        return ""
    return _norm_str(dados[idx])


def _campo_dec(dados: list[Any], idx: int) -> Decimal:
    if idx < 0 or idx >= len(dados):
        return Decimal("0")
    return _as_decimal(dados[idx])

def q2(v: Decimal) -> Decimal:
    return (v or Decimal("0")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def _split_sped_line(line: str) -> tuple[str, list[str]]:
    """
    Converte uma linha SPED como:
    |C100|0|1|...|
    em:
    reg='C100', fields=[...]
    """
    if not line or "|" not in line:
        return "", []
    parts = line.strip().split("|")

    if len(parts) < 3:
        return "", []
    payload = parts[1:-1] if parts[-1] == "" else parts[1:]

    if not payload:
        return "", []
    reg = payload[0].strip()
    fields = [p.strip() for p in payload[1:]]
    return reg, fields


def _parse_date_ddmmyyyy(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%d%m%Y").date()



def _parse_decimal(value: str) -> Decimal:
    value = (value or "").strip()

    if not value:
        return Decimal("0")

    # padrão SPED: 95268,36
    if "," in value:
        value = value.replace(".", "").replace(",", ".")
        try:
            return Decimal(value)
        except InvalidOperation:
            return Decimal("0")

    # números inteiros do SPED já estão corretos
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal("0")

def _norm(v) -> str:
    return str(v or "").strip().upper()

def _digits(v) -> str:
    return "".join(ch for ch in str(v or "") if ch.isdigit())

def _item_cfop(item: dict) -> str:
    return _norm(
        item.get("cfop")
        or item.get("cod_cfop")
        or ""
    )

def _item_ncm(item: dict) -> str:
    return _digits(
        item.get("ncm")
        or item.get("cod_ncm")
        or item.get("ncm_0200")
        or ""
    )

def _item_desc(item: dict) -> str:
    return _norm(
        item.get("descricao")
        or item.get("descr_item")
        or item.get("descricao_item")
        or item.get("desc_item")
        or item.get("descricao_0200")
        or ""
    )

def _item_dominio_ok(item: dict, dominio: str, catalogo: CatalogoFiscal | None = None) -> bool:
    cfop = _item_cfop(item)
    ncm = _item_ncm(item)
    desc = _item_desc(item)
    dom = _norm(dominio)

    if dom == DOM_CAFE:
        if cfop not in CFOPS_ELEGIVEIS:
            return False
        if ncm.startswith("0901"):
            return True
        palavras = (
            "CAFE", "CAFÉ", "CAFE EM GRAO", "CAFÉ EM GRÃO",
            "CAFE ARABICA", "GRÃO DE CAFÉ", "GRAO DE CAFE",
        )
        return any(p in desc for p in palavras)

    if dom == DOM_AGRO:
        if cfop not in CFOPS_ELEGIVEIS:
            return False
        if ncm.startswith(("0901", "1001", "1005", "1201")):
            return True
        palavras = ("CAFE", "CAFÉ", "SOJA", "MILHO", "TRIGO")
        return any(p in desc for p in palavras)

    if dom == DOM_TRANSP:
        if not catalogo:
            return False
        return _match_dominio_transp_catalogo(
            ncm=ncm,
            desc=desc,
            catalogo=catalogo,
        )

    if dom == DOM_POSTO:
        if not catalogo:
            return False

        if ncm and catalogo.ncm_match("COMB_LC192_NCM", ncm):
            return True

        if ncm and catalogo.ncm_match("MONO_COMBUSTIVEIS", ncm):
            return True

        if ncm and any(catalogo.ncm_match(grupo, ncm) for grupo in grupos_posto_credito_normal):
            return True

        palavras = (
            "GASOLINA", "DIESEL", "OLEO DIESEL", "ÓLEO DIESEL",
            "ETANOL", "ALCOOL", "ÁLCOOL", "GLP",
            "GAS LIQUEFEITO", "GÁS LIQUEFEITO",
            "LUBRIFICANTE", "OLEO", "ÓLEO", "GRAXA",
            "LUBRAX", "TUTELA", "MOBIL", "CASTROL", "SELENIA", "SHELL",
            "FILTRO", "ADITIVO", "FLUIDO", "ARLA",
        )
        return any(p in desc for p in palavras)

    if dom == DOM_REVENDA_GAS:
        if not catalogo:
            return False

        if ncm and catalogo.ncm_match("COMB_LC192_NCM", ncm):
            return True

        if ncm and catalogo.ncm_match("MONO_COMBUSTIVEIS", ncm):
            return True

        # fallback forte para GLP
        if ncm.startswith("271119"):
            return True

        palavras = (
            "GLP",
            "GAS GLP",
            "GÁS GLP",
            "GAS LIQUEFEITO",
            "GÁS LIQUEFEITO",
            "BOTIJAO",
            "BOTIJÃO",
            "P13",
            "P20",
            "P45",
        )
        return any(p in desc for p in palavras)

    if dom == DOM_GERAL:
        return True

    return False

