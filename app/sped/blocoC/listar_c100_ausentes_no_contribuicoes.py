from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from sqlalchemy.orm import Session
from app.db.models import NfIcmsBase
from app.db.models.nf_icms_item import NfIcmsItem
from app.Legacy.fiscal.constants import DOM_GERAL
from app.Legacy.fiscal.regras.helpers.elegibilidade_dominio import item_cfop_elegivel
from app.Legacy.fiscal.settings_fiscais import CFOPS_ELEGIVEIS, COD_SIT_SKIP_CONS
from app.services.dominio_service import resolver_dominio_por_versao
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes
from app.icms_ipi.icms_helpers import _campo, _only_digits
from app.icms_ipi.icms_ipi_funcoes import _eh_c100
from app.sped.blocoC.c100_utils import montar_linha_c100_de_icms
import logging

logger = logging.getLogger(__name__)


CFOPS_ELEGIVEIS_CREDITO = CFOPS_ELEGIVEIS
COD_SIT_SKIP = COD_SIT_SKIP_CONS


def _buscar_itens_nf_icms(
    db: Session,
    *,
    empresa_id: int,
    nf_id: int,
) -> list[NfIcmsItem]:
    return (
        db.query(NfIcmsItem)
        .filter(
            NfIcmsItem.empresa_id == int(empresa_id),
            NfIcmsItem.nf_icms_base_id == int(nf_id),
        )
        .order_by(NfIcmsItem.id.asc())
        .all()
    )


def _extrair_ind_oper_cod_sit_do_nf(nf: Any) -> tuple[str, str]:
    """
    Usa a mesma montagem do C100 que a correção usa hoje.
    Layout esperado:
    |C100|IND_OPER|IND_EMIT|COD_PART|COD_MOD|COD_SIT|...
    """
    try:
        linha_c100 = montar_linha_c100_de_icms(nf)
        partes = [p for p in str(linha_c100 or "").split("|") if p != ""]
        if not partes or partes[0].strip().upper() != "C100":
            return "", ""

        ind_oper = str(partes[1]).strip() if len(partes) > 1 else ""
        cod_sit = str(partes[5]).strip() if len(partes) > 5 else ""
        return ind_oper, cod_sit
    except Exception:
        return "", ""


def _nf_icms_pf_skip(nf: Any) -> bool:
    """
    Para C100 ausente não dá para usar eh_pf_por_c100().
    Então tentamos decidir PF/PJ pela base ICMS.
    """
    cnpj = _only_digits(
        getattr(nf, "cnpj_participante", None)
        or getattr(nf, "cnpj_cpf_part", None)
        or getattr(nf, "cnpj_cpf", None)
        or getattr(nf, "cnpj_emitente", None)
        or ""
    )
    cpf = _only_digits(
        getattr(nf, "cpf_participante", None)
        or getattr(nf, "cpf", None)
        or ""
    )
    if cnpj:
        return False

    return len(cpf) == 11

