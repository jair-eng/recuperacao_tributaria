from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.domain.relatorio_executivo.IcmsContribuicao.icms_item_map_local import montar_mapa_contrib_item_local, \
    buscar_contrib_item_em_mapa
from app.utils.numbers import to_decimal
from app.utils.sped import chave_match_num_item, chave_match_item
from app.utils.strings import only_digits, norm_cod_item, s



def indexar_c170_contrib_local(
    c170_contrib: list[dict[str, Any]],
) -> dict[str, dict[Any, list[dict[str, Any]]]]:
    idx = {
        "item": defaultdict(list),
        "num_item": defaultdict(list),
        "chave": defaultdict(list),
    }

    for item in c170_contrib:
        chave = item.get("chv_nfe") or item.get("chave")

        if not chave:
            continue

        idx["chave"][chave].append(item)

        k_item = chave_match_item(item)
        if k_item[0] and k_item[1]:
            idx["item"][k_item].append(item)

        k_num_item = chave_match_num_item(item)
        if k_num_item[0] and k_num_item[1]:
            idx["num_item"][k_num_item].append(item)

    return idx


def localizar_match_c170_contrib(
    item_icms: dict[str, Any],
    idx: dict[str, dict[Any, list[dict[str, Any]]]],
) -> tuple[dict[str, Any] | None, str]:
    k_item = chave_match_item(item_icms)
    candidatos = idx["item"].get(k_item) or []

    if candidatos:
        return candidatos[0], "MATCH_ITEM"

    k_num_item = chave_match_num_item(item_icms)
    candidatos = idx["num_item"].get(k_num_item) or []

    if candidatos:
        return candidatos[0], "MATCH_NUM_ITEM"

    chave = item_icms.get("chv_nfe") or item_icms.get("chave")
    candidatos = idx["chave"].get(chave) or []

    if len(candidatos) == 1:
        return candidatos[0], "MATCH_CHAVE"

    return None, ""


def cruzar_c170_icms_contrib_local(
    *,
    c170_icms: list[dict[str, Any]],
    c170_contrib: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    idx = indexar_c170_contrib_local(c170_contrib)

    resultado = []
    stats = defaultdict(int)

    mapa_contrib = montar_mapa_contrib_item_local(
        c170_contrib
    )

    ids_contrib_usados: set[int] = set()

    for item_icms in c170_icms:
        texto_item = " ".join(
            [
                str(item_icms.get("cod_item") or ""),
                str(item_icms.get("descr_item") or ""),
                str(item_icms.get("descr_compl") or ""),
                str(item_icms.get("ncm") or ""),
                str(item_icms.get("cod_ncm") or ""),
            ]
        ).upper()

        eh_diesel = (
                "DIESEL" in texto_item
                or str(item_icms.get("ncm") or "").startswith("271019")
                or str(item_icms.get("cod_ncm") or "").startswith("271019")
        )

        if eh_diesel:
            print(
                "[DBG DIESEL ENTRADA CRUZAMENTO]",
                {
                    "arquivo": item_icms.get("arquivo"),
                    "periodo": item_icms.get("periodo"),
                    "ind_oper": item_icms.get("ind_oper"),
                    "chv_nfe": item_icms.get("chv_nfe"),
                    "num_item": item_icms.get("num_item"),
                    "cod_item": item_icms.get("cod_item"),
                    "descricao": item_icms.get("descr_item"),
                    "ncm": item_icms.get("ncm"),
                    "cfop": item_icms.get("cfop"),
                    "vl_item": item_icms.get("vl_item"),
                },
            )
        if item_icms.get("ind_oper") != "0":
            continue

        # --------------------------------------------------
        # Novo motor de match (espelhando o materializador)
        # --------------------------------------------------
        match, tipo_match = buscar_contrib_item_em_mapa(
            mapa_contrib,
            chave_nfe=item_icms.get("chv_nfe"),
            num_item=item_icms.get("num_item"),
            cod_item=item_icms.get("cod_item"),
            vl_item=item_icms.get("vl_item"),
            ids_usados=ids_contrib_usados,
        )

        if eh_diesel:
            print(
                "[DBG DIESEL RESULTADO MATCH]",
                {
                    "periodo": item_icms.get("periodo"),
                    "cod_item_icms": item_icms.get("cod_item"),
                    "vl_item_icms": item_icms.get("vl_item"),
                    "match": bool(match),
                    "tipo_match": tipo_match,
                    "cod_item_contrib": (
                        match.get("cod_item")
                        if match
                        else None
                    ),
                    "vl_item_contrib": (
                        match.get("vl_item")
                        if match
                        else None
                    ),
                },
            )

        # Fallback temporário para comparação
        if match is None:
            match, tipo_match = localizar_match_c170_contrib(
                item_icms,
                idx,
            )

        if match:
            ids_contrib_usados.add(match["_match_local_id"])

        if match:
            ids_contrib_usados.add(match["_match_local_id"])

        item_contrib = match or {}

        status = "MATCH" if match else "NAO_ESCRITURADO"

        stats[status] += 1
        stats[tipo_match or "SEM_MATCH"] += 1

        resultado.append(
            {
                "periodo": item_icms.get("periodo") or item_contrib.get("periodo"),
                "status_cruzamento": status,
                "tipo_match": tipo_match,
                "match_encontrado": bool(match),

                "chv_nfe": item_icms.get("chv_nfe") or item_contrib.get("chv_nfe"),
                "num_doc": item_icms.get("num_doc") or item_contrib.get("num_doc"),
                "num_item": item_icms.get("num_item") or item_contrib.get("num_item"),
                "cod_item": item_icms.get("cod_item") or item_contrib.get("cod_item"),
                "descricao": (
                    item_icms.get("descr_item")
                    or item_icms.get("descr_compl")
                    or item_contrib.get("descr_item")
                    or item_contrib.get("descr_compl")
                ),
                "ncm": item_icms.get("ncm") or item_contrib.get("ncm"),
                "cfop": item_icms.get("cfop") or item_contrib.get("cfop"),
                "cod_cta": item_contrib.get("cod_cta") or item_icms.get("cod_cta"),

                "valor_item_icms": to_decimal(item_icms.get("vl_item")),
                "valor_desc_icms": to_decimal(item_icms.get("vl_desc")),
                "valor_icms": to_decimal(item_icms.get("vl_icms")),
                "valor_ipi": to_decimal(item_icms.get("vl_ipi")),

                "cst_pis": item_contrib.get("cst_pis") or "SEM_EFD",
                "vl_bc_pis": to_decimal(item_contrib.get("vl_bc_pis")),
                "vl_pis": to_decimal(item_contrib.get("vl_pis")),
                "cst_cofins": item_contrib.get("cst_cofins") or "SEM_EFD",
                "vl_bc_cofins": to_decimal(item_contrib.get("vl_bc_cofins")),
                "vl_cofins": to_decimal(item_contrib.get("vl_cofins")),

                "icms": item_icms,
                "contrib": match,
            }
        )

    print("[MATCH C170]", dict(stats))

    return resultado