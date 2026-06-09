from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.sped.maps.f100_map import IDX_F100, REG_F100
from app.utils.list_utils import get_safe
from app.utils.numbers import to_decimal
from app.utils.sped import ler_linhas_sped


CAMPOS_DECIMAIS_F100 = {
    "vl_oper",
    "vl_bc_pis",
    "aliq_pis",
    "vl_pis",
    "vl_bc_cofins",
    "aliq_cofins",
    "vl_cofins",
}


def extrair_f100_de_partes(
    partes: list[str],
    *,
    arquivo: str | None = None,
) -> dict[str, Any]:
    campos = partes[1:]

    registro = {
        nome_campo: get_safe(campos, idx)
        for nome_campo, idx in IDX_F100.items()
    }

    for campo in CAMPOS_DECIMAIS_F100:
        registro[campo] = to_decimal(registro.get(campo))

    registro["reg"] = REG_F100
    registro["arquivo"] = arquivo

    return registro


def carregar_f100_local(
    arquivos: list[Path],
) -> list[dict[str, Any]]:
    registros: list[dict[str, Any]] = []

    for arquivo in arquivos:
        for partes in ler_linhas_sped(arquivo):
            reg = get_safe(partes, 0)

            if reg != REG_F100:
                continue

            registros.append(
                extrair_f100_de_partes(
                    partes,
                    arquivo=arquivo.name,
                )
            )

    return registros