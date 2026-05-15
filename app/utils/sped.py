def split_linha_sped(linha: str) -> list[str]:
    return str(linha or "").strip().strip("|").split("|")