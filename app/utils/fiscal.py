from app.utils.strings import norm_str


def eh_complemento_valor(descricao: str = "", cod_sit: str = "") -> bool:
    desc = norm_str(descricao or "").upper()
    cod_sit = str(cod_sit or "").strip().zfill(2)

    if cod_sit in {"06", "07"}:
        return True

    termos = (
        "COMPLEMENTO DE VALOR",
        "COMPLEMENTO",
        "NOTA COMPLEMENTAR",
        "COMPLEMENTAR",
    )

    return any(t in desc for t in termos)