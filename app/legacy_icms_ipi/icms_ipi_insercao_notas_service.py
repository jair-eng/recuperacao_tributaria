from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Set
from sqlalchemy.orm import Session

from app.Legacy.fiscal.constants import DOM_GERAL
from app.db.models import EfdRegistro, EfdRevisao, NfIcmsItem
from app.db.models.nf_icms_base import NfIcmsBase
from app.icms_ipi.icms_0150_agregador import resolver_ou_criar_0150_por_cnpj, _fmt_campo
from app.icms_ipi.icms_c170_utils import inserir_c170s_da_nf_encadeados, montar_linha_c170_de_icms
from app.icms_ipi.icms_helpers import (
    _campo,
    _only_digits,
    fmt_sped_num,
)
from app.icms_ipi.icms_utils_fiscal import _filtrar_notas_elegiveis_por_dominio, _cfop_item_icms, \
    _cfop_elegivel_por_dominio
from types import SimpleNamespace

from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert
from app.services.dominio_service import resolver_dominio_por_versao
from app.sped.bloco_0.bloco_0_0190_0200_agregador import _garantir_mestres_para_notas_elegiveis
from app.sped.logic.consolidador import _get_dados, consolidar_totais_no_proprio_c100_inserido
from app.sped.revisao_overlay import LinhaLogica
from app.sped.utils_geral import q2
import logging

from app.utils.sped import preview_linha_sped

log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


def _listar_chaves_c100_existentes(
    db: Session,
    *,
    versao_origem_id: int,
) -> tuple[Set[str], List[EfdRegistro]]:
    regs = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "C100",
        )
        .order_by(EfdRegistro.linha.asc())
        .all()
    )

    chaves: Set[str] = set()

    for r in regs:
        dados = _get_dados(r)
        chave = _only_digits(_campo(dados, 7))
        if chave:
            chaves.add(chave)

    return chaves, regs

def _resolver_ancora_bloco_c_fim(
    db: Session,
    *,
    versao_origem_id: int,
) -> tuple[Optional[int], int, str]:
    reg_c990 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "C990",
        )
        .order_by(EfdRegistro.linha.asc())
        .first()
    )

    if reg_c990:
        return int(reg_c990.id), int(getattr(reg_c990, "linha", 0) or 0), "INSERT_BEFORE"

    # fallback antigo, se não houver C990
    regs_c100 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "C100",
        )
        .order_by(EfdRegistro.linha.asc())
        .all()
    )

    if regs_c100:
        ultimo = regs_c100[-1]
        return int(ultimo.id), int(getattr(ultimo, "linha", 0) or 0), "INSERT_AFTER"

    return None, 0, "INSERT_AFTER"

def _resolver_ancora_bloco_c_fim(
    db: Session,
    *,
    versao_origem_id: int,
) -> tuple[Optional[int], int, str]:
    reg_c990 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "C990",
        )
        .order_by(EfdRegistro.linha.asc())
        .first()
    )

    if reg_c990:
        return int(reg_c990.id), int(getattr(reg_c990, "linha", 0) or 0), "INSERT_BEFORE"

    # fallback antigo, se não houver C990
    regs_c100 = (
        db.query(EfdRegistro)
        .filter(
            EfdRegistro.versao_id == int(versao_origem_id),
            EfdRegistro.reg == "C100",
        )
        .order_by(EfdRegistro.linha.asc())
        .all()
    )

    if regs_c100:
        ultimo = regs_c100[-1]
        return int(ultimo.id), int(getattr(ultimo, "linha", 0) or 0), "INSERT_AFTER"

    return None, 0, "INSERT_AFTER"

