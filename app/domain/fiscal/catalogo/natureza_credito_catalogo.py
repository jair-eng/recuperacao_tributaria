from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def carregar_mapa_nat_bc_cred(db: Session) -> dict[str, str]:
    rows = db.execute(
        text("""
            SELECT codigo, descricao
            FROM fiscal_base_calculo_credito_sped
            WHERE ativo = 1
        """)
    ).mappings().all()

    return {
        str(row["codigo"]).strip().zfill(2): str(row["descricao"] or "").strip()
        for row in rows
    }