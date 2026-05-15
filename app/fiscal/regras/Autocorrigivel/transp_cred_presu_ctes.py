from __future__ import annotations

from typing import Dict, Any, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from app.fiscal.constants import DOM_TRANSP
from app.db.models import EfdApontamento, EfdRevisao
from app.services.dominio_service import resolver_dominio_por_versao

 ##########REGRA NAO ESTA SENDO APLICADA - PRECISA DE EMPRESA NO LUCRO REAL PARA SEGUIR ANALISE

def aplicar_correcao_transp_credito_presumido(
    db: Session,
    *,
    versao_origem_id: int,
    apontamento_id: Optional[int] = None,
) -> Dict[str, Any]:
    versao_origem_id = int(versao_origem_id)

    dom = (resolver_dominio_por_versao(db, versao_origem_id) or "").strip().upper()
    if dom != DOM_TRANSP:
        return {
            "status": "skip",
            "msg": f"dominio={dom} não permite TRANSP_CRED_PRES",
            "candidatos": 0,
            "total_revisoes": 0,
            "total_erros": 0,
            "modo_usado": "TRANSP_CRED_PRES",
        }

    q = (
        db.query(EfdApontamento)
        .filter(EfdApontamento.versao_id == versao_origem_id)
        .filter(EfdApontamento.codigo.in_(["TRANSP_CRED_PRES_V1", "TRANSP_CRED_PRES_AGR_V1"]))
        .filter(EfdApontamento.resolvido.is_(False))
    )

    if apontamento_id:
        q = q.filter(EfdApontamento.id == int(apontamento_id))

    aps = q.all()
    if not aps:
        return {
            "status": "vazio",
            "msg": "Sem apontamentos TRANSP_CRED_PRES pendentes.",
            "candidatos": 0,
            "total_revisoes": 0,
            "total_erros": 0,
            "modo_usado": "TRANSP_CRED_PRES",
        }

    total_revisoes = 0
    total_erros = 0
    ignorados_nao_autocorrigiveis = 0

    for ap in aps:
        meta = dict(ap.meta_json or {})

        if not meta.get("permite_autocorrecao"):
            ignorados_nao_autocorrigiveis += 1
            continue

        try:
            base = Decimal(str(meta.get("base_total") or "0"))
        except Exception:
            total_erros += 1
            continue

        if base <= 0:
            continue

        registro_id = int(meta.get("registro_id_ancora") or 0)
        if registro_id <= 0:
            total_erros += 1
            continue

        revisao = EfdRevisao(
            versao_origem_id=versao_origem_id,
            versao_revisada_id=None,  # ou a versão revisada real, conforme teu fluxo
            registro_id=registro_id,
            reg="M",
            acao="AJUSTE_M",
            motivo_codigo="TRANSP_CRED_PRES_V1",
            apontamento_id=int(ap.id),
            revisao_json={
                "meta": {
                    "tipo": "TRANSP_PF",
                    "base_transporte": str(base),
                    "origem_regra": "TRANSP_CRED_PRES_V1",
                    "apontamento_id": int(ap.id),
                    "qtd_docs": int(meta.get("qtd_docs") or 0),
                    "cfop": str(meta.get("cfop") or "").strip(),
                    "chv_cte": str(meta.get("chv_cte") or "").strip(),
                    "reg_ancora": str(meta.get("reg_ancora") or "").strip(),
                    "linha_ancora": int(meta.get("linha_ancora") or 0),
                }
            },
        )

        db.add(revisao)
        total_revisoes += 1

    return {
        "status": "ok" if total_revisoes > 0 else "vazio",
        "candidatos": len(aps),
        "ignorados_nao_autocorrigiveis": ignorados_nao_autocorrigiveis,
        "total_revisoes": total_revisoes,
        "total_erros": total_erros,
        "modo_usado": "TRANSP_CRED_PRES",
    }