def montar_linha_c100_de_icms(nf: NfIcmsBase) -> str:
    dt_doc_txt = nf.dt_doc.strftime("%d%m%Y") if getattr(nf, "dt_doc", None) else ""
    dt_es_txt = nf.dt_es.strftime("%d%m%Y") if getattr(nf, "dt_es", None) else dt_doc_txt

    vl_doc = q2(getattr(nf, "vl_doc", Decimal("0")) or Decimal("0"))
    vl_icms = q2(getattr(nf, "vl_icms", Decimal("0")) or Decimal("0"))

    # C100 nasce zerado em PIS/COFINS.
    # Depois os totais são consolidados pela soma dos C170 finais.
    vl_pis = Decimal("0.00")
    vl_cofins = Decimal("0.00")

    campos = [
        "C100",                                     # 1
        "0",                                        # 2 IND_OPER
        "1",                                        # 3 IND_EMIT
        str(getattr(nf, "cod_part", "") or ""),     # 4 COD_PART
        str(getattr(nf, "cod_mod", "") or "55"),    # 5 COD_MOD
        str(getattr(nf, "cod_sit", "") or "00"),    # 6 COD_SIT
        str(getattr(nf, "serie", "") or ""),        # 7 SER
        str(getattr(nf, "num_doc", "") or ""),      # 8 NUM_DOC
        str(getattr(nf, "chave_nfe", "") or ""),    # 9 CHV_NFE
        dt_doc_txt,                                 # 10 DT_DOC
        dt_es_txt,                                  # 11 DT_E_S
        fmt_sped_num(vl_doc),                       # 12 VL_DOC
        "0",                                        # 13 IND_PGTO
        "0",                                        # 14 VL_DESC
        "0",                                        # 15 ABAT_NT
        fmt_sped_num(vl_doc),                       # 16 VL_MERC
        "0",                                        # 17 IND_FRT
        "0",                                        # 18 VL_FRT
        "0",                                        # 19 VL_SEG
        "0",                                        # 20 VL_OUT_DA
        fmt_sped_num(vl_doc),                       # 21 VL_BC_ICMS
        fmt_sped_num(vl_icms),                      # 22 VL_ICMS
        "0",                                        # 23 VL_BC_ICMS_ST
        "0",                                        # 24 VL_ICMS_ST
        "0",                                        # 25 VL_PIS
        fmt_sped_num(vl_pis),                       # 26
        fmt_sped_num(vl_cofins),                    # 27
        "0",                                        # 28
        "0",                                        # 29
    ]

    if len(campos) != 29:
        raise ValueError(f"C100 inválido: esperado 29 campos, veio {len(campos)}")

    linha = "|" + "|".join(campos) + "|"

    return linha

def _ja_existe_revisao_insert_para_nf(
    db: Session,
    *,
    versao_origem_id: int,
    nf_icms_base_id: int,
    motivo_codigo: str = "CORRETIVA_V2_SO_ICMS",
) -> bool:
    qs = (
        db.query(EfdRevisao.id)
        .filter(EfdRevisao.versao_origem_id == int(versao_origem_id))
        .filter(EfdRevisao.acao.in_(["INSERT_AFTER", "INSERT_BEFORE"]))
        .filter(EfdRevisao.reg == "C100")
        .filter(EfdRevisao.motivo_codigo == motivo_codigo)
        .all()
    )

    for rid, in qs:
        rv = db.query(EfdRevisao).filter(EfdRevisao.id == rid).first()
        j = getattr(rv, "revisao_json", None) or {}
        if int(j.get("nf_icms_base_id") or 0) == int(nf_icms_base_id):
            return True

    return False

def _criar_revisao_insert_c100_faltante(
    db: Session,
    *,
    versao_origem_id: int,
    registro_id_alvo: int | None,
    linha_ref: int,
    nf: NfIcmsBase,
    motivo_codigo: str = "CORRETIVA_V2_SO_ICMS",
    apontamento_id: int | None = None,
    acao: str = "INSERT_AFTER",
) -> EfdRevisao:

    logger.warning(
        "[C100_INSERT] INICIO | versao=%s | nf_id=%s | chave_nfe=%s | registro_id_alvo=%s | linha_ref=%s | motivo=%s | apontamento_id=%s | acao=%s",
        versao_origem_id,
        getattr(nf, "id", None),
        getattr(nf, "chave_nfe", None),
        registro_id_alvo,
        linha_ref,
        motivo_codigo,
        apontamento_id,
        acao,
    )
    # 1️⃣ garante participante
    cod_part_final = _fmt_campo(getattr(nf, "cod_part", None))

    logger.warning(
        "[C100_INSERT] COD_PART_INICIAL | nf_id=%s | cod_part_nf=%s",
        getattr(nf, "id", None),
        getattr(nf, "cod_part", None),
    )
    if not cod_part_final:
        cod_part_final = resolver_ou_criar_0150_por_cnpj(
            db,
            versao_id=versao_origem_id,
            nf=nf,
        )
    logger.warning(
        "[C100_INSERT] COD_PART_GERADO_0150 | nf_id=%s | cod_part_final=%s",
        getattr(nf, "id", None),
        cod_part_final,
    )

    # atualiza o objeto da nota
    nf.cod_part = cod_part_final

    logger.debug(
        "C100 COD_PART resolvido | nf_id=%s chave_nfe=%s cod_part_final=%s",
        getattr(nf, "id", None),
        getattr(nf, "chave_nfe", None),
        cod_part_final,
    )

    # 2️⃣ monta linha C100
    linha_nova = montar_linha_c100_de_icms(nf)

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=registro_id_alvo,
        reg="C100",
        acao=str(acao).upper(),
        revisao_json={
            "linha_nova": linha_nova,
            "linha_referencia": int(linha_ref or 0),
            "nf_icms_base_id": int(nf.id),
            "origem": "ICMS_IPI",
            "motivo": "Nota presente no ICMS/IPI e ausente no C100 da EFD Contribuições",
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )
    db.add(rv)
    db.flush()
    logger.warning(
        "[C100_INSERT] REVISAO_CRIADA | revisao_id=%s | versao=%s | nf_id=%s | chave_nfe=%s | registro_id_alvo=%s | linha_ref=%s | motivo=%s",
        rv.id,
        versao_origem_id,
        getattr(nf, "id", None),
        getattr(nf, "chave_nfe", None),
        registro_id_alvo,
        linha_ref,
        motivo_codigo,
    )
    return rv

