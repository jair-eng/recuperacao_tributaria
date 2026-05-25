
from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text


def buscar_enquadramento_por_cenario(
    db: Session,
    codigo_cenario: str,
) -> Optional[Dict[str, Any]]:

    codigo_cenario = (codigo_cenario or "").strip()

    if not codigo_cenario:
        return None

    sql = text("""
        SELECT
            codigo_cenario,
            tipo_credito_codigo,
            base_credito_codigo,
            cst_pis_destino,
            cst_cofins_destino,
            aliq_pis,
            aliq_cofins
        FROM fiscal_enquadramento_cenario
        WHERE codigo_cenario = :codigo_cenario
          AND ativo = 1
        LIMIT 1
    """)

    row = db.execute(
        sql,
        {
            "codigo_cenario": codigo_cenario,
        }
    ).mappings().first()

    if not row:
        return None

    out = {
        "codigo_cenario": row["codigo_cenario"],
        "tipo_credito_codigo": row["tipo_credito_codigo"],
        "base_credito_codigo": row["base_credito_codigo"],
        "cst_pis_destino": row["cst_pis_destino"],
        "cst_cofins_destino": row["cst_cofins_destino"],
        "aliq_pis": float(row["aliq_pis"] or 0),
        "aliq_cofins": float(row["aliq_cofins"] or 0),
    }


    return out