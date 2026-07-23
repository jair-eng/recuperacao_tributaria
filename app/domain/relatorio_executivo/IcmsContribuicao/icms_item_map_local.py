from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.utils.numbers import dec_any
from app.utils.strings import only_digits, norm_cod_item


def montar_mapa_contrib_item_local(
    itens_contrib: list[dict[str, Any]],
) -> dict[str, Any]:
    mapa_full = {}
    mapa_cod = defaultdict(list)
    mapa_cod_valor = defaultdict(list)
    mapa_valor = defaultdict(list)
    mapa_num = defaultdict(list)
    mapa_por_chave = defaultdict(list)

    for posicao, item in enumerate(itens_contrib):
        chave_nfe = only_digits(
            item.get("chv_nfe")
            or item.get("chave")
        )

        num_item = str(
            item.get("num_item") or ""
        ).strip()

        cod_item = norm_cod_item(
            item.get("cod_item")
        )

        vl_item = dec_any(
            item.get("vl_item")
        )

        # Identificador local estável durante esta execução.
        item["_match_local_id"] = posicao

        if chave_nfe:
            mapa_por_chave[chave_nfe].append(item)

        if chave_nfe and num_item and cod_item:
            mapa_full.setdefault(
                (chave_nfe, num_item, cod_item),
                [],
            ).append(item)

        if chave_nfe and cod_item:
            mapa_cod[
                (chave_nfe, cod_item)
            ].append(item)

            mapa_cod_valor[
                (chave_nfe, cod_item, vl_item)
            ].append(item)

        if chave_nfe:
            mapa_valor[
                (chave_nfe, vl_item)
            ].append(item)

        if chave_nfe and num_item:
            mapa_num[
                (chave_nfe, num_item)
            ].append(item)

    return {
        "itens": itens_contrib,
        "full": mapa_full,
        "cod": mapa_cod,
        "cod_valor": mapa_cod_valor,
        "valor": mapa_valor,
        "num": mapa_num,
        "por_chave": mapa_por_chave,
    }

def buscar_contrib_item_em_mapa(
    mapa_contrib: dict[str, Any],
    *,
    chave_nfe,
    num_item,
    cod_item,
    vl_item=None,
    ids_usados: set[int] | None = None,
) -> tuple[dict[str, Any] | None, str]:
    chave_nfe = only_digits(chave_nfe)
    num_item = str(num_item or "").strip()
    cod_item = norm_cod_item(cod_item)
    vl_item = dec_any(vl_item)

    usados = ids_usados if ids_usados is not None else set()

    def primeiro_disponivel(
        candidatos: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        for item in candidatos or []:
            item_id = int(item.get("_match_local_id", -1))

            if item_id >= 0 and item_id not in usados:
                return item

        return None

    # 1) Código + valor.
    if chave_nfe and cod_item:
        candidatos = mapa_contrib["cod_valor"].get(
            (chave_nfe, cod_item, vl_item),
            [],
        )

        item = primeiro_disponivel(candidatos)

        if item is not None:
            return item, "MATCH_COD_VALOR"

    # 2) Número + código, mas o valor precisa confirmar.
    if chave_nfe and num_item and cod_item:
        candidatos = mapa_contrib["full"].get(
            (chave_nfe, num_item, cod_item),
            [],
        )

        candidatos = [
            item
            for item in candidatos
            if dec_any(item.get("vl_item")) == vl_item
        ]

        item = primeiro_disponivel(candidatos)

        if item is not None:
            return item, "MATCH_FULL_VALOR"

    # 3) Mesmo valor dentro da NF.
    candidatos = mapa_contrib["valor"].get(
        (chave_nfe, vl_item),
        [],
    )

    item = primeiro_disponivel(candidatos)

    if item is not None:
        return item, "MATCH_VALOR"

    # 4) Código como fallback, ainda confirmando o valor.
    if chave_nfe and cod_item:
        candidatos = mapa_contrib["cod"].get(
            (chave_nfe, cod_item),
            [],
        )

        candidatos = [
            item
            for item in candidatos
            if dec_any(item.get("vl_item")) == vl_item
        ]

        item = primeiro_disponivel(candidatos)

        if item is not None:
            return item, "MATCH_COD_VALOR_FALLBACK"

    # NUM_ITEM isolado não deve casar.
    return None, ""
