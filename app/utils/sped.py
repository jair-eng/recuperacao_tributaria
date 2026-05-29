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


def extrair_dados_sped(reg: Any) -> list[Any]:
    if hasattr(reg, "dados"):
        return list(reg.dados or [])

    conteudo_json = getattr(reg, "conteudo_json", None) or {}

    return list(conteudo_json.get("dados") or [])