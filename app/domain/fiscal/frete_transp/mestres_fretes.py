from __future__ import annotations

import re
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db.models import EfdRegistro


# ============================================================
# HELPERS
# ============================================================

def somente_digitos(valor: Any) -> str:
    """
    Remove qualquer caractere que não seja número.

    Exemplos:
        13.248.429/0001-44 -> 13248429000144
        003.611.657-22     -> 00361165722
    """

    return re.sub(
        r"\D",
        "",
        str(valor or ""),
    )


def _dados_registro(
    registro: EfdRegistro,
) -> list:
    """
    Retorna os campos de conteudo_json['dados'] sem o código REG.

    A função aceita os dois formatos:

        ["0140", "10", "EMPRESA", ...]
    ou
        ["10", "EMPRESA", ...]

    Isso evita dependermos de como o parser armazenou o registro.
    """

    conteudo = getattr(
        registro,
        "conteudo_json",
        None,
    ) or {}

    if not isinstance(conteudo, dict):
        return []

    dados = list(
        conteudo.get("dados")
        or []
    )

    reg = str(
        getattr(registro, "reg", "")
        or ""
    ).strip()

    if (
        dados
        and str(dados[0] or "").strip() == reg
    ):
        dados = dados[1:]

    return dados


def _campo(
    dados: list,
    indice: int,
) -> Optional[str]:

    if indice >= len(dados):
        return None

    valor = dados[indice]

    if valor is None:
        return None

    valor = str(valor).strip()

    return valor or None


# ============================================================
# 0140
# ============================================================

def localizar_0140_por_cnpj(
    db: Session,
    *,
    versao_id: int,
    cnpj: str,
) -> Optional[Dict[str, Any]]:
    """
    Localiza o registro 0140 correspondente exatamente ao
    CNPJ informado.

    Além do próprio 0140, determina o intervalo estrutural
    daquele estabelecimento:

        linha_inicio = linha do 0140 encontrado
        linha_fim    = próximo 0140 ou 0990

    Layout 0140:

        01 REG
        02 COD_EST
        03 NOME
        04 CNPJ
        05 UF
        06 IE
        07 COD_MUN
        08 IM
        09 SUFRAMA

    Como _dados_registro remove REG:

        0 COD_EST
        1 NOME
        2 CNPJ
        3 UF
        4 IE
        5 COD_MUN
        6 IM
        7 SUFRAMA
    """

    cnpj_busca = somente_digitos(cnpj)

    if not cnpj_busca:
        return None

    registros_0140 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id
            == int(versao_id),

            EfdRegistro.reg == "0140",
        )
        .order_by(
            EfdRegistro.linha.asc()
        )
        .all()
    )

    registro_encontrado = None
    dados_encontrados = None

    for registro in registros_0140:

        dados = _dados_registro(
            registro
        )

        cnpj_0140 = somente_digitos(
            _campo(dados, 2)
        )

        if cnpj_0140 == cnpj_busca:
            registro_encontrado = registro
            dados_encontrados = dados
            break

    if not registro_encontrado:
        return None

    linha_inicio = int(
        getattr(
            registro_encontrado,
            "linha",
            0,
        )
        or 0
    )

    # --------------------------------------------------------
    # Procura próximo 0140
    # --------------------------------------------------------

    proximo_0140 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id
            == int(versao_id),

            EfdRegistro.reg == "0140",

            EfdRegistro.linha
            > linha_inicio,
        )
        .order_by(
            EfdRegistro.linha.asc()
        )
        .first()
    )

    if proximo_0140:

        linha_fim = int(
            getattr(
                proximo_0140,
                "linha",
                0,
            )
            or 0
        )

    else:

        # ----------------------------------------------------
        # Se não existe outro 0140, termina no 0990
        # ----------------------------------------------------

        registro_0990 = (
            db.query(EfdRegistro)
            .filter(
                EfdRegistro.versao_id
                == int(versao_id),

                EfdRegistro.reg == "0990",

                EfdRegistro.linha
                > linha_inicio,
            )
            .order_by(
                EfdRegistro.linha.asc()
            )
            .first()
        )

        linha_fim = (
            int(
                getattr(
                    registro_0990,
                    "linha",
                    0,
                )
                or 0
            )
            if registro_0990
            else 0
        )

    dados = dados_encontrados or []

    return {
        "existe": True,

        "registro_id": getattr(
            registro_encontrado,
            "id",
            None,
        ),

        "linha_inicio": linha_inicio,
        "linha_fim": linha_fim,

        "cod_est": _campo(
            dados,
            0,
        ),

        "nome": _campo(
            dados,
            1,
        ),

        "cnpj": somente_digitos(
            _campo(dados, 2)
        ),

        "uf": _campo(
            dados,
            3,
        ),

        "ie": _campo(
            dados,
            4,
        ),

        "cod_mun": _campo(
            dados,
            5,
        ),

        "registro": registro_encontrado,
    }


