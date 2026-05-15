from __future__ import annotations

import json
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.db.models.efd_registro import EfdRegistro
from app.db.models.efd_revisao import EfdRevisao
import logging

from app.services.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert

logger = logging.getLogger(__name__)


def _somente_digitos(txt: str | None) -> str:
    return "".join(ch for ch in str(txt or "") if ch.isdigit())


def _fmt_campo(txt: Any) -> str:
    return str(txt or "").strip()


def montar_linha_0150_de_nf(nf) -> str:
    campos = [
        "0150",
        _fmt_campo(getattr(nf, "cod_part", None)),
        _fmt_campo(getattr(nf, "participante_nome", None)),
        _fmt_campo(getattr(nf, "participante_cod_pais", None) or "1058"),
        _somente_digitos(getattr(nf, "participante_cnpj", None)),
        "",  # CPF -> não usamos no fluxo
        _fmt_campo(getattr(nf, "participante_ie", None)),
        _fmt_campo(getattr(nf, "participante_cod_mun", None)),
        _fmt_campo(getattr(nf, "participante_suframa", None)),
        _fmt_campo(getattr(nf, "participante_end", None)),
        _fmt_campo(getattr(nf, "participante_num", None)),
        _fmt_campo(getattr(nf, "participante_compl", None)),
        _fmt_campo(getattr(nf, "participante_bairro", None)),
    ]
    return "|" + "|".join(campos) + "|"


def _extrair_dados_0150(reg: EfdRegistro) -> list[str]:
    """
    efd_registro.conteudo_json esperado:
    {"dados": ["COD_PART", "NOME", "1058", "CNPJ", "", "IE", ...]}
    """
    conteudo = getattr(reg, "conteudo_json", None)
    if not conteudo:
        return []

    if isinstance(conteudo, dict):
        return list(conteudo.get("dados") or [])

    if isinstance(conteudo, str):
        try:
            obj = json.loads(conteudo)
            return list(obj.get("dados") or [])
        except Exception:
            return []

    return []

def _extrair_dados_0150_de_linha_logica(linha: Any) -> list[str]:
    dados = list(getattr(linha, "dados", []) or [])
    if dados and str(dados[0]).strip().upper() == "0150":
        return dados[1:]
    return dados


def _buscar_0150_existente_por_cod_part(
    db: Session,
    *,
    versao_id: int,
    cod_part: str,
) -> Optional[EfdRegistro]:
    if not cod_part:
        return None

    regs = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == versao_id,
            EfdRegistro.reg == "0150",
        )
        .order_by(EfdRegistro.linha.asc())
        .all()
    )

    cod_part = _fmt_campo(cod_part)
    for reg in regs:
        dados = _extrair_dados_0150(reg)
        if dados and _fmt_campo(dados[0] if len(dados) > 0 else "") == cod_part:
            return reg

    return None

def _buscar_0150_logico_por_cod_part(
    db: Session,
    *,
    versao_id: int,
    cod_part: str,
) -> Optional[dict]:
    cod_part = _fmt_campo(cod_part)
    if not cod_part:
        return None

    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db,
        versao_origem_id=int(versao_id),
    )

    for linha in linhas:
        reg = str(getattr(linha, "reg", "") or "").upper()
        if reg != "0150":
            continue

        dados = _extrair_dados_0150_de_linha_logica(linha)
        cod_part_ln = _fmt_campo(dados[0] if len(dados) > 0 else "")
        if cod_part_ln != cod_part:
            continue

        cnpj_ln = _somente_digitos(dados[3] if len(dados) > 3 else "")
        cpf_ln = _somente_digitos(dados[4] if len(dados) > 4 else "")

        return {
            "linha": linha,
            "dados": dados,
            "cod_part": cod_part_ln,
            "cnpj": cnpj_ln,
            "cpf": cpf_ln,
        }

    return None