def listar_c100_ausentes(
    db: Session,
    *,
    versao_origem_id: int,
    empresa_id: int,
    periodo: str | None = None,
    cfops_elegiveis: Optional[set[str]] = None,
    aplicar_trava_ind_oper_entrada: bool = True,
    aplicar_trava_cod_sit: bool = True,
    aplicar_trava_pf: bool = True,
    filtro_item_extra: Optional[Callable[[NfIcmsItem], bool]] = None,
) -> List[Dict[str, Any]]:
    """
    Lista notas presentes no ICMS/IPI e ausentes no C100 da EFD Contribuições,
    sem criar revisão.

    Travas:
    - chave ainda não existe no C100 da versão
    - IND_OPER = 0 (entrada), extraído do C100 montado
    - COD_SIT não pode ser 06/07, extraído do C100 montado
    - pula PF
    - exige itens
    - exige pelo menos 1 item com CFOP elegível
    - opcionalmente aplica filtro_item_extra (CPC/catálogo)
    """
    dominio = resolver_dominio_por_versao(db, versao_origem_id) or DOM_GERAL

    linhas = carregar_linhas_logicas_com_revisoes(
        db,
        versao_origem_id=int(versao_origem_id),
    )

    chaves_existentes: set[str] = set()

    for linha in linhas:
        if not _eh_c100(linha):
            continue

        dados = list(getattr(linha, "dados", []) or [])
        chave = _only_digits(_campo(dados, 7))
        if chave:
            chaves_existentes.add(chave)

    logger.debug(
        "C100 existentes mapeados | total=%s",
        len(chaves_existentes),
    )

    q_nf_ids = (
        db.query(NfIcmsItem.nf_icms_base_id)
        .filter(NfIcmsItem.empresa_id == int(empresa_id))
        .distinct()
    )

    nf_ids = [int(row[0]) for row in q_nf_ids.all() if row and row[0]]
    if not nf_ids:
        return []

    q_nfs = db.query(NfIcmsBase).filter(NfIcmsBase.id.in_(nf_ids))

    if periodo and hasattr(NfIcmsBase, "periodo"):
        q_nfs = q_nfs.filter(NfIcmsBase.periodo == str(periodo))

    nfs = q_nfs.all()

    resultados: List[Dict[str, Any]] = []

    for nf in nfs:

        cod_mod = str(
            getattr(nf, "cod_mod", None)
            or getattr(nf, "modelo", None)
            or ""
        ).strip()

        # 🔒 FILTRO DEFINITIVO - C100 só aceita NF-e
        if cod_mod != "55":

            continue

        chave = _only_digits(getattr(nf, "chave_nfe", None) or "")
        if not chave:
            continue

        if chave in chaves_existentes:
            continue

        ind_oper, cod_sit = _extrair_ind_oper_cod_sit_do_nf(nf)

        if aplicar_trava_ind_oper_entrada and ind_oper != "0":
            logger.debug("C100 ausentes - Saida | chave=%s ind_oper=%s",
                         chave,
                         ind_oper,
                        )
            continue

        if aplicar_trava_cod_sit and cod_sit in COD_SIT_SKIP:
            logger.debug("C100 ausentes - Codigo situacao | chave=%s cod_sit=%s",
                         chave,
                         cod_sit,
                         )
            continue

        if aplicar_trava_pf and _nf_icms_pf_skip(nf):
            logger.debug("C100 ausentes - Pessoa fisica | chave=%s",
                         chave,
                         )
            continue

        itens_nf = _buscar_itens_nf_icms(
            db,
            empresa_id=int(empresa_id),
            nf_id=int(nf.id),
        )
        if not itens_nf:
            continue

        itens_cfop_ok = [
            it for it in itens_nf
            if item_cfop_elegivel({
                "cfop": str(getattr(it, "cfop", "") or "").strip(),
                "dominio": dominio,
            })
        ]
        if not itens_cfop_ok:
            logger.debug(
                "C100 ausentes - CFOP nao permitido por dominio | chave=%s dominio=%s cfops_nf=%s",
                chave,
                dominio,
                [str(getattr(it, "cfop", "") or "").strip() for it in itens_nf],
            )
            continue

        if filtro_item_extra is not None:
            itens_filtrados = [it for it in itens_cfop_ok if bool(filtro_item_extra(it))]
            if not itens_filtrados:
                logger.debug("C100 ausentes - Filtro Extra | chave=%s",
                             chave,
                             )
                continue
        else:
            itens_filtrados = itens_cfop_ok

        cfops_nf = sorted({
            str(getattr(it, "cfop", "") or "").strip()
            for it in itens_filtrados
            if str(getattr(it, "cfop", "") or "").strip()
        })
        valor_total_nf = (
            getattr(nf, "vl_doc", None)
            or getattr(nf, "valor_total", None)
            or 0
        )
        numero_nf = (
            getattr(nf, "numero_nf", None)
            or getattr(nf, "num_doc", None)
            or getattr(nf, "numero", None)
            or ""
        )
        serie_nf = (
            getattr(nf, "serie_nf", None)
            or getattr(nf, "serie", None)
            or ""
        )
        dt_doc = (
            getattr(nf, "dt_doc", None)
            or getattr(nf, "data_emissao", None)
            or ""
        )
        participante_nome = (
            getattr(nf, "nome_participante", None)
            or getattr(nf, "razao_social", None)
            or getattr(nf, "nome_emitente", None)
            or ""
        )
        resultados.append({
            "origem": "ICMS_IPI",
            "tipo_match": "CONTRIB_SEM_C100",
            "status": "NAO_ESCRITURADO",
            "nf_icms_base_id": int(nf.id),
            "chave_nfe": chave,
            "numero_nf": str(numero_nf or ""),
            "serie_nf": str(serie_nf or ""),
            "dt_doc": str(dt_doc or ""),
            "participante_nome": str(participante_nome or ""),
            "valor_total_nf": str(valor_total_nf or "0"),
            "cfops": cfops_nf,
            "qtd_itens_elegiveis": len(itens_filtrados),
            "nf_icms_item_ids": [int(it.id) for it in itens_filtrados],
            "ind_oper": ind_oper,
            "cod_sit": cod_sit,

            # novo: contexto para a regra diagnóstica decidir
            "nota_elegivel_para_insercao": True,
            "itens_contexto": [
                {
                    "id": int(getattr(it, "id", 0) or 0),
                    "cod_item": str(getattr(it, "cod_item", "") or "").strip(),
                    "descricao": str(
                        getattr(it, "descr_item", None)
                        or getattr(it, "descricao", None)
                        or getattr(it, "descricao_item", None)
                        or getattr(it, "desc_item", None)
                        or ""
                    ).strip(),
                    "cfop": str(getattr(it, "cfop", "") or "").strip(),
                    "ncm": str(getattr(it, "ncm", "") or getattr(it, "cod_ncm", "") or "").strip(),
                    "cst_icms": str(getattr(it, "cst_icms", "") or "").strip(),
                    "origem_item": str(getattr(it, "origem_item", "") or "").strip(),
                }
                for it in itens_filtrados
            ],
            "ncms": sorted({
                str(getattr(it, "ncm", "") or getattr(it, "cod_ncm", "") or "").strip()
                for it in itens_filtrados
                if str(getattr(it, "ncm", "") or getattr(it, "cod_ncm", "") or "").strip()
            }),
            "descricoes_itens": [
                str(
                    getattr(it, "descr_item", None)
                    or getattr(it, "descricao", None)
                    or getattr(it, "descricao_item", None)
                    or getattr(it, "desc_item", None)
                    or ""
                ).strip()
                for it in itens_filtrados
            ],

            "registro_id_ancora": None,
            "linha_ancora": 0,
        })

    return resultados