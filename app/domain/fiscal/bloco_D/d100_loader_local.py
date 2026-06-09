from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.sped.maps.d100_map import IDX_D100, REG_D100
from app.utils.list_utils import get_safe
from app.utils.numbers import to_decimal
from app.utils.sped import ler_linhas_sped


CAMPOS_DECIMAIS_D100 = {
    "vl_doc",
    "vl_desc",
    "vl_serv",
    "vl_bc_icms",
    "vl_icms",
    "vl_nt",
}


def extrair_d100_de_partes(
    partes: list[str],
    *,
    arquivo: str | None = None,
) -> dict[str, Any]:
    """
    Extrai um registro D100 usando IDX_D100.

    Observação:
    A linha SPED vem normalmente assim:
    |D100|0|1|...|

    Portanto:
    partes[0] = ''
    partes[1] = 'D100'
    partes[2:] = campos reais do D100
    """

    campos = partes[1:]

    registro = {
        nome_campo: get_safe(campos, idx)
        for nome_campo, idx in IDX_D100.items()
    }

    for campo in CAMPOS_DECIMAIS_D100:
        registro[campo] = to_decimal(registro.get(campo))

    registro["reg"] = REG_D100
    registro["arquivo"] = arquivo

    return registro


def carregar_d100_local(
    arquivos: list[Path],
) -> list[dict[str, Any]]:
    """
    Carrega registros D100 diretamente de arquivos TXT SPED.

    Uso esperado:
    - Relatório Executivo local;
    - contexto fiscal local;
    - diagnóstico exploratório sem depender do banco.
    """

    registros: list[dict[str, Any]] = []

    for arquivo in arquivos:
        for partes in ler_linhas_sped(arquivo):
            reg = get_safe(partes, 0)

            if reg != REG_D100:
                continue

            registros.append(
                extrair_d100_de_partes(
                    partes,
                    arquivo=arquivo.name,
                )
            )

    return registros