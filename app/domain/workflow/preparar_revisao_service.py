from sqlalchemy.orm import Session

from app.db.models import ItemFiscalConsolidado, EfdApontamento, EfdRevisao
from app.domain.sped.services.contexto_fiscal.materializar_contexto_fiscal import materializar_contexto_fiscal
from app.domain.workflow.gerar_apontamentos_service import gerar_apontamentos_por_contexto
import logging

logger = logging.getLogger(__name__)

def limpar_apontamentos_versao_seguro(
    db: Session,
    *,
    versao_id: int,
    batch_size: int = 100,
) -> int:
    total = 0

    logger.info("## [LIMPAR_AP v%s] inicio ##", versao_id)

    # Desvincula revisões para não pesar FK e não travar delete
    db.query(EfdRevisao).filter(
        EfdRevisao.versao_origem_id == int(versao_id)
    ).update(
        {EfdRevisao.apontamento_id: None},
        synchronize_session=False,
    )
    db.flush()

    while True:
        ids = [
            row[0]
            for row in (
                db.query(EfdApontamento.id)
                .filter(EfdApontamento.versao_id == int(versao_id))
                .order_by(EfdApontamento.id.asc())
                .limit(batch_size)
                .all()
            )
        ]

        if not ids:
            break

        apagados = (
            db.query(EfdApontamento)
            .filter(EfdApontamento.id.in_(ids))
            .delete(synchronize_session=False)
        )

        total += int(apagados or 0)
        db.flush()

        logger.info(
            "## [LIMPAR_AP v%s] apagados parcial=%s ##",
            versao_id,
            total,
        )

    logger.info("## [LIMPAR_AP v%s] fim total=%s ##", versao_id, total)

    return total

def preparar_revisao(
    *,
    db: Session,
    versao_id: int,
) -> dict:
    import time
    t0 = time.perf_counter()

    logger.info("## [PREPARAR_REVISAO v%s] inicio ##", versao_id)

    qtd_apontamentos_apagados = limpar_apontamentos_versao_seguro(
        db,
        versao_id=int(versao_id),
        batch_size=100,
    )

    logger.info(
        "## [PREPARAR_REVISAO v%s] apontamentos limpos=%s tempo=%.3fs ##",
        versao_id,
        qtd_apontamentos_apagados,
        time.perf_counter() - t0,
    )

    materializar_contexto_fiscal(db, versao_id)

    logger.info(
        "## [PREPARAR_REVISAO v%s] contexto materializado tempo=%.3fs ##",
        versao_id,
        time.perf_counter() - t0,
    )

    gerar_apontamentos_por_contexto(
        db=db,
        versao_id=versao_id,
    )

    logger.info(
        "## [PREPARAR_REVISAO v%s] apontamentos gerados tempo=%.3fs ##",
        versao_id,
        time.perf_counter() - t0,
    )

    total = (
        db.query(ItemFiscalConsolidado.id)
        .filter(ItemFiscalConsolidado.versao_id == versao_id)
        .count()
    )

    logger.info(
        "## [PREPARAR_REVISAO v%s] fim itens_materializados=%s tempo=%.3fs ##",
        versao_id,
        total,
        time.perf_counter() - t0,
    )

    return {
        "ok": True,
        "versao_id": int(versao_id),
        "apontamentos_apagados": int(qtd_apontamentos_apagados),
        "itens_materializados": int(total),
    }