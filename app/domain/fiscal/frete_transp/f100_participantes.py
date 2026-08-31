from __future__ import annotations
from app.domain.fiscal.frete_transp.mestres_fretes import somente_digitos, _dados_registro, _campo
import re
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from app.db.models import EfdRegistro

def montar_linha_0150_frete(
    *,
    cod_part: str,
    nome: str,
    documento: str,
    tipo_pessoa: str,
    cod_pais: str = "1058",
    ie: str | None = None,
    cod_mun: str | None = None,
    suframa: str | None = None,
    logradouro: str | None = None,
    numero: str | None = None,
    complemento: str | None = None,
    bairro: str | None = None,
) -> list:

    documento_limpo = somente_digitos(
        documento
    )

    tipo_pessoa = str(
        tipo_pessoa or ""
    ).strip().upper()

    if tipo_pessoa == "PJ":
        cnpj = documento_limpo
        cpf = None

    elif tipo_pessoa == "PF":
        cnpj = None
        cpf = documento_limpo

    else:
        raise ValueError(
            f"Tipo de pessoa inválido para 0150: {tipo_pessoa}"
        )

    dados = [
        "0150",
        str(cod_part).strip(),
        str(nome or "").strip(),
        str(cod_pais or "1058").strip(),
        cnpj,
        cpf,
        str(ie or "").strip() or None,
        str(cod_mun or "").strip() or None,
        str(suframa or "").strip() or None,
        str(logradouro or "").strip() or None,
        str(numero or "").strip() or None,
        str(complemento or "").strip() or None,
        str(bairro or "").strip() or None,
    ]

    return dados


def localizar_0150_por_documento_na_versao(
    db: Session,
    *,
    versao_id: int,
    documento: str,
) -> Optional[Dict[str, Any]]:

    documento_busca = somente_digitos(documento)

    if not documento_busca:
        return None

    registros_0150 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_id),
            EfdRegistro.reg == "0150",
        )
        .order_by(
            EfdRegistro.linha.asc()
        )
        .all()
    )

    for registro in registros_0150:

        dados = _dados_registro(registro)

        cnpj_0150 = somente_digitos(
            _campo(dados, 3)
        )

        cpf_0150 = somente_digitos(
            _campo(dados, 4)
        )

        documento_0150 = (
                cnpj_0150
                or cpf_0150
        )

        if documento_0150 != documento_busca:
            continue

        return {
            "existe": True,

            "registro_id": getattr(
                registro,
                "id",
                None,
            ),

            "linha": int(
                getattr(
                    registro,
                    "linha",
                    0,
                )
                or 0
            ),

            "cod_part": _campo(
                dados,
                0,
            ),

            "nome": _campo(
                dados,
                1,
            ),

            "cod_pais": _campo(
                dados,
                2,
            ),

            "cnpj": (
                    cnpj_0150
                    or None
            ),

            "cpf": (
                    cpf_0150
                    or None
            ),

            "documento": documento_0150,

            "tipo_pessoa": (
                "PJ"
                if cnpj_0150
                else "PF"
            ),

            "ie": _campo(
                dados,
                5,
            ),

            "cod_mun": _campo(
                dados,
                6,
            ),

            "suframa": _campo(
                dados,
                7,
            ),

            "logradouro": _campo(
                dados,
                8,
            ),

            "numero": _campo(
                dados,
                9,
            ),

            "complemento": _campo(
                dados,
                10,
            ),

            "bairro": _campo(
                dados,
                11,
            ),

            "registro": registro,
        }

    return None

def gerar_novo_cod_part_frete(
    db: Session,
    *,
    versao_id: int,
) -> str:

    registros_0150 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_id),
            EfdRegistro.reg == "0150",
        )
        .order_by(
            EfdRegistro.linha.asc()
        )
        .all()
    )

    codigos_existentes = set()

    for registro in registros_0150:

        dados = _dados_registro(
            registro
        )

        cod_part = _campo(
            dados,
            0,
        )

        if cod_part:
            codigos_existentes.add(
                str(cod_part).strip()
            )

    numeros = []

    for codigo in codigos_existentes:

        if codigo.isdigit():
            numeros.append(
                int(codigo)
            )

    if numeros:
        novo_codigo = max(numeros) + 1
    else:
        novo_codigo = 1

    while str(novo_codigo) in codigos_existentes:
        novo_codigo += 1

    return str(novo_codigo)

def resolver_cod_part_frete(
    db: Session,
    *,
    versao_id: int,
    documento: str,
) -> str:

    participante_existente = (
        localizar_0150_por_documento_na_versao(
            db,
            versao_id=versao_id,
            documento=documento,
        )
    )

    if participante_existente:
        return participante_existente["cod_part"]

    return gerar_novo_cod_part_frete(
        db,
        versao_id=versao_id,
    )