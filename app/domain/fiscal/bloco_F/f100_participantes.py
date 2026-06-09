from __future__ import annotations

from typing import Any

from app.utils.strings import norm_str


def participante_f100(
    f100: dict[str, Any],
    mapa_participantes: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    cod_part = norm_str(f100.get("cod_part"))

    if not cod_part:
        return None

    return mapa_participantes.get(cod_part)


def enriquecer_registro_f100_com_participante(
    f100: dict[str, Any],
    mapa_participantes: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    participante = participante_f100(f100, mapa_participantes)

    return {
        **f100,
        "participante": participante,
        "participante_nome": participante.get("nome") if participante else None,
        "participante_cnpj": participante.get("cnpj") if participante else None,
        "participante_cpf": participante.get("cpf") if participante else None,
        "participante_tipo": participante.get("tipo_pessoa") if participante else None,
    }


def enriquecer_f100_com_participantes(
    registros_f100: list[dict[str, Any]],
    mapa_participantes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        enriquecer_registro_f100_com_participante(item, mapa_participantes)
        for item in registros_f100
    ]