def _buscar_0150_existente_por_cnpj(
    db: Session,
    *,
    versao_id: int,
    cnpj: str,
) -> Optional[EfdRegistro]:
    cnpj = _somente_digitos(cnpj)
    if not cnpj:
        return None

    regs = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == versao_id,
            EfdRegistro.reg == "0150",
        )
        .order_by(EfdRegistro.linha.asc())
        .all()
    )

    for reg in regs:
        dados = _extrair_dados_0150(reg)
        cnpj_reg = _somente_digitos(dados[3] if len(dados) > 3 else "")
        if cnpj_reg == cnpj:
            return reg

    return None

def _buscar_0150_logico_por_cnpj(
    db: Session,
    *,
    versao_id: int,
    cnpj: str,
) -> Optional[dict]:
    cnpj = _somente_digitos(cnpj)
    if not cnpj:
        return None

    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db,
        versao_origem_id=int(versao_id),
    )

    for linha in linhas:
        reg = str(getattr(linha, "reg", "") or "").upper()
        if reg != "0150":
            continue

        dados = _extrair_dados_0150_de_linha_logica(linha)
        cnpj_ln = _somente_digitos(dados[3] if len(dados) > 3 else "")
        if cnpj_ln != cnpj:
            continue

        cod_part_ln = _fmt_campo(dados[0] if len(dados) > 0 else "")
        cpf_ln = _somente_digitos(dados[4] if len(dados) > 4 else "")

        return {
            "linha": linha,
            "dados": dados,
            "cod_part": cod_part_ln,
            "cnpj": cnpj_ln,
            "cpf": cpf_ln,
        }

    return None




def _achar_linha_insercao_0150(
    db: Session,
    *,
    versao_id: int,
) -> int:
    """
    Regra:
    - se já houver 0150, insere após o último 0150
    - senão, insere após o último 0140
    - fallback final: após o último 0120/0110/0100/0001/0000
    """
    # 1) último 0150
    reg = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == versao_id,
            EfdRegistro.reg == "0150",
        )
        .order_by(EfdRegistro.linha.desc())
        .first()
    )
    if reg:
        return int(reg.linha or 0)

    # 2) último 0140
    reg = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == versao_id,
            EfdRegistro.reg == "0140",
        )
        .order_by(EfdRegistro.linha.desc())
        .first()
    )
    if reg:
        return int(reg.linha or 0)

    # 3) fallback em registros anteriores do bloco 0
    for reg_code in ["0120", "0110", "0100", "0001", "0000"]:
        reg = (
            db.query(EfdRegistro)
            .filter(
                EfdRegistro.versao_id == versao_id,
                EfdRegistro.reg == reg_code,
            )
            .order_by(EfdRegistro.linha.desc())
            .first()
        )
        if reg:
            return int(reg.linha or 0)

    return 0

def _validar_0150_logico_para_nf(
    db: Session,
    *,
    versao_id: int,
    cod_part: str,
    cnpj_esperado: str,
) -> bool:
    found = _buscar_0150_logico_por_cod_part(
        db,
        versao_id=int(versao_id),
        cod_part=cod_part,
    )
    if not found:
        return False

    cnpj_found = _somente_digitos(found.get("cnpj"))
    return bool(cnpj_found and cnpj_found == _somente_digitos(cnpj_esperado))



def criar_revisao_insert_0150(
    db: Session,
    *,
    versao_origem_id: int,
    linha_ref: int,
    nf,
) -> EfdRevisao:
    linha_nova = montar_linha_0150_de_nf(nf)

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=None,
        reg="0150",
        acao="INSERT_AFTER",
        revisao_json={
            "linha_nova": linha_nova,
            "linha_referencia": int(linha_ref or 0),
            "origem": "ICMS_IPI",
            "motivo": "Participante da nota não existe no 0150 da versão",
            "chave_nfe": getattr(nf, "chave_nfe", None),
            "cod_part": getattr(nf, "cod_part", None),
            "participante_cnpj": getattr(nf, "participante_cnpj", None),
        },
        motivo_codigo="CONTRIB_PART_0150_V1",
        apontamento_id=None,
    )
    db.add(rv)
    db.flush()
    return rv


