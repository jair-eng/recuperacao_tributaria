from typing import Optional

from sqlalchemy.orm import Session
from app.db.models import EfdRegistro


def resolver_ancora_bloco_f_fim(
    db: Session,
    *,
    versao_origem_id: int,
) -> tuple[Optional[int], int, str]:
    """
    Resolve a âncora para inserção de um novo bloco F010 + F100.

    Regra principal:

        inserir imediatamente antes do F990.

    Exemplo:

        |F001|0|
        |F010|...|
        |F100|...|
        |F990|...|

    Se não existir F990, utiliza o último F010 como fallback.
    """

    # ---------------------------------------------------------
    # 1. Regra principal:
    #    inserir antes do F990
    # ---------------------------------------------------------

    reg_f990 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "F990",
        )
        .order_by(EfdRegistro.linha.asc())
        .first()
    )

    if reg_f990:
        return (
            int(reg_f990.id),
            int(getattr(reg_f990, "linha", 0) or 0),
            "INSERT_BEFORE",
        )

    # ---------------------------------------------------------
    # 2. Fallback:
    #    se não houver F990, tenta inserir após último F010
    # ---------------------------------------------------------

    regs_f010 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "F010",
        )
        .order_by(EfdRegistro.linha.asc())
        .all()
    )

    if regs_f010:
        ultimo = regs_f010[-1]

        return (
            int(ultimo.id),
            int(getattr(ultimo, "linha", 0) or 0),
            "INSERT_AFTER",
        )

    # ---------------------------------------------------------
    # 3. Último fallback
    # ---------------------------------------------------------

    return None, 0, "INSERT_AFTER"