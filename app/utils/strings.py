
import re
import unicodedata
from typing import Any


def only_digits(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def norm_str(valor):
    return str(valor or "").strip().upper()

def normalizar_texto(valor: str) -> str:
    valor = unicodedata.normalize("NFKD", valor)
    valor = valor.encode("ascii", "ignore").decode("ascii")
    return valor.upper().strip()

def normalizar_espacos(valor: str) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()

def limpar_texto_sped(valor: str) -> str:
    valor = normalizar_espacos(valor)
    return valor

def norm_code(valor: str) -> str:
    return re.sub(r"\s+", "", str(valor or "").strip().upper())

def match_palavras(texto: str, palavras_chave: str | list[str]) -> bool:
    texto_norm = norm_str(texto or "").upper()

    if isinstance(palavras_chave, str):
        termos = split_palavras(palavras_chave)
    else:
        termos = [
            norm_str(x or "").upper().strip()
            for x in palavras_chave
            if str(x or "").strip()
        ]

    return any(t and t in texto_norm for t in termos)

def split_palavras(palavras_chave: str) -> list[str]:
    return [
        norm_str(x or "").upper().strip()
        for x in str(palavras_chave or "").split(";")
        if str(x or "").strip()
    ]

def s(v: Any) -> str:
    return str(v or "").strip()


def norm_cod_item(v: Any) -> str:
    return s(v).upper().replace(" ", "").replace("-", "").replace(".", "")