def _inserir_bloco_nf_icms_na_efd(
    db: Session,
    *,
    versao_origem_id: int,
    nf: NfIcmsBase,
    itens: List[NfIcmsItem],
    registro_id_alvo: int | None,
    linha_ref_alvo: int,
    acao_inicial: str,
    apontamento_id: int | None = None,
    contexto: str | None = None,
    fator_base_credito: float | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
    cod_cred: str | None = None,
    nat_bc_cred: str | None = None,
    motivo_codigo: str = "CORRETIVA_V2_SO_ICMS",
) -> Dict[str, Any]:
    chave = _only_digits(getattr(nf, "chave_nfe", None))

    rv_c100 = _criar_revisao_insert_c100_faltante(
        db,
        versao_origem_id=versao_origem_id,
        registro_id_alvo=registro_id_alvo,
        linha_ref=linha_ref_alvo,
        nf=nf,
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
        acao=acao_inicial,
    )
    db.flush()

    log.info(
        "Bloco NF C100 criado nf_id=%s chave=%s revisao_id=%s registro_id_alvo=%s linha_ref_alvo=%s acao=%s",
        nf.id,
        chave,
        rv_c100.id,
        registro_id_alvo,
        linha_ref_alvo,
        acao_inicial,
    )

    # 2) recarrega e acha o C100 inserido
    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db,
        versao_origem_id=int(versao_origem_id),
        versao_final_id=None,
    )

    linha_c100 = None

    for l in linhas:
        if (
                str(getattr(l, "reg", "")).upper() == "C100"
                and getattr(l, "revisao_id", None) == rv_c100.id
        ):
            linha_c100 = l
            break

    if not linha_c100:
        log.warning(
            "Bloco NF C100 não localizado no overlay nf_id=%s chave=%s revisao_id=%s",
            nf.id,
            chave,
            rv_c100.id,
        )
        return {
            "c100_inserido": 1,
            "c170_inseridos": 0,
            "revisao_c100_id": int(rv_c100.id),
            "registro_id_fim_bloco": registro_id_alvo,
            "linha_fim_bloco": linha_ref_alvo,
        }

    log.debug(
        "Bloco NF C100 localizado nf_id=%s chave=%s revisao_id=%s linha_c100=%s registro_id_c100=%s",
        nf.id,
        chave,
        rv_c100.id,
        getattr(linha_c100, "linha", None),
        getattr(linha_c100, "registro_id", None),
    )
    #####
    try:
        idx_c100 = linhas.index(linha_c100)
        janela = linhas[max(0, idx_c100 - 5): idx_c100 + 6]

        log.warning(
            "[LOCALIZAR C100 DBG] nf=%s chave=%s rev=%s idx=%s linha=%s reg_id=%s total_linhas=%s",
            nf.id,
            chave,
            rv_c100.id,
            idx_c100,
            getattr(linha_c100, "linha", None),
            getattr(linha_c100, "registro_id", None),
            len(linhas),
        )

        for j, lx in enumerate(janela, start=max(0, idx_c100 - 5)):
            log.warning(
                "[LOCALIZAR C100 DBG] ctx idx=%s linha=%s reg=%s rev=%s rid=%s pai=%s dados0=%s",
                j,
                getattr(lx, "linha", None),
                getattr(lx, "reg", None),
                getattr(lx, "revisao_id", None),
                getattr(lx, "registro_id", None),
                getattr(lx, "pai_id", None),
                (getattr(lx, "dados", []) or [])[:8],
            )
    except Exception:
        log.exception(
            "[LOCALIZAR C100 DBG] erro ao logar contexto nf=%s rev=%s",
            nf.id,
            rv_c100.id,
        )
    ##

    log.warning(
        "[NF BLOCO] C170 START "
        "nf=%s "
        "c100_rev=%s "
        "c100_linha=%s "
        "c100_registro=%s",
        getattr(nf, "id", None),
        rv_c100.id,
        getattr(linha_c100, "linha", None),
        getattr(linha_c100, "registro_id", None),
    )

    res_c170 = inserir_c170s_da_nf_encadeados(
        db,
        versao_origem_id=versao_origem_id,
        nf=nf,
        itens=itens,
        linha_c100=linha_c100,
        contexto=contexto,
        fator_base_credito=fator_base_credito,
        aliq_pis=aliq_pis,
        aliq_cofins=aliq_cofins,
        cod_cred=cod_cred,
        nat_bc_cred=nat_bc_cred,
        apontamento_id=apontamento_id,
        motivo_codigo=motivo_codigo,
    )

    log.warning(
        "[NF BLOCO] C170 END "
        "nf=%s "
        "fim_linha=%s "
        "fim_registro=%s",
        getattr(nf, "id", None),
        res_c170["linha_fim_bloco"],
        res_c170["registro_id_fim_bloco"],
    )

    log.info(
        "Bloco NF finalizado nf_id=%s chave=%s revisao_c100_id=%s c170_inseridos=%s linha_fim_bloco=%s registro_id_fim_bloco=%s",
        nf.id,
        chave,
        rv_c100.id,
        int(res_c170["total_inseridos"]),
        res_c170["linha_fim_bloco"],
        res_c170["registro_id_fim_bloco"],
    )

    rv_c100_sum_id = consolidar_totais_no_proprio_c100_inserido(
        db,
        versao_origem_id=versao_origem_id,
        versao_final_id=None,
        revisao_c100_id=int(rv_c100.id),
    )

    log.info(
        "C100 consolidado por soma dos filhos nf_id=%s chave=%s revisao_c100_id=%s revisao_c100_sum_id=%s",
        nf.id,
        chave,
        rv_c100.id,
        rv_c100_sum_id,
    )

    return {
        "c100_inserido": 1,
        "c170_inseridos": int(res_c170["total_inseridos"]),
        "revisao_c100_id": int(rv_c100.id),
        "registro_id_fim_bloco": res_c170["registro_id_fim_bloco"],
        "linha_fim_bloco": res_c170["linha_fim_bloco"],
    }

