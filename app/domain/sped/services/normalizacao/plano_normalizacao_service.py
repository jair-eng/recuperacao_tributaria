from collections import defaultdict

from app.db.models import ItemFiscalConsolidado


def gerar_plano_normalizacao(db, versao_id: int):
    itens = (
        db.query(ItemFiscalConsolidado)
        .filter(
            ItemFiscalConsolidado.versao_id == versao_id,
            ItemFiscalConsolidado.status_cruzamento == "SO_ICMS",
        )
        .all()
    )

    plano = defaultdict(list)

    for item in itens:
        meta = item.meta or {}
        tipo = meta.get("tipo_normalizacao") or "INDEFINIDO"

        plano[tipo].append({
            "item_id": item.id,
            "chave_nfe": item.chave_nfe,
            "modelo": item.cod_mod,
            "num_item": item.num_item,
            "cod_item": item.cod_item,
            "descricao": item.descr_item,
            "ncm": item.ncm,
            "cfop": item.cfop,
            "vl_item": float(item.vl_item or 0),
            "participante_nome": item.participante_nome,
        })

    return dict(plano)

def gerar_plano_c100_c170_faltante(db, versao_id: int):
    itens = (
        db.query(ItemFiscalConsolidado)
        .filter(
            ItemFiscalConsolidado.versao_id == versao_id,
            ItemFiscalConsolidado.status_cruzamento == "SO_ICMS",
            ItemFiscalConsolidado.cod_mod == "55",
        )
        .order_by(
            ItemFiscalConsolidado.chave_nfe,
            ItemFiscalConsolidado.num_item,
        )
        .all()
    )

    plano = {}

    for item in itens:
        chave = item.chave_nfe

        if chave not in plano:
            plano[chave] = {
                "chave_nfe": item.chave_nfe,
                "modelo": item.cod_mod,
                "participante_nome": item.participante_nome,
                "participante_doc": item.participante_doc,
                "itens": [],
            }

        plano[chave]["itens"].append({
            "item_id": item.id,
            "nf_icms_item_id": item.nf_icms_item_id,
            "num_item": item.num_item,
            "cod_item": item.cod_item,
            "descricao": item.descr_item,
            "ncm": item.ncm,
            "cfop": item.cfop,
            "cst_icms": item.cst_icms,
            "vl_item": float(item.vl_item or 0),
            "vl_desc": float(item.vl_desc or 0),
            "vl_icms": float(item.vl_icms or 0),
        })

    return plano

def gerar_plano_d100_faltante(db, versao_id: int):
    itens = (
        db.query(ItemFiscalConsolidado)
        .filter(
            ItemFiscalConsolidado.versao_id == versao_id,
            ItemFiscalConsolidado.status_cruzamento == "SO_ICMS",
            ItemFiscalConsolidado.cod_mod == "57",
        )
        .order_by(ItemFiscalConsolidado.chave_nfe)
        .all()
    )

    plano = {}

    for item in itens:
        chave = item.chave_nfe

        if chave not in plano:
            plano[chave] = {
                "chave_nfe": item.chave_nfe,
                "modelo": item.cod_mod,
                "participante_nome": item.participante_nome,
                "participante_doc": item.participante_doc,
                "cfop": item.cfop,
                "itens": [],
            }

        plano[chave]["itens"].append({
            "item_id": item.id,
            "nf_icms_item_id": item.nf_icms_item_id,
            "descricao": item.descr_item,
            "cfop": item.cfop,
            "vl_item": float(item.vl_item or 0),
            "vl_icms": float(item.vl_icms or 0),
        })

    return plano