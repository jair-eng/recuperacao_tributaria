from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.db.models import EfdApontamento, EfdRevisao, NfIcmsItem
from app.db.models.nf_icms_base import NfIcmsBase
from app.db.models.item_fiscal_consolidado import ItemFiscalConsolidado
from app.icms_ipi.icms_c170_utils import _criar_revisao_insert_c170_faltante_v2
from app.legacy_icms_ipi.icms_ipi_insercao_notas_service import _inserir_bloco_nf_icms_na_efd, \
    _resolver_ancora_bloco_c_fim
from app.legacy_service.c170_service import revisar_c170_lote

from app.sped.bloco_0.bloco_0_0190_0200_agregador import (
    _garantir_mestres_para_notas_elegiveis,
)
import logging

from app.utils.numbers import fmt_aliq_sped

logger = logging.getLogger(__name__)


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
            cache=cache,
        )

    if status_cruzamento in {"MATCH"}:
        return _aplicar_corretiva_match_patch_c170_v2(
            db=db,
            apontamento=apontamento,
            item=item,
            meta=meta,
            cache=cache,
        )



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
    cache: dict | None = None,
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
        cache_mestres=(cache or {}).get("cache_mestres"),
    )

    enq = meta.get("enquadramento") or {}

    contexto = (
        meta.get("codigo_cenario")
        or meta.get("cenario")
        or meta.get("contexto_credito")
    )

    aliq_pis = fmt_aliq_sped(enq.get("aliq_pis") or "")
    aliq_cofins = fmt_aliq_sped(enq.get("aliq_cofins") or "")

    tipo_corretiva_v2 = meta.get("tipo_corretiva_v2")
    tipo_normalizacao = meta.get("tipo_normalizacao")

    registro_id_c100 = (
        meta.get("registro_id_c100")
        or getattr(item, "registro_id_c100", None)
    )

    linha_c100 = (
        meta.get("linha_c100")
        or getattr(item, "linha_c100", None)
        or 0
    )

    contrib_tem_c100 = bool(
        meta.get("contrib_tem_c100")
        or registro_id_c100
    )

    cod_cred = (
        enq.get("cod_cred")
        or enq.get("tipo_credito_codigo")
        or meta.get("cod_cred")
        or meta.get("tipo_credito_codigo")
        or getattr(item, "cod_cred", None)
        or getattr(item, "tipo_credito_codigo", None)
    )

    nat_bc_cred = (
        enq.get("nat_bc_cred")
        or enq.get("base_credito_codigo")
        or enq.get("cod_base_credito")
        or meta.get("nat_bc_cred")
        or meta.get("base_credito_codigo")
        or meta.get("cod_base_credito")
        or getattr(item, "nat_bc_cred", None)
        or getattr(item, "base_credito_codigo", None)
        or getattr(item, "cod_base_credito", None)
    )
    cst_pis_destino = (
            meta.get("cst_pis_destino")
            or enq.get("cst_pis_destino")
    )

    cst_cofins_destino = (
            meta.get("cst_cofins_destino")
            or enq.get("cst_cofins_destino")
    )

    if not cod_cred or not nat_bc_cred:
        logger.warning(
            "[SO_ICMS_V2] ENQ INCOMPLETO | ap=%s item=%s cod=%s nat=%s enq=%s",
            apontamento.id,
            item.id,
            cod_cred,
            nat_bc_cred,
            enq,
        )

    logger.warning(
        "[SO_ICMS_V2] DECISAO | ap=%s item=%s tipo=%s normalizacao=%s contrib_tem_c100=%s reg_c100=%s linha_c100=%s chave=%s",
        apontamento.id,
        item.id,
        tipo_corretiva_v2,
        tipo_normalizacao,
        contrib_tem_c100,
        registro_id_c100,
        linha_c100,
        chave,
    )

    # ------------------------------------------------------------
    # Caso 1: C100 existe na EFD -> inserir apenas C170
    # ------------------------------------------------------------
    if contrib_tem_c100:
        if tipo_corretiva_v2 == "INSERIR_C100_C170":
            logger.warning(
                "[SO_ICMS_V2] META INCONSISTENTE | ap=%s diz INSERIR_C100_C170 mas C100 existe reg_c100=%s",
                apontamento.id,
                registro_id_c100,
            )

        registro_id_alvo = (
            meta.get("registro_id_ancora")
            or registro_id_c100
        )

        linha_ref = (
            meta.get("linha_ancora")
            or linha_c100
            or 0
        )

        if not registro_id_alvo:
            return {
                "ok": False,
                "status": "erro",
                "msg": "C100 existe, mas sem registro_id_ancora/registro_id_c100 para inserir C170.",
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
            cst_pis_destino=cst_pis_destino,
            cst_cofins_destino=cst_cofins_destino,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
            cod_cred=cod_cred,
            nat_bc_cred=nat_bc_cred,
            motivo_codigo="CORRETIVA_V2_SO_ICMS",
            apontamento_id=int(apontamento.id),
        )

        if not rv_c170:
            return {
                "ok": False,
                "status": "skip",
                "msg": "C100 existe, mas não foi possível criar revisão C170.",
                "chave_nfe": chave,
                "tipo_corretiva": "INSERIR_C170_EM_C100_EXISTENTE",
            }

        res_bloco = {
            "c100_inserido": 0,
            "c170_inseridos": 1,
            "revisao_c170_id": int(rv_c170.id),
            "registro_id_alvo": int(registro_id_alvo),
        }

        tipo_resultado = "INSERIR_C170_EM_C100_EXISTENTE"

    # ------------------------------------------------------------
    # Caso 2: C100 não existe na EFD -> inserir bloco C100 + C170
    # ------------------------------------------------------------
    else:
        if tipo_corretiva_v2 == "INSERIR_C170_EM_C100_EXISTENTE":
            logger.warning(
                "[SO_ICMS_V2] META INCONSISTENTE | ap=%s diz INSERIR_C170_EM_C100_EXISTENTE mas C100 não existe",
                apontamento.id,
            )

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
            cod_cred=cod_cred,
            nat_bc_cred=nat_bc_cred,
            motivo_codigo="CORRETIVA_V2_SO_ICMS",
        )

        tipo_resultado = "INSERIR_C100_C170"

    apontamento.resolvido = True
    db.add(apontamento)
    db.flush()

    return {
        "ok": True,
        "status": "OK",
        "tipo_corretiva": tipo_resultado,
        "apontamento_id": int(apontamento.id),
        "versao_id": versao_id,
        "item_fiscal_consolidado_id": int(item.id),
        "nf_icms_base_id": int(nf.id),
        "nf_icms_item_id": int(nf_icms_item_id),
        "chave_nfe": chave,
        "mestres": res_mestres,
        "resultado": res_bloco,
        "msg": "Corretiva V2 SO_ICMS aplicada.",
    }