# ============================================================
# 0150
# ============================================================

def localizar_0150_contratado(
    db: Session,
    *,
    versao_id: int,
    contexto_0140: Dict[str, Any],
    documento: str,
) -> Optional[Dict[str, Any]]:
    """
    Procura CPF ou CNPJ do contratado SOMENTE dentro do
    intervalo pertencente ao 0140 informado.

    Layout 0150:

        01 REG
        02 COD_PART
        03 NOME
        04 COD_PAIS
        05 CNPJ
        06 CPF
        07 IE
        08 COD_MUN
        09 SUFRAMA
        10 END
        11 NUM
        12 COMPL
        13 BAIRRO

    Depois de remover REG:

        0  COD_PART
        1  NOME
        2  COD_PAIS
        3  CNPJ
        4  CPF
        5  IE
        6  COD_MUN
        7  SUFRAMA
        8  END
        9  NUM
        10 COMPL
        11 BAIRRO
    """

    documento_busca = somente_digitos(
        documento
    )

    if not documento_busca:
        return None

    linha_inicio = int(
        contexto_0140.get(
            "linha_inicio"
        )
        or 0
    )

    linha_fim = int(
        contexto_0140.get(
            "linha_fim"
        )
        or 0
    )

    query = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id
            == int(versao_id),

            EfdRegistro.reg == "0150",

            EfdRegistro.linha
            > linha_inicio,
        )
    )

    if linha_fim:
        query = query.filter(
            EfdRegistro.linha
            < linha_fim
        )

    registros_0150 = (
        query
        .order_by(
            EfdRegistro.linha.asc()
        )
        .all()
    )

    for registro in registros_0150:

        dados = _dados_registro(
            registro
        )

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

        tipo_pessoa = (
            "PJ"
            if cnpj_0150
            else "PF"
        )

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

            "cnpj": cnpj_0150 or None,
            "cpf": cpf_0150 or None,

            "documento": documento_0150,

            "tipo_pessoa": tipo_pessoa,

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


def localizar_f010_por_cnpj(
    db: Session,
    *,
    versao_id: int,
    cnpj: str,
) -> Optional[Dict[str, Any]]:
    """
    Localiza o registro F010 correspondente ao CNPJ informado
    e determina o intervalo estrutural daquele estabelecimento
    dentro do Bloco F.

    O contexto retornado é utilizado para procurar registros F100
    somente no estabelecimento correto.

    Intervalo:

        linha_inicio = linha do F010 encontrado
        linha_fim    = próximo F010 ou F990
    """

    cnpj_busca = somente_digitos(
        cnpj
    )

    if not cnpj_busca:
        return None

    registros_f010 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_id),
            EfdRegistro.reg == "F010",
        )
        .order_by(
            EfdRegistro.linha.asc()
        )
        .all()
    )

    registro_encontrado = None
    dados_encontrados = None

    for registro in registros_f010:

        dados = _dados_registro(
            registro
        )

        # F010:
        # após remover REG:
        # 0 = CNPJ

        cnpj_f010 = somente_digitos(
            _campo(dados, 0)
        )

        if cnpj_f010 == cnpj_busca:
            registro_encontrado = registro
            dados_encontrados = dados
            break

    if not registro_encontrado:
        return None

    linha_inicio = int(
        getattr(
            registro_encontrado,
            "linha",
            0,
        )
        or 0
    )

    proximo_f010 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_id),
            EfdRegistro.reg == "F010",
            EfdRegistro.linha > linha_inicio,
        )
        .order_by(
            EfdRegistro.linha.asc()
        )
        .first()
    )

    if proximo_f010:

        linha_fim = int(
            getattr(
                proximo_f010,
                "linha",
                0,
            )
            or 0
        )

    else:

        registro_f990 = (
            db.query(EfdRegistro)
            .filter(
                EfdRegistro.versao_id == int(versao_id),
                EfdRegistro.reg == "F990",
                EfdRegistro.linha > linha_inicio,
            )
            .order_by(
                EfdRegistro.linha.asc()
            )
            .first()
        )

        linha_fim = (
            int(
                getattr(
                    registro_f990,
                    "linha",
                    0,
                )
                or 0
            )
            if registro_f990
            else 0
        )

    return {
        "existe": True,
        "registro_id": getattr(
            registro_encontrado,
            "id",
            None,
        ),
        "linha_inicio": linha_inicio,
        "linha_fim": linha_fim,
        "cnpj": somente_digitos(
            _campo(
                dados_encontrados or [],
                0,
            )
        ),
        "registro": registro_encontrado,
    }

