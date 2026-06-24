from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.models import EfdApontamento, EfdRevisao, NfIcmsItem
from app.db.models.nf_icms_base import NfIcmsBase
from app.db.models.item_fiscal_consolidado import ItemFiscalConsolidado
from app.icms_ipi.icms_c170_utils import _criar_revisao_insert_c170_faltante_v2
from app.legacy_icms_ipi.icms_ipi_insercao_notas_service import _inserir_bloco_nf_icms_na_efd, \
    _resolver_ancora_bloco_c_fim

from app.sped.bloco_0.bloco_0_0190_0200_agregador import (
    _garantir_mestres_para_notas_elegiveis,
)


def aplicar_corretiva_apontamento_v2(
    db: Session,
    *,
    apontamento_id: int,
    cache: dict | None = None,
) -> Dict[str, Any]:

    apontamento = (
        db.query(EfdApontamento)
        .filter(EfdApontamento.id == int(apontamento_id))
        .first()
    )

    if not apontamento:
        return {"ok": False, "status": "erro", "msg": "Apontamento não encontrado"}

    meta = apontamento.meta_json or {}

    item_id = (
        apontamento.item_fiscal_consolidado_id
        or meta.get("item_fiscal_consolidado_id")
    )

    if not item_id:
        return {"ok": False, "status": "erro", "msg": "Apontamento sem item fiscal consolidado"}

    item = (
        db.query(ItemFiscalConsolidado)
        .filter(ItemFiscalConsolidado.id == int(item_id))
        .first()
    )

    if not item:
        return {"ok": False, "status": "erro", "msg": "ItemFiscalConsolidado não encontrado"}

    status_cruzamento = str(
        meta.get("status_cruzamento")
        or getattr(item, "status_cruzamento", "")
        or ""
    ).upper()

    if status_cruzamento == "SO_ICMS":
        return _aplicar_corretiva_so_icms_v2(
            db=db,
            apontamento=apontamento,
            item=item,
            meta=meta,
        )

    if status_cruzamento == "MATCH":
        return {
            "ok": False,
            "status": "pendente",
            "msg": "Corretiva MATCH ainda não implementada. Futuro: patch C170 existente.",
            "tipo_corretiva": "PATCH_C170_EXISTENTE",
        }

    return {
        "ok": False,
        "status": "skip",
        "msg": f"Status de cruzamento não suportado para corretiva V2: {status_cruzamento}",
    }


def _aplicar_corretiva_so_icms_v2(
    db: Session,
    *,
    apontamento: EfdApontamento,
    item: ItemFiscalConsolidado,
    meta: Dict[str, Any],
) -> Dict[str, Any]:

    versao_id = int(apontamento.versao_id)

    nf_icms_item_id = (
        meta.get("nf_icms_item_id")
        or getattr(item, "nf_icms_item_id", None)
    )

    if not nf_icms_item_id:
        return {"ok": False, "status": "erro", "msg": "SO_ICMS sem nf_icms_item_id"}

    nf_item = (
        db.query(NfIcmsItem)
        .filter(NfIcmsItem.id == int(nf_icms_item_id))
        .first()
    )

    if not nf_item:
        return {"ok": False, "status": "erro", "msg": "NfIcmsItem não encontrado"}

    nf_base_id = getattr(nf_item, "nf_icms_base_id", None)

    if not nf_base_id:
        return {"ok": False, "status": "erro", "msg": "NfIcmsItem sem nf_icms_base_id"}

    nf = (
        db.query(NfIcmsBase)
        .filter(NfIcmsBase.id == int(nf_base_id))
        .first()
    )

    if not nf:
        return {"ok": False, "status": "erro", "msg": "NfIcmsBase não encontrada"}

    chave = str(getattr(nf, "chave_nfe", "") or "").strip()

    res_mestres = _garantir_mestres_para_notas_elegiveis(
        db,
        versao_origem_id=versao_id,
        notas_elegiveis=[(nf, [nf_item], chave)],
    )

    enq = meta.get("enquadramento") or {}
    contexto = meta.get("codigo_cenario") or meta.get("cenario")
    aliq_pis = str(enq.get("aliq_pis") or "")
    aliq_cofins = str(enq.get("aliq_cofins") or "")

    tipo_corretiva_v2 = meta.get("tipo_corretiva_v2")
    tipo_normalizacao = meta.get("tipo_normalizacao")

    c100_ja_existe = (
            tipo_corretiva_v2 == "INSERIR_C170_EM_C100_EXISTENTE"
            or tipo_normalizacao == "CONTRIB_SEM_C170"
    )

    if c100_ja_existe:
        registro_id_alvo = (
                meta.get("registro_id_ancora")
                or meta.get("registro_id_c100")
        )

        linha_ref = (
                meta.get("linha_ancora")
                or meta.get("linha_c100")
                or 0
        )

        if not registro_id_alvo:
            return {
                "ok": False,
                "status": "erro",
                "msg": "CONTRIB_SEM_C170 sem registro_id_ancora/registro_id_c100 no apontamento.",
                "chave_nfe": chave,
                "tipo_corretiva": "INSERIR_C170_EM_C100_EXISTENTE",
            }

        rv_c170 = _criar_revisao_insert_c170_faltante_v2(
            db,
            versao_origem_id=versao_id,
            registro_id_alvo=registro_id_alvo,
            linha_ref=linha_ref,
            item_icms=nf_item,
            contexto=contexto,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
            cod_cred=enq.get("cod_cred"),
            nat_bc_cred=enq.get("nat_bc_cred"),
            apontamento_id=int(apontamento.id),
        )

        if not rv_c170:
            return {
                "ok": False,
                "status": "skip",
                "msg": "C100 já existe, mas não foi possível criar revisão C170.",
                "chave_nfe": chave,
                "tipo_corretiva": "INSERIR_C170_EM_C100_EXISTENTE",
            }

        res_bloco = {
            "c100_inserido": 0,
            "c170_inseridos": 1,
            "revisao_c170_id": int(rv_c170.id),
            "registro_id_alvo": int(registro_id_alvo),
        }

    else:
        registro_id_alvo, linha_ref_alvo, acao_inicial = _resolver_ancora_bloco_c_fim(
            db,
            versao_origem_id=versao_id,
        )

        res_bloco = _inserir_bloco_nf_icms_na_efd(
            db,
            versao_origem_id=versao_id,
            nf=nf,
            itens=[nf_item],
            registro_id_alvo=registro_id_alvo,
            linha_ref_alvo=linha_ref_alvo,
            acao_inicial=acao_inicial,
            apontamento_id=int(apontamento.id),
            contexto=contexto,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
            cod_cred=enq.get("cod_cred"),
            nat_bc_cred=enq.get("nat_bc_cred"),
            motivo_codigo="CORRETIVA_V2_SO_ICMS",
        )


    apontamento.resolvido = True
    db.add(apontamento)
    db.flush()

    return {
        "ok": True,
        "status": "OK",
        "tipo_corretiva": "INSERIR_C170_EM_C100_EXISTENTE" if c100_ja_existe else "INSERIR_C100_C170",
        "apontamento_id": int(apontamento.id),
        "versao_id": versao_id,
        "item_fiscal_consolidado_id": int(item.id),
        "nf_icms_base_id": int(nf.id),
        "nf_icms_item_id": int(nf_icms_item_id),
        "chave_nfe": chave,
        "mestres": res_mestres,
        "resultado": res_bloco,
        "msg": "Corretiva V2 SO_ICMS aplicada: C100/C170 propostos via revisão.",
    }