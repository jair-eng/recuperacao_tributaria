from __future__ import annotations

from typing import Any, Dict, Optional, List
from sqlalchemy.orm import Session

import logging

from app.services.c170_service import revisar_c170_lote

logger = logging.getLogger(__name__)

def aplicar_correcao_lc192_c170_existente(
    db: Session,
    *,
    versao_origem_id: int,
    itens: List[Dict[str, Any]],
    apontamento_id: Optional[int] = None,
) -> Dict[str, Any]:

    lote: List[Dict[str, Any]] = []

    for item in itens:
        registro_id = item.get("registro_id")
        if not registro_id:
            continue

        lote.append({
            "registro_id": int(registro_id),
            "cfop": None,

            # LC192
            "cst_pis": "61",
            "cst_cofins": "61",
            "fator_base_credito": None,
            "aliq_pis": "1,6500",
            "aliq_cofins": "7,6000",
            "contexto": "LC192",
            "natureza_credito_m": "206",
        })

    if not lote:
        return {
            "status": "vazio",
            "msg": "Nenhum item válido para correção LC192.",
        }

    return revisar_c170_lote(
        db,
        versao_origem_id=int(versao_origem_id),
        alteracoes=lote,
        motivo_codigo="COMB_LC192_V1",
        apontamento_id=apontamento_id,
    )