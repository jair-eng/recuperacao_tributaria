from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models.efd_apontamento import EfdApontamento
from app.Legacy.fiscal.regras.Autocorrigivel.correcao_manual.correcoes_combustivel_manual import \
    aplicar_correcao_combustivel_c170_manual, aplicar_correcao_c170_faltante_manual

import logging

from app.legacy_icms_ipi.icms_ipi_insercao_notas_service import aplicar_correcao_c100_faltante_manual

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manual", tags=["Correção Manual"])

@router.post("/c170/combustivel/{apontamento_id}")
def aplicar_combustivel_manual(
    apontamento_id: int,
    db: Session = Depends(get_db),
):
    """
    Aplica correção manual de combustível para C170 existente.
    """
    ap = db.get(EfdApontamento, int(apontamento_id))
    if not ap:
        return {"erro": "Apontamento não encontrado"}
    ##Checando Apontamento Meta
    print("APONTAMENTO ATTRS:", ap.__dict__.keys())
    print("CAMPOS:", list(ap.__dict__.keys()))
    meta = ap.meta_json or {}
    itens = meta.get("itens") or []

    if not meta.get("permite_acao_manual"):
        return {"erro": "Ação manual não permitida para este apontamento"}

    if str(meta.get("modo_correcao") or "").strip().upper() != "MANUAL_ONLY":
        return {"erro": "Apontamento não está configurado para correção manual"}

    registros = []

    for it in itens:
        if str(it.get("bucket") or "").strip().upper() != "COMBUSTIVEL":
            continue

        if str(it.get("subbucket") or "").strip().upper() != "DIESEL":
            continue

        teses = it.get("teses_aplicaveis") or []
        if "CREDITO_PRESUMIDO" not in teses:
            continue

        rid = it.get("registro_id_c170")
        if rid:
            registros.append({"registro_id": int(rid)})

    if not registros:
        return {
            "status": "vazio",
            "msg": "Nenhum C170 elegível encontrado para correção",
        }

    res = aplicar_correcao_combustivel_c170_manual(
        db,
        versao_origem_id=int(ap.versao_id),
        itens=registros,
        apontamento_id=int(ap.id),
    )

    if res and (
            res.get("total_alterado", 0) > 0
            or res.get("status") in {"ok", "sucesso"}
    ):
        ap.resolvido = True
        db.flush()
        db.commit()

    return res



