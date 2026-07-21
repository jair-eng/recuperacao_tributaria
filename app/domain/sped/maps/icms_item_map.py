from app.db.models.nf_icms_item import NfIcmsItem
from app.utils.numbers import dec_any


def montar_mapa_icms_item(db, *, empresa_id: int, periodo: str):
    mapa_full = {}
    mapa_cod = {}
    mapa_cod_valor = {}
    mapa_valor = {}
    mapa_num = {}
    mapa_por_chave = {}

    itens = (
        db.query(NfIcmsItem)
        .filter(
            NfIcmsItem.empresa_id == empresa_id,
            NfIcmsItem.periodo == periodo,
        )
        .order_by(NfIcmsItem.id.asc())
        .all()
    )

    for item in itens:
        chave_nfe = str(item.chave_nfe or "").strip()
        num_item = str(item.num_item or "").strip()
        cod_item = str(item.cod_item or "").strip()
        vl_item = dec_any(item.vl_item)

        if chave_nfe:
            mapa_por_chave.setdefault(
                chave_nfe,
                [],
            ).append(item)

        if chave_nfe and num_item and cod_item:
            mapa_full[
                (chave_nfe, num_item, cod_item)
            ] = item

        # Pode haver mais de um item com mesmo código
        if chave_nfe and cod_item:
            mapa_cod.setdefault(
                (chave_nfe, cod_item),
                [],
            ).append(item)

        # Pode haver mais de um item com mesmo código + valor
        if chave_nfe and cod_item:
            mapa_cod_valor.setdefault(
                (chave_nfe, cod_item, vl_item),
                [],
            ).append(item)

        # Valor também pode se repetir
        if chave_nfe:
            mapa_valor.setdefault(
                (chave_nfe, vl_item),
                [],
            ).append(item)

        if chave_nfe and num_item:
            mapa_num[
                (chave_nfe, num_item)
            ] = item

    return {
        "itens": itens,
        "full": mapa_full,
        "cod": mapa_cod,
        "cod_valor": mapa_cod_valor,
        "valor": mapa_valor,
        "num": mapa_num,
        "por_chave": mapa_por_chave,
    }

def buscar_icms_item_em_mapa(
    mapa_icms,
    *,
    chave_nfe,
    num_item,
    cod_item,
    vl_item=None,
    ids_usados=None,
):
    chave_nfe = str(chave_nfe or "").strip()
    num_item = str(num_item or "").strip()
    cod_item = str(cod_item or "").strip()
    vl_item = dec_any(vl_item)

    usados = ids_usados or set()

    def primeiro_disponivel(candidatos):
        for item in candidatos or []:
            item_id = int(getattr(item, "id", 0) or 0)

            if item_id and item_id not in usados:
                return item

        return None

    # 1) Código + valor
    if chave_nfe and cod_item:
        candidatos = mapa_icms["cod_valor"].get(
            (chave_nfe, cod_item, vl_item),
            [],
        )

        item = primeiro_disponivel(candidatos)

        if item is not None:
            return item

    # 2) Match exato, mas valor precisa confirmar
    if chave_nfe and num_item and cod_item:
        item = mapa_icms["full"].get(
            (chave_nfe, num_item, cod_item)
        )

        if (
            item is not None
            and int(getattr(item, "id", 0) or 0) not in usados
            and dec_any(item.vl_item) == vl_item
        ):
            return item

    # 3) Mesmo valor dentro da mesma NF.
    # Consome um candidato ainda não usado.
    candidatos_valor = mapa_icms["valor"].get(
        (chave_nfe, vl_item),
        [],
    )

    item = primeiro_disponivel(candidatos_valor)

    if item is not None:
        return item

    # 4) Código como último fallback controlado
    if chave_nfe and cod_item:
        candidatos_cod = mapa_icms["cod"].get(
            (chave_nfe, cod_item),
            [],
        )

        candidatos_cod = [
            item
            for item in candidatos_cod
            if (
                int(getattr(item, "id", 0) or 0) not in usados
                and dec_any(item.vl_item) == vl_item
            )
        ]

        item = primeiro_disponivel(candidatos_cod)

        if item is not None:
            return item

    # NUM_ITEM sozinho não deve casar itens.
    return None