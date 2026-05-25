
import re

def only_digits(valor):
    return "".join(ch for ch in str(valor or "") if ch.isdigit())


def norm_str(valor):
    return str(valor or "").strip().upper()

def normalizar_espacos(valor: str) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()

def limpar_texto_sped(valor: str) -> str:
    valor = normalizar_espacos(valor)
    return valor

def norm_code(valor: str) -> str:
    return re.sub(r"\s+", "", str(valor or "").strip().upper())