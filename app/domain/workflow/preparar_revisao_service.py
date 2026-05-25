from sqlalchemy.orm import Session

from app.db.models import ItemFiscalConsolidado
from app.domain.sped.services.contexto_fiscal.materializar_contexto_fiscal import materializar_contexto_fiscal
from app.domain.workflow.gerar_apontamentos_service import gerar_apontamentos_por_contexto


def preparar_revisao(
    *,
    db: Session,
    versao_id: int,
) -> dict:
    materializar_contexto_fiscal(db, versao_id)

    gerar_apontamentos_por_contexto(
        db=db,
        versao_id=versao_id,
    )

    total = (
        db.query(ItemFiscalConsolidado)
        .filter(ItemFiscalConsolidado.versao_id == versao_id)
        .count()
    )

    print("[SERVICE_PREPARAR_REVISAO_V2] itens_materializados=", total, flush=True)

    return {
        "ok": True,
        "versao_id": versao_id,
        "itens_materializados": total,
    }