def resolver_ou_criar_0150_por_cnpj(
    db: Session,
    *,
    versao_id: int,
    nf,
) -> str:
    cod_part_nf = _fmt_campo(getattr(nf, "cod_part", None))
    cnpj_nf = _somente_digitos(getattr(nf, "participante_cnpj", None))

    if not cnpj_nf:
        raise ValueError(
            f"NF {getattr(nf, 'chave_nfe', None)} sem participante_cnpj para resolver/criar 0150"
        )

    # 1) tenta por COD_PART no estado lógico
    if cod_part_nf:
        found = _buscar_0150_logico_por_cod_part(
            db,
            versao_id=versao_id,
            cod_part=cod_part_nf,
        )
        if found and _somente_digitos(found.get("cnpj")) == cnpj_nf:
            logger.debug(
                "0150 lógico match por COD_PART | versao_id=%s cod_part=%s cnpj=%s",
                versao_id,
                cod_part_nf,
                cnpj_nf,
            )
            return cod_part_nf

    # 2) tenta por CNPJ no estado lógico
    found = _buscar_0150_logico_por_cnpj(
        db,
        versao_id=versao_id,
        cnpj=cnpj_nf,
    )
    if found:
        cod_part_match = _fmt_campo(found.get("cod_part"))
        if cod_part_match:
            logger.debug(
                "0150 lógico match por CNPJ | versao_id=%s cnpj=%s cod_part=%s",
                versao_id,
                cnpj_nf,
                cod_part_match,
            )
            return cod_part_match

    # 3) fallback legado: base persistida
    if cod_part_nf:
        reg = _buscar_0150_existente_por_cod_part(
            db,
            versao_id=versao_id,
            cod_part=cod_part_nf,
        )
        if reg:
            logger.debug(
                "0150 base match por COD_PART | versao_id=%s cod_part=%s linha=%s",
                versao_id,
                cod_part_nf,
                getattr(reg, "linha", None),
            )
            return cod_part_nf

    reg = _buscar_0150_existente_por_cnpj(
        db,
        versao_id=versao_id,
        cnpj=cnpj_nf,
    )
    if reg:
        dados = _extrair_dados_0150(reg)
        cod_part_match = _fmt_campo(dados[0] if len(dados) > 0 else "")
        if cod_part_match:
            logger.debug(
                "0150 base match por CNPJ | versao_id=%s cnpj=%s cod_part=%s linha=%s",
                versao_id,
                cnpj_nf,
                cod_part_match,
                getattr(reg, "linha", None),
            )
            return cod_part_match

    # 4) cria novo 0150
    if not cod_part_nf:
        cod_part_nf = f"F{cnpj_nf}"

    linha_ref = _achar_linha_insercao_0150(
        db,
        versao_id=versao_id,
    )

    rv = criar_revisao_insert_0150(
        db,
        versao_origem_id=versao_id,
        linha_ref=linha_ref,
        nf=nf,
    )


    logger.debug(
        "0150 revisão criada | versao_id=%s rv_id=%s linha_ref=%s cod_part=%s cnpj=%s chave_nfe=%s",
        versao_id,
        getattr(rv, "id", None),
        linha_ref,
        cod_part_nf,
        cnpj_nf,
        getattr(nf, "chave_nfe", None),
    )

    # 5) sanity check: só retorna se o 0150 estiver visível no estado lógico
    if not _validar_0150_logico_para_nf(
        db,
        versao_id=versao_id,
        cod_part=cod_part_nf,
        cnpj_esperado=cnpj_nf,
    ):
        raise ValueError(
            f"0150 não ficou visível no estado lógico após criação | "
            f"versao_id={versao_id} cod_part={cod_part_nf} cnpj={cnpj_nf} "
            f"nf_id={getattr(nf, 'id', None)} chave_nfe={getattr(nf, 'chave_nfe', None)}"
        )

    return cod_part_nf

