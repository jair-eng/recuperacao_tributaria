from __future__ import annotations

from typing import Any
from app.utils.strings import norm_str


def participante_d100(
    d100: dict[str, Any],
    mapa_participantes: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    cod_part = norm_str(d100.get("cod_part"))

    if not cod_part:
        return None

    return mapa_participantes.get(cod_part)


def enriquecer_registro_d100_com_participante(
    d100: dict[str, Any],
    mapa_participantes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    participante = participante_d100(d100, mapa_participantes)

    return {
        **d100,
        "participante": participante,
        "participante_nome": participante.get("nome") if participante else None,
        "participante_cnpj": participante.get("cnpj") if participante else None,
        "participante_cpf": participante.get("cpf") if participante else None,
        "participante_tipo": participante.get("tipo_pessoa") if participante else None,
    }


def enriquecer_contexto_d100_com_participantes(
    ctx_d100: dict[str, Any],
    mapa_participantes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    def enriquecer_item(item: dict[str, Any]) -> dict[str, Any]:
        novo = dict(item)

        if "icms" in novo and isinstance(novo["icms"], dict):
            novo["icms"] = enriquecer_registro_d100_com_participante(
                novo["icms"],
                mapa_participantes,
            )

        if "contrib" in novo and isinstance(novo["contrib"], dict):
            novo["contrib"] = enriquecer_registro_d100_com_participante(
                novo["contrib"],
                mapa_participantes,
            )

        return novo

    return {
        **ctx_d100,
        "matches": [enriquecer_item(item) for item in ctx_d100.get("matches", [])],
        "sem_contrib": [enriquecer_item(item) for item in ctx_d100.get("sem_contrib", [])],
        "sem_icms": [enriquecer_item(item) for item in ctx_d100.get("sem_icms", [])],
    }