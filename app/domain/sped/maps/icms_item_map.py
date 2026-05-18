from app.db.models.nf_icms_item import NfIcmsItem


def montar_mapa_icms_item(db, *, empresa_id: int, periodo: str):
    mapa_full = {}
    mapa_cod = {}
    mapa_num = {}

    itens = (
        db.query(NfIcmsItem)
        .filter(
            NfIcmsItem.empresa_id == empresa_id,
            NfIcmsItem.periodo == periodo,
        )
        .all()
    )

    for item in itens:
        chave_nfe = str(item.chave_nfe or "").strip()
        num_item = str(item.num_item or "").strip()
        cod_item = str(item.cod_item or "").strip()

        if chave_nfe and num_item and cod_item:
            mapa_full[(chave_nfe, num_item, cod_item)] = item

        if chave_nfe and cod_item:
            mapa_cod[(chave_nfe, cod_item)] = item

        if chave_nfe and num_item:
            mapa_num[(chave_nfe, num_item)] = item

    return {
        "full": mapa_full,
        "cod": mapa_cod,
        "num": mapa_num,
    }


def buscar_icms_item_em_mapa(mapa_icms, *, chave_nfe, num_item, cod_item):
    chave_nfe = str(chave_nfe or "").strip()
    num_item = str(num_item or "").strip()
    cod_item = str(cod_item or "").strip()

    return (
        mapa_icms["full"].get((chave_nfe, num_item, cod_item))
        or mapa_icms["cod"].get((chave_nfe, cod_item))
        or mapa_icms["num"].get((chave_nfe, num_item))
    )