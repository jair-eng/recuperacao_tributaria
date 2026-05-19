from __future__ import annotations

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.Legacy.fiscal.constants import DOM_POSTO
from app.db.models import EfdApontamento
from app.legacy_service.c170_service import revisar_c170_lote
from app.services.dominio_service import resolver_dominio_por_versao
import logging

logger = logging.getLogger(__name__)


def aplicar_correcao_posto_credito_normal_c170(
    db: Session,
    *,
    versao_origem_id: int,
    apontamento_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Autocorreção POSTO_CREDITO_NORMAL_V1 para itens já existentes no C170.
    Atua somente em:
    - apontamentos POSTO_CREDITO_NORMAL_V1
    - itens com registro_id_c170 válido
    - C170 existente com CST/base/crédito não aproveitado
    Não trata:
    - CONTRIB_SEM_C170_V1
    - CONTRIB_SEM_C100_V1
    """

    versao_origem_id = int(versao_origem_id)

    dom = (resolver_dominio_por_versao(db, versao_origem_id) or "").strip().upper()

    if dom != DOM_POSTO:
        return {
            "status": "skip",
            "msg": f"dominio={dom} não permite POSTO_CREDITO_NORMAL_V1",
            "candidatos": 0,
            "total_alterado": 0,
            "total_erros": 0,
            "modo_usado": "POSTO_CREDITO_NORMAL_C170_EXISTENTE",
        }

    q = (
        db.query(EfdApontamento)
        .filter(EfdApontamento.versao_id == versao_origem_id)
        .filter(EfdApontamento.codigo == "POSTO_CREDITO_NORMAL_V1")
        .filter(EfdApontamento.resolvido.is_(False))
    )

    if apontamento_id:
        q = q.filter(EfdApontamento.id == int(apontamento_id))

    aps = q.all()
    logger.info(
        "[POSTO_CRED_NORMAL_FIX] aps_encontrados=%s versao=%s",
        len(aps),
        versao_origem_id,
    )
    if not aps:
        return {
            "status": "vazio",
            "msg": "Sem apontamentos POSTO_CREDITO_NORMAL_V1 pendentes.",
            "candidatos": 0,
            "total_alterado": 0,
            "total_erros": 0,
            "modo_usado": "POSTO_CREDITO_NORMAL_C170_EXISTENTE",
        }

    lote: List[Dict[str, Any]] = []
    vistos: set[int] = set()

    ignorados_sem_registro = 0
    ignorados_sem_oportunidade = 0
    ignorados_nao_autofix = 0

    situacoes_ok = {
        "CST_NAO_CREDITAVEL",
        "BASE_ZERADA",
        "CREDITO_NAO_APROVEITADO",
    }

    for ap in aps:
        meta = dict(ap.meta_json or {})

        if not bool(meta.get("permite_autocorrecao") or meta.get("permite_auto_fix")):
            ignorados_nao_autofix += 1
            continue

        itens = list(meta.get("itens") or [])

        for it in itens:
            if not isinstance(it, dict):
                continue

            registro_id = int(
                it.get("registro_id_c170")
                or it.get("registro_id")
                or 0
            )

            situacao_principal = str(
                it.get("situacao_credito_principal") or ""
            ).strip().upper()
            logger.debug(
                "[POSTO_CRED_NORMAL_FIX] item entrada | ap=%s registro_id=%s situacao=%s permite_fix=%s",
                ap.id,
                it.get("registro_id_c170") or it.get("registro_id"),
                it.get("situacao_credito_principal"),
                meta.get("permite_autocorrecao") or meta.get("permite_auto_fix"),
            )

            if situacao_principal not in situacoes_ok:
                logger.warning(
                    "[POSTO_CRED_NORMAL_FIX] skip situacao | ap=%s situacao=%s",
                    ap.id,
                    situacao_principal,
                )
                ignorados_sem_oportunidade += 1
                continue

            if registro_id <= 0:
                logger.warning(
                    "[POSTO_CRED_NORMAL_FIX] skip registro_id | ap=%s item=%s",
                    ap.id,
                    it,
                )
                ignorados_sem_registro += 1
                continue

            if registro_id in vistos:
                continue
            vistos.add(registro_id)


            lote.append({
                "registro_id": registro_id,
                "cfop": None,

                # POSTO crédito normal
                "cst_pis": str(it.get("cst_pis_sugerido") or "50"),
                "cst_cofins": str(it.get("cst_cofins_sugerido") or "50"),

                # deixa pronto caso revisar_c170_lote/patch aceite esses campos
                "vl_bc_pis": str(it.get("base_credito_sugerida") or ""),
                "aliq_pis": str(it.get("aliq_pis_sugerida") or "1,65"),
                "vl_pis": str(it.get("pis_estimado") or ""),

                "vl_bc_cofins": str(it.get("base_credito_sugerida") or ""),
                "aliq_cofins": str(it.get("aliq_cofins_sugerida") or "7,60"),
                "vl_cofins": str(it.get("cofins_estimado") or ""),
            })

    if not lote:
        return {
            "status": "vazio",
            "msg": "Sem candidatos corrigíveis após filtros.",
            "candidatos": 0,
            "ignorados_sem_registro": ignorados_sem_registro,
            "ignorados_nao_autofix": ignorados_nao_autofix,
            "ignorados_sem_oportunidade": ignorados_sem_oportunidade,
            "total_alterado": 0,
            "total_erros": 0,
            "modo_usado": "POSTO_CREDITO_NORMAL_C170_EXISTENTE",
        }

    res = revisar_c170_lote(
        db,
        versao_origem_id=versao_origem_id,
        alteracoes=lote,
        motivo_codigo="POSTO_CREDITO_NORMAL_V1",
        apontamento_id=apontamento_id,
    )
    logger.info(
        "[POSTO_CRED_NORMAL_FIX] resultado | alterado=%s erros=%s detalhe=%s",
        res.get("total_alterado"),
        res.get("total_erros"),
        res.get("erros_detalhe"),
    )

    return {
        "status": "ok" if int(res.get("total_alterado") or 0) > 0 else "vazio",
        "candidatos": len(lote),
        "ignorados_sem_registro": ignorados_sem_registro,
        "ignorados_nao_autofix": ignorados_nao_autofix,
        "ignorados_sem_oportunidade": ignorados_sem_oportunidade,
        "total_alterado": int(res.get("total_alterado") or 0),
        "total_ignorado_pf": int(res.get("total_ignorado_pf") or 0),
        "total_erros": int(res.get("total_erros") or 0),
        "erros_detalhe": res.get("erros_detalhe") or [],
        "registro_ids_alterados": [int(x["registro_id"]) for x in lote],
        "modo_usado": "POSTO_CREDITO_NORMAL_C170_EXISTENTE",
    }