@router.post("/c170/faltante/{apontamento_id}")
def aplicar_c170_faltante_manual(
    apontamento_id: int,
    db: Session = Depends(get_db),
):
    ap = db.get(EfdApontamento, int(apontamento_id))
    if not ap:
        return {"erro": "Apontamento não encontrado"}

    logger.warning(
        "[MANUAL_C170] INICIO | apontamento_id=%s",
        apontamento_id,
    )

    meta = ap.meta_json or {}

    if not meta.get("permite_acao_manual"):
        return {"erro": "Ação manual não permitida para este apontamento"}

    logger.warning(
        "[MANUAL_C170] APONTAMENTO | id=%s | versao_id=%s | codigo=%s | meta=%s",
        ap.id,
        ap.versao_id,
        ap.codigo,
        meta,
    )

    itens_raw = meta.get("itens_contexto_filtrados") or meta.get("itens") or []

    # fallback: apontamento com item único direto na raiz do meta
    if not itens_raw and (
        meta.get("nf_icms_item_id")
        or meta.get("registro_id_c100")
        or meta.get("registro_id_ancora")
        or meta.get("linha_c100")
        or meta.get("linha_ancora")
    ):
        itens_raw = [{
            "nf_icms_item_id": meta.get("nf_icms_item_id"),
            "registro_id_c100": meta.get("registro_id_c100"),
            "linha_c100": meta.get("linha_c100"),
            "registro_id_ancora": meta.get("registro_id_ancora"),
            "linha_ancora": meta.get("linha_ancora"),
        }]
        logger.warning(
            "[MANUAL_C170] FALLBACK_ITEM_UNICO | itens_raw=%s",
            itens_raw,
        )

    itens = []

    logger.warning(
        "[MANUAL_C170] ITENS_RAW | total=%s | itens_raw=%s",
        len(itens_raw),
        itens_raw,
    )

    for it in itens_raw:
        nf_icms_item_id = int(it.get("nf_icms_item_id") or 0)
        registro_id_c100 = int(
            it.get("registro_id_c100")
            or it.get("registro_id_ancora")
            or 0
        )
        linha_c100 = int(
            it.get("linha_c100")
            or it.get("linha_ancora")
            or 0
        )

        if nf_icms_item_id <= 0:
            logger.warning(
                "[MANUAL_C170] ITEM_DESCARTADO | motivo=nf_icms_item_id_invalido | item=%s",
                it,
            )
            continue
        if registro_id_c100 <= 0:
            logger.warning(
                "[MANUAL_C170] ITEM_DESCARTADO | motivo=registro_id_c100_invalido | item=%s",
                it,
            )
            continue
        if linha_c100 <= 0:
            logger.warning(
                "[MANUAL_C170] ITEM_DESCARTADO | motivo=linha_c100_invalida | item=%s",
                it,
            )
            continue

        itens.append({
            "nf_icms_item_id": nf_icms_item_id,
            "registro_id_c100": registro_id_c100,
            "linha_c100": linha_c100,
            "registro_id_ancora": int(it.get("registro_id_ancora") or 0) or None,
            "linha_ancora": int(it.get("linha_ancora") or 0) or None,
        })

    logger.warning(
        "[MANUAL_C170] ITENS_FILTRADOS | total=%s | itens=%s",
        len(itens),
        itens,
    )

    if not itens:
        return {
            "status": "vazio",
            "msg": "Nenhum item elegível encontrado para inserção manual de C170.",
        }

    res = aplicar_correcao_c170_faltante_manual(
        db,
        versao_origem_id=int(ap.versao_id),
        itens=itens,
        apontamento_id=int(ap.id),
    )

    logger.warning("[MANUAL_C170] RESULTADO_FINAL | res=%s", res)

    alterou = (
        (res or {}).get("total_alterado", 0) > 0
        or (res or {}).get("insert_criado", 0) > 0
        or (res or {}).get("status") in {"ok", "sucesso"}
    )

    if alterou:
        ap.resolvido = True
        db.flush()
        db.commit()
        db.refresh(ap)
        logger.warning(
            "[MANUAL_C170] APONTAMENTO_RESOLVIDO | ap_id=%s | resolvido=%s",
            ap.id,
            ap.resolvido,
        )

    return {
        "debug_res": res
    }


@router.post("/c100/faltante/{apontamento_id}")
def aplicar_c100_faltante_manual(
    apontamento_id: int,
    db: Session = Depends(get_db),
):
    ap = db.get(EfdApontamento, int(apontamento_id))
    if not ap:
        return {"erro": "Apontamento não encontrado"}

    meta = ap.meta_json or {}

    if not meta.get("permite_acao_manual"):
        return {"erro": "Ação manual não permitida para este apontamento"}

    nf_icms_base_id = int(meta.get("nf_icms_base_id") or 0)
    nf_icms_item_ids = [int(x) for x in (meta.get("nf_icms_item_ids") or []) if int(x or 0) > 0]

    if nf_icms_base_id <= 0:
        return {"status": "vazio", "msg": "nf_icms_base_id ausente no meta"}

    res = aplicar_correcao_c100_faltante_manual(
        db,
        versao_origem_id=int(ap.versao_id),
        empresa_id=int(meta.get("empresa_id") or 0),
        nf_icms_base_id=nf_icms_base_id,
        nf_icms_item_ids=nf_icms_item_ids,
        apontamento_id=int(ap.id),
    )

    alterou = (
        (res or {}).get("c100_inserido", 0) > 0
        or (res or {}).get("total_alterado", 0) > 0
        or (res or {}).get("status") in {"ok", "sucesso"}
    )

    if alterou:
        ap.resolvido = True
        db.flush()
        db.commit()
        db.refresh(ap)

    return {"debug_res": res}