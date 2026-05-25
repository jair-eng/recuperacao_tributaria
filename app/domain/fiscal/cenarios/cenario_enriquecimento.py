from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from app.domain.fiscal.enquadramento.enquadramento_repository import (
    buscar_enquadramento_por_cenario,
)


def enriquecer_cenario_com_enquadramento(
    db: Session,
    cenario: Dict[str, Any],
) -> Dict[str, Any]:

    if not cenario:
        return cenario

    if not cenario.get("ativo"):
        return cenario

    fundamentos = cenario.get("fundamento_legal") or []

    if not fundamentos:
        return cenario

    codigo_cenario = str(fundamentos[0]).strip()

    if not codigo_cenario:
        return cenario

    enquadramento = buscar_enquadramento_por_cenario(
        db,
        codigo_cenario,
    )

    if not enquadramento:
        return cenario

    cenario["codigo_cenario"] = codigo_cenario
    cenario["enquadramento"] = enquadramento



    return cenario