def _aplicar_corretiva_match_patch_c170_v2(
    db: Session,
    *,
    apontamento: EfdApontamento,
    item: ItemFiscalConsolidado,
    meta: Dict[str, Any],
    cache: dict | None = None,
) -> Dict[str, Any]:
    logger.info(
        "[MATCH_V2] status=%s ap=%s reg_c170=%s",
        meta.get("status_cruzamento"),
        apontamento.id,
        meta.get("registro_id_c170"),
    )

    versao_id = int(apontamento.versao_id)
    logger.info(
        "[MATCH_V2] inicio | ap=%s registro_c170=%s item=%s",
        apontamento.id,
        meta.get("registro_id_c170"),
        item.id,
    )
    registro_id_c170 = (
        meta.get("registro_id_c170")
        or meta.get("registro_id_ancora")
        or getattr(item, "registro_id_c170", None)
    )

    if not registro_id_c170:
        return {
            "ok": False,
            "status": "erro",
            "msg": "MATCH sem registro_id_c170 para PATCH_C170_EXISTENTE.",
            "tipo_corretiva": "PATCH_C170_EXISTENTE",
        }

    meta_fiscal = meta.get("meta_fiscal") or {}

    enq = (
            meta_fiscal.get("enquadramento")
            or meta.get("enquadramento")
            or {}  )

    logger.info(
        "[MATCH_V2] enquadramento tipos | "
        "aliq_pis=%r tipo=%s | aliq_cofins=%r tipo=%s",
        enq.get("aliq_pis"),
        type(enq.get("aliq_pis")).__name__,
        enq.get("aliq_cofins"),
        type(enq.get("aliq_cofins")).__name__,
    )
    codigo_cenario = (
            meta_fiscal.get("codigo_cenario")
            or meta.get("codigo_cenario")
            or meta.get("cenario")
    )

    cod_cred = (
            meta_fiscal.get("cod_cred")
            or meta_fiscal.get("tipo_credito_codigo")
            or enq.get("tipo_credito_codigo")
            or enq.get("cod_cred")
    )

    nat_bc_cred = (
            meta_fiscal.get("nat_bc_cred")
            or meta_fiscal.get("base_credito_codigo")
            or enq.get("base_credito_codigo")
            or enq.get("nat_bc_cred")
    )

    cst_pis_destino = (
            meta.get("cst_pis_destino")
            or meta_fiscal.get("cst_pis_destino")
            or enq.get("cst_pis_destino")
    )

    cst_cofins_destino = (
            meta.get("cst_cofins_destino")
            or meta_fiscal.get("cst_cofins_destino")
            or enq.get("cst_cofins_destino")
    )
    cst_pis_destino = (
        str(cst_pis_destino).strip().zfill(2)
        if cst_pis_destino not in (None, "")
        else None
    )

    cst_cofins_destino = (
        str(cst_cofins_destino).strip().zfill(2)
        if cst_cofins_destino not in (None, "")
        else None
    )

    aliq_pis = fmt_aliq_sped(enq.get("aliq_pis") or "")
    aliq_cofins = fmt_aliq_sped(enq.get("aliq_cofins") or "")

    alteracao = {
        "registro_id": int(registro_id_c170),
        "cfop": None,

        "cst_pis": cst_pis_destino,
        "cst_cofins": cst_cofins_destino,

        # Não enviar base pronta.
        # O patch_c170_campos calcula pela regra:
        # VL_ITEM - VL_DESC - VL_ICMS
        "vl_bc_pis": None,
        "aliq_pis": aliq_pis,
        "vl_pis": None,

        "vl_bc_cofins": None,
        "aliq_cofins": aliq_cofins,
        "vl_cofins": None,

        "meta_fiscal": {
            **meta_fiscal,
            "codigo_cenario": codigo_cenario,
            "cenario": codigo_cenario,
            "enquadramento": {
                **enq,
                "cst_pis_destino": cst_pis_destino,
                "cst_cofins_destino": cst_cofins_destino,
                "cst_pis": cst_pis_destino,
                "cst_cofins": cst_cofins_destino,
                "aliq_pis": aliq_pis,
                "aliq_cofins": aliq_cofins,
            },
            "cst_pis_destino": cst_pis_destino,
            "cst_cofins_destino": cst_cofins_destino,
            "cst_pis": cst_pis_destino,
            "cst_cofins": cst_cofins_destino,
            "aliq_pis": aliq_pis,
            "aliq_cofins": aliq_cofins,
            "cod_cred": cod_cred,
            "tipo_credito_codigo": cod_cred,
            "nat_bc_cred": nat_bc_cred,
            "base_credito_codigo": nat_bc_cred,
            "cod_base_credito": nat_bc_cred,
            "contexto_credito": codigo_cenario,
            "natureza_credito_m": nat_bc_cred,
        },

        "codigo_cenario": codigo_cenario,
        "contexto": codigo_cenario,
        "cod_cred": cod_cred,
        "nat_bc_cred": nat_bc_cred,
        "natureza_credito_m": nat_bc_cred,
        "dominio": meta.get("dominio"),
    }

    res = revisar_c170_lote(
        db,
        versao_origem_id=versao_id,
        alteracoes=[alteracao],
        motivo_codigo="CREDITO_NAO_APROVEITADO_V2",
        apontamento_id=int(apontamento.id),
        garantir_hierarquia=False,
    )

    total_alterado = int(res.get("total_alterado") or 0)

    if total_alterado <= 0:
        return {
            "ok": False,
            "status": "skip",
            "msg": "MATCH encontrado, mas revisão PATCH_C170_EXISTENTE não foi criada.",
            "tipo_corretiva": "PATCH_C170_EXISTENTE",
            "resultado": res,
        }

    apontamento.resolvido = True
    db.add(apontamento)
    db.flush()

    return {
        "ok": True,
        "status": "OK",
        "tipo_corretiva": "PATCH_C170_EXISTENTE",
        "apontamento_id": int(apontamento.id),
        "versao_id": versao_id,
        "item_fiscal_consolidado_id": int(item.id),
        "registro_id_c170": int(registro_id_c170),
        "resultado": res,
        "msg": "Corretiva V2 MATCH aplicada: C170 existente ajustado via revisão.",
    }