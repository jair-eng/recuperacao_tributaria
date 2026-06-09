from __future__ import annotations

from typing import Any
from app.utils.strings import only_digits, norm_str

REG_0150 = "0150"

IDX_0150 = {
    "cod_part": 0,
    "nome": 1,
    "cod_pais": 2,
    "cnpj": 3,
    "cpf": 4,
    "ie": 5,
    "cod_mun": 6,
    "suframa": 7,
    "endereco": 8,
    "numero": 9,
    "complemento": 10,
    "bairro": 11,
}

def tipo_pessoa_0150(reg: dict[str, Any]) -> str | None:
    cnpj = only_digits(reg.get("cnpj"))
    cpf = only_digits(reg.get("cpf"))

    if cnpj:
        return "PJ"

    if cpf:
        return "PF"

    return None


def montar_mapa_participantes_0150(
    registros_0150: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    mapa: dict[str, dict[str, Any]] = {}

    for reg in registros_0150:
        cod_part = norm_str(reg.get("cod_part"))

        if not cod_part:
            continue

        item = {
            **reg,
            "cod_part": cod_part,
            "cnpj": only_digits(reg.get("cnpj")),
            "cpf": only_digits(reg.get("cpf")),
        }

        item["tipo_pessoa"] = tipo_pessoa_0150(item)

        mapa[cod_part] = item

    return mapa