def _inserir_bloco_nf_icms_na_efd_v2_linhas_novas(
    db: Session,
    *,
    versao_origem_id: int,
    nf: NfIcmsBase,
    itens: list[NfIcmsItem],
    registro_id_alvo: int | None,
    linha_ref_alvo: int,
    acao_inicial: str,
    apontamento_id: int | None = None,
    contexto: str | None = None,
    cst_pis_destino: str | None = None,
    cst_cofins_destino: str | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
    cod_cred: str | None = None,
    nat_bc_cred: str | None = None,
    motivo_codigo: str = "CORRETIVA_V2_SO_ICMS",
) -> dict:
    nf_id = int(getattr(nf, "id", 0) or 0)
    chave = _only_digits(getattr(nf, "chave_nfe", None))
    dominio = resolver_dominio_por_versao(db, versao_origem_id) or DOM_GERAL

    logger.warning(
        "[INSERIR_NF_V2_BLOCO][START] "
        "versao=%s nf=%s chave=%s itens=%s dominio=%s "
        "ancora=(registro_id=%s linha=%s acao=%s) "
        "contexto=%s cod_cred=%s nat=%s "
        "cst_pis=%s cst_cofins=%s "
        "aliq_pis=%s aliq_cofins=%s apontamento=%s",
        versao_origem_id,
        nf_id,
        chave,
        len(itens or []),
        dominio,
        registro_id_alvo,
        linha_ref_alvo,
        acao_inicial,
        contexto,
        cod_cred,
        nat_bc_cred,
        cst_pis_destino,
        cst_cofins_destino,
        aliq_pis,
        aliq_cofins,
        apontamento_id,
    )

    linha_c100 = montar_linha_c100_de_icms(nf)

    linhas_novas = [linha_c100]

    logger.warning(
        "[INSERIR_NF_V2_BLOCO][C100] nf=%s chave=%s linha=%s",
        nf_id,
        chave,
        preview_linha_sped(linha_c100),
    )

    for idx, it in enumerate(itens, start=1):
        item_id = int(getattr(it, "id", 0) or 0)
        cod_item = getattr(it, "cod_item", None)
        num_item = getattr(it, "num_item", None)

        linha_c170 = montar_linha_c170_de_icms(
            it,
            dominio=dominio,
            contexto=contexto,
            cst_pis_destino=cst_pis_destino,
            cst_cofins_destino=cst_cofins_destino,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
        )

        linhas_novas.append(linha_c170)

        logger.info(
            "[INSERIR_NF_V2_BLOCO][C170] nf=%s chave=%s ordem=%s item_id=%s num_item=%s cod_item=%s linha=%s",
            nf_id,
            chave,
            idx,
            item_id,
            num_item,
            cod_item,
            preview_linha_sped(linha_c170),
        )

    qtd_c100 = sum(1 for l in linhas_novas if str(l or "").startswith("|C100|"))
    qtd_c170 = sum(1 for l in linhas_novas if str(l or "").startswith("|C170|"))

    logger.warning(
        "[INSERIR_NF_V2_BLOCO][VALIDA_LINHAS] nf=%s chave=%s total_linhas=%s qtd_c100=%s qtd_c170=%s itens_origem=%s ok_ordem=%s",
        nf_id,
        chave,
        len(linhas_novas),
        qtd_c100,
        qtd_c170,
        len(itens or []),
        bool(linhas_novas and str(linhas_novas[0]).startswith("|C100|") and qtd_c100 == 1 and qtd_c170 == len(itens or [])),
    )

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=registro_id_alvo,
        reg="C100",
        acao=acao_inicial,
        revisao_json={
            "linhas_novas": linhas_novas,
            "linha_referencia": int(linha_ref_alvo or 0),
            "nf_icms_base_id": nf_id,
            "nf_icms_item_ids": [
                int(getattr(it, "id", 0) or 0)
                for it in itens
            ],
            "mapa_linha_nf_icms_item_id": {
                str(i + 1): int(getattr(it, "id", 0) or 0)
                for i, it in enumerate(itens)
            },
            "origem": "ICMS_IPI",
            "tipo_bloco": "C100_C170_V2",
            "contexto": contexto,
            "cod_cred": cod_cred,
            "nat_bc_cred": nat_bc_cred,
            "cst_pis_destino": cst_pis_destino,
            "cst_cofins_destino": cst_cofins_destino,
            "aliq_pis": aliq_pis,
            "aliq_cofins": aliq_cofins,
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )

    db.add(rv)
    db.flush()

    logger.warning(
        "[INSERIR_NF_V2_BLOCO][REVISAO_CRIADA] rv=%s nf=%s chave=%s reg=%s acao=%s "
        "registro_id=%s linha_ref=%s linhas_novas=%s c100=%s c170=%s item_ids=%s",
        rv.id,
        nf_id,
        chave,
        rv.reg,
        rv.acao,
        rv.registro_id,
        linha_ref_alvo,
        len(linhas_novas),
        qtd_c100,
        qtd_c170,
        [int(getattr(it, "id", 0) or 0) for it in itens],
    )
    rv_c100_sum_id = consolidar_totais_no_proprio_c100_inserido(
        db,
        versao_origem_id=versao_origem_id,
        versao_final_id=None,
        revisao_c100_id=int(rv.id),
    )

    logger.warning(
        "[INSERIR_NF_V2_BLOCO][C100_CONSOLIDADO] "
        "nf=%s chave=%s revisao_bloco=%s revisao_sum=%s",
        nf_id,
        chave,
        rv.id,
        rv_c100_sum_id,
    )

    return {
        "c100_inserido": 1,
        "c170_inseridos": max(0, len(linhas_novas) - 1),
        "revisao_c100_id": int(rv.id),
        "revisao_c100_sum_id": rv_c100_sum_id,
        "registro_id_fim_bloco": registro_id_alvo,
        "linha_fim_bloco": linha_ref_alvo,
        "revisao_fim_bloco_id": int(rv.id),
    }


