from __future__ import annotations

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.Legacy.fiscal.constants import DOM_TRANSP
from app.db.models import EfdApontamento
from app.legacy_service.c170_service import revisar_c170_lote
from app.services.dominio_service import resolver_dominio_por_versao


def aplicar_correcao_transp_insumo_c170(
    db: Session,
    *,
    versao_origem_id: int,
    apontamento_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Autocorreção da transportadora para itens já existentes no C170.

    Atua somente em:
    - apontamentos TRANSP_INSUMO_V1
    - itens elegivel autofix
    - itens com registro_id válido (MATCH / C170 existente)

    Não trata:
    - CONTRIB_SEM_C170_V1
    - CONTRIB_SEM_C100_V1
    """

    versao_origem_id = int(versao_origem_id)

    dom = (resolver_dominio_por_versao(db, versao_origem_id) or "").strip().upper()
    if dom != DOM_TRANSP:
        return {
            "status": "skip",
            "msg": f"dominio={dom} não permite TRANSP_INSUMO_V1",
            "candidatos": 0,
            "total_alterado": 0,
            "total_erros": 0,
            "modo_usado": "TRANSP_MATCH",
        }

    q = (
        db.query(EfdApontamento)
        .filter(EfdApontamento.versao_id == versao_origem_id)
        .filter(EfdApontamento.codigo == "TRANSP_INSUMO_V1")
        .filter(EfdApontamento.resolvido.is_(False))
    )

    if apontamento_id:
        q = q.filter(EfdApontamento.id == int(apontamento_id))

    aps = q.all()
    if not aps:
        return {
            "status": "vazio",
            "msg": "Sem apontamentos TRANSP_INSUMO_V1 pendentes.",
            "candidatos": 0,
            "total_alterado": 0,
            "total_erros": 0,
            "modo_usado": "TRANSP_MATCH",
        }

    lote: List[Dict[str, Any]] = []
    vistos: set[int] = set()
    ignorados_sem_registro = 0
    ignorados_nao_autocorrigiveis = 0
    ignorados_sem_oportunidade = 0

    for ap in aps:
        meta = dict(ap.meta_json or {})
        itens = list(meta.get("itens") or [])

        for it in itens:
            if not isinstance(it, dict):
                continue

            registro_id = int(it.get("registro_id") or 0)
            #tipo_insumo = str(it.get("tipo_insumo") or "").strip().upper()
            situacao_principal = str(it.get("situacao_credito_principal") or "").strip().upper()

            elegivel_autofix = bool(it.get("elegivel_autofix"))

            if not elegivel_autofix:
                ignorados_nao_autocorrigiveis += 1
                continue

            if situacao_principal not in {
                "CST_NAO_CREDITAVEL",
                "BASE_ZERADA",
                "CREDITO_NAO_APROVEITADO",
            }:
                ignorados_sem_oportunidade += 1
                continue

            if registro_id <= 0:
                ignorados_sem_registro += 1
                continue

            if registro_id in vistos:
                continue
            vistos.add(registro_id)

            # nesta primeira versão vamos ajustar só CST
            lote.append({
                "registro_id": int(registro_id),
                "cfop": None,
                "cst_pis": "51",
                "cst_cofins": "51",
            })

    if not lote:
        return {
            "status": "vazio",
            "msg": "Sem candidatos corrigíveis após filtros.",
            "candidatos": 0,
            "ignorados_sem_registro": ignorados_sem_registro,
            "ignorados_nao_operacional": ignorados_nao_autocorrigiveis,
            "ignorados_sem_oportunidade": ignorados_sem_oportunidade,
            "total_alterado": 0,
            "total_erros": 0,
            "modo_usado": "TRANSP_MATCH",
        }

    res = revisar_c170_lote(
        db,
        versao_origem_id=versao_origem_id,
        alteracoes=lote,
        motivo_codigo="TRANSP_INSUMO_V1",
        apontamento_id=apontamento_id,
    )

    return {
        "status": "ok" if int(res.get("total_alterado") or 0) > 0 else "vazio",
        "candidatos": len(lote),
        "ignorados_sem_registro": ignorados_sem_registro,
        "ignorados_nao_operacional": ignorados_nao_autocorrigiveis,
        "ignorados_sem_oportunidade": ignorados_sem_oportunidade,
        "total_alterado": int(res.get("total_alterado") or 0),
        "total_ignorado_pf": int(res.get("total_ignorado_pf") or 0),
        "total_erros": int(res.get("total_erros") or 0),
        "erros_detalhe": res.get("erros_detalhe") or [],
        "registro_ids_alterados": [int(x["registro_id"]) for x in lote],
        "modo_usado": "TRANSP_MATCH",
    }