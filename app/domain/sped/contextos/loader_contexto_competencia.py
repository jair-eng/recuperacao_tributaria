from sqlalchemy.orm import Session

from app.db.models.efd_registro import EfdRegistro
from app.domain.sped.contextos.contexto_competencia import montar_contexto_competencia


def carregar_contexto_competencia_por_versao(
    db: Session,
    *,
    versao_id: int,
):
    registros = (
        db.query(EfdRegistro)
        .filter(EfdRegistro.versao_id == versao_id)
        .order_by(EfdRegistro.linha.asc())
        .all()
    )

    return montar_contexto_competencia(registros=registros)