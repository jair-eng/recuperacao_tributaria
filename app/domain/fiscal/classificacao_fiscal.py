def classificar_modelo_documento(modelo: str | None) -> str | None:
    if modelo == "55":
        return "NFE"
    if modelo == "57":
        return "CTE"
    if modelo == "65":
        return "NFCE"
    return None


def classificar_tipo_normalizacao(modelo: str | None) -> str:
    if modelo == "55":
        return "CONTRIB_C100_C170_FALTANTE"
    if modelo == "57":
        return "CONTRIB_D100_FALTANTE"
    return "CONTRIB_DOC_FALTANTE"


def detectar_tipo_participante_doc(doc: str | None) -> str | None:
    doc = "".join(ch for ch in str(doc or "") if ch.isdigit())

    if len(doc) == 14:
        return "CNPJ"
    if len(doc) == 11:
        return "CPF"
    return None