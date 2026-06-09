from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.sped.maps.reg0150_map import REG_0150, IDX_0150
from app.utils.list_utils import get_safe
from app.utils.sped import ler_linhas_sped


def extrair_0150_de_partes(
    partes: list[str],
    *,
    arquivo: str | None = None,
) -> dict[str, Any]:
    campos = partes[1:]

    registro = {
        nome_campo: get_safe(campos, idx)
        for nome_campo, idx in IDX_0150.items()
    }

    registro["reg"] = REG_0150
    registro["arquivo"] = arquivo

    return registro


def carregar_0150_local(
    arquivos: list[Path],
) -> list[dict[str, Any]]:
    registros: list[dict[str, Any]] = []

    for arquivo in arquivos:
        for partes in ler_linhas_sped(arquivo):
            reg = get_safe(partes, 0)

            if reg != REG_0150:
                continue

            registros.append(
                extrair_0150_de_partes(
                    partes,
                    arquivo=arquivo.name,
                )
            )

    return registros