def inserir_notas_icms_ausentes_na_efd_v2(
    db: Session,
    *,
    versao_origem_id: int,
    notas_elegiveis: list[dict],
    periodo: str | None = None,
    apontamento_id: int | None = None,
    nf_icms_base_ids: list[int] | None = None,
    contexto: str | None = None,
    motivo_codigo: str = "CORRETIVA_V2_SO_ICMS",
) -> dict:
    total_c100_insert = 0
    total_c170_insert = 0
    detalhes = []
    mensagens = []

    chaves_existentes, _regs_c100 = _listar_chaves_c100_existentes(
        db,
        versao_origem_id=versao_origem_id,
    )

    registro_id_alvo, linha_ref_alvo, acao_inicial = _resolver_ancora_bloco_c_fim(
        db,
        versao_origem_id=versao_origem_id,
    )

    if not notas_elegiveis:
        return {
            "ok": True,
            "versao_origem_id": int(versao_origem_id),
            "total_notas_ausentes": 0,
            "total_c100_insert": 0,
            "total_c170_insert": 0,
            "detalhes": [],
            "mensagens": ["Nenhuma nota elegível V2 para inserir."],
        }

    logger.info(
        "[INSERIR_NF_V2] inicio | versao=%s notas=%s",
        versao_origem_id,
        len(notas_elegiveis),
    )

    notas_elegiveis = sorted(
        notas_elegiveis,
        key=lambda x: (
            str(getattr(x.get("nf"), "dt_doc", "") or ""),
            str(getattr(x.get("nf"), "num_doc", "") or ""),
            str(x.get("chave") or getattr(x.get("nf"), "chave_nfe", "") or ""),
            int(getattr(x.get("nf"), "id", 0) or 0),
        ),
    )

    notas_para_mestres = [
        (
            item["nf"],
            item["itens"],
            str(item.get("chave") or getattr(item["nf"], "chave_nfe", "") or ""),
        )
        for item in notas_elegiveis
        if item.get("nf") and item.get("itens")
    ]

    res_mestres = _garantir_mestres_para_notas_elegiveis(
        db,
        versao_origem_id=versao_origem_id,
        notas_elegiveis=notas_para_mestres,
    )

    logger.info(
        "[INSERIR_NF_V2] mestres | 0150=%s 0190=%s 0200=%s 0500=%s",
        res_mestres.get("total_0150", 0),
        res_mestres.get("total_0190", 0),
        res_mestres.get("total_0200", 0),
        res_mestres.get("total_0500", 0),
    )



    logger.warning(
        "[INSERIR_NF_V2] ancora inicial | registro_id=%s linha=%s acao=%s",
        registro_id_alvo,
        linha_ref_alvo,
        acao_inicial,
    )
    logger.warning(
        "[INSERIR_NF_V2][ANCORA_CONGELADA] registro_id=%s linha=%s acao_inicial=%s notas=%s",
        registro_id_alvo,
        linha_ref_alvo,
        acao_inicial,
        len(notas_elegiveis),
    )

    for item in notas_elegiveis:
        nf = item.get("nf")
        itens = item.get("itens") or []

        if not nf or not itens:
            continue

        chave = str(item.get("chave") or getattr(nf, "chave_nfe", "") or "")
        nf_id = int(getattr(nf, "id", 0) or 0)

        if nf_id and _ja_existe_revisao_insert_para_nf(
            db,
            versao_origem_id=versao_origem_id,
            nf_icms_base_id=nf_id,
            motivo_codigo="CORRETIVA_V2_SO_ICMS",
        ):
            logger.info(
                "[INSERIR_NF_V2] skip NF revisão C100 já existe | nf=%s chave=%s",
                nf_id,
                chave,
            )
            continue

        contexto = item.get("contexto")
        cod_cred = item.get("cod_cred")
        nat_bc_cred = item.get("nat_bc_cred")
        cst_pis_destino = item.get("cst_pis_destino")
        cst_cofins_destino = item.get("cst_cofins_destino")
        aliq_pis = item.get("aliq_pis")
        aliq_cofins = item.get("aliq_cofins")
        apontamento_id = item.get("apontamento_id")

        logger.warning(
            "[INSERIR_NF_V2][NF_START] "
            "nf=%s chave=%s num_doc=%s serie=%s itens=%s "
            "ancora_antes=(%s,%s,%s) "
            "contexto=%s cod_cred=%s nat=%s "
            "cst_pis=%s cst_cofins=%s apontamento=%s",
            nf_id,
            chave,
            getattr(nf, "num_doc", None),
            getattr(nf, "serie", None),
            len(itens),
            registro_id_alvo,
            linha_ref_alvo,
            acao_inicial,
            contexto,
            cod_cred,
            nat_bc_cred,
            cst_pis_destino,
            cst_cofins_destino,
            apontamento_id,
        )

        res_bloco = _inserir_bloco_nf_icms_na_efd_v2_linhas_novas(
            db,
            versao_origem_id=versao_origem_id,
            nf=nf,
            itens=itens,
            registro_id_alvo=registro_id_alvo,
            linha_ref_alvo=linha_ref_alvo,
            acao_inicial=acao_inicial,
            apontamento_id=apontamento_id,
            contexto=contexto,
            cst_pis_destino=cst_pis_destino,
            cst_cofins_destino=cst_cofins_destino,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
            cod_cred=cod_cred,
            nat_bc_cred=nat_bc_cred,
            motivo_codigo=motivo_codigo,
        )
        c100_insert = int(res_bloco.get("c100_inserido") or 0)
        c170_insert = int(res_bloco.get("c170_inseridos") or 0)
        logger.warning(
            "[INSERIR_NF_V2][NF_OK] nf=%s chave=%s revisao=%s c100=%s c170=%s "
            "ancora_depois=(%s,%s,%s) OBS=ancora_deve_permanecer_igual",
            nf_id,
            chave,
            res_bloco.get("revisao_c100_id"),
            c100_insert,
            c170_insert,
            registro_id_alvo,
            linha_ref_alvo,
            acao_inicial,
        )

        total_c100_insert += c100_insert
        total_c170_insert += c170_insert

        chaves_existentes.add(chave)

        detalhes.append({
            "nf_icms_base_id": nf_id,
            "chave_nfe": chave,
            "num_doc": str(getattr(nf, "num_doc", "") or ""),
            "serie": str(getattr(nf, "serie", "") or ""),
            "itens": len(itens),
            "revisao_c100_id": res_bloco.get("revisao_c100_id"),
            "c170_inseridos": res_bloco["c170_inseridos"],
            "linha_ref_final": linha_ref_alvo,
            "registro_id_final": registro_id_alvo,
            "contexto": contexto,
            "cod_cred": cod_cred,
            "nat_bc_cred": nat_bc_cred,
            "cst_pis_destino": cst_pis_destino,
            "cst_cofins_destino": cst_cofins_destino,
        })

    db.flush()

    mensagens.append(f"{len(notas_elegiveis)} notas V2 elegíveis para inserção")
    mensagens.append(f"{res_mestres.get('total_0150', 0)} registros 0150 criados")
    mensagens.append(f"{res_mestres.get('total_0190', 0)} registros 0190 criados")
    mensagens.append(f"{res_mestres.get('total_0200', 0)} registros 0200 criados")
    mensagens.append(f"{total_c100_insert} registros C100 inseridos")
    mensagens.append(f"{total_c170_insert} registros C170 inseridos")

    logger.warning(
        "[INSERIR_NF_V2][RESUMO_FINAL] versao=%s notas_elegiveis=%s detalhes=%s "
        "c100_total=%s c170_total=%s ancora_final=(%s,%s,%s)",
        versao_origem_id,
        len(notas_elegiveis),
        len(detalhes),
        total_c100_insert,
        total_c170_insert,
        registro_id_alvo,
        linha_ref_alvo,
        acao_inicial,
    )

    return {
        "ok": True,
        "versao_origem_id": int(versao_origem_id),
        "total_notas_ausentes": len(notas_elegiveis),
        "total_c100_insert": total_c100_insert,
        "total_c170_insert": total_c170_insert,
        "total_0150_criados": int(res_mestres.get("total_0150", 0)),
        "total_0190_criados": int(res_mestres.get("total_0190", 0)),
        "total_0200_criados": int(res_mestres.get("total_0200", 0)),
        "detalhes": detalhes,
        "mensagens": mensagens,
    }