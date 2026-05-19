from dataclasses import dataclass
from typing import Any

from app.domain.sped.contabil.loaders.loader_0500 import Contabil0500Context, carregar_0500


@dataclass(frozen=True)
class ContextoCompetencia:
    registros: list[Any]
    contabil_0500: Contabil0500Context


def montar_contexto_competencia(
    *,
    registros: list[Any],
) -> ContextoCompetencia:
    contabil_0500 = carregar_0500(registros)

    return ContextoCompetencia(
        registros=registros,
        contabil_0500=contabil_0500,
    )