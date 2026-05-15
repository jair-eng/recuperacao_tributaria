from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy.orm import Session
from app.db.models import EfdRevisao, EfdVersao
import logging
log = logging.getLogger(__name__)


MOTIVOS_RESET_AUTO_ICMS_EFD = [
    "CONTRIB_SEM_C100_V1",
    "CONTRIB_SEM_C100_V1_AUTO_SUM",
    "CONTRIB_SEM_C170_V1",
    "CONTRIB_SEM_C170_V1_AUTO_SUM",
    "CONTRIB_PART_0150_V1",
    "CONTRIB_SEM_0190_V1",
    "CONTRIB_SEM_0200_V1",
    "CONTRIB_CONTA_0500_V1",
]


def limpar_revisoes_automaticas_da_versao(
    db: Session,
    *,
    versao_origem_id: int,
) -> Dict[str, Any]:
    """
    Remove revisões automáticas da família ICMS/EFD de uma versão,
    preservando revisões manuais e quaisquer outras revisões fora da lista.

    Uso esperado:
      - usuário quer resetar a versão para reprocessar / resolver novamente
      - evita precisar apagar direto no banco manualmente
    """

    versao = db.query(EfdVersao).filter(EfdVersao.id == int(versao_origem_id)).first()
    if not versao:
        raise ValueError("Versão não encontrada.")

    if str(getattr(versao, "status", "")).upper() == "EXPORTADA":
        raise ValueError("Não é permitido limpar revisões automáticas de uma versão EXPORTADA.")

    revisoes = (
        db.query(EfdRevisao)
        .filter(
            EfdRevisao.versao_origem_id == int(versao_origem_id),
            EfdRevisao.motivo_codigo.in_(MOTIVOS_RESET_AUTO_ICMS_EFD),
        )
        .order_by(EfdRevisao.id.asc())
        .all()
    )

    total_encontrado = len(revisoes)

    por_motivo: Dict[str, int] = {}
    por_acao: Dict[str, int] = {}
    ids_removidos: List[int] = []

    for rv in revisoes:
        motivo = str(getattr(rv, "motivo_codigo", "") or "")
        acao = str(getattr(rv, "acao", "") or "")

        por_motivo[motivo] = por_motivo.get(motivo, 0) + 1
        por_acao[acao] = por_acao.get(acao, 0) + 1
        ids_removidos.append(int(rv.id))

        db.delete(rv)

    db.flush()
    log.info(
        "RESET AUTO REVISOES | versao_origem_id=%s total_removido=%s por_motivo=%s por_acao=%s",
        versao_origem_id,
        total_encontrado,
        por_motivo,
        por_acao,
    )

    return {
        "ok": True,
        "versao_origem_id": int(versao_origem_id),
        "total_removido": total_encontrado,
        "por_motivo": por_motivo,
        "por_acao": por_acao,
        "ids_removidos": ids_removidos,
        "mensagem": (
            "Revisões automáticas da versão removidas com sucesso."
            if total_encontrado > 0
            else "Nenhuma revisão automática da família ICMS/EFD foi encontrada para esta versão."
        ),
    }