from __future__ import annotations


from typing import Any, Dict, List
from app.config.settings import ALIQUOTA_PIS_PCT, ALIQUOTA_COFINS_PCT
from decimal import Decimal
from sqlalchemy.orm import Session
from app.db.models import NfIcmsItem, EfdRevisao, NfIcmsBase
from typing import TYPE_CHECKING

from app.Legacy.fiscal.constants import DOM_GERAL
from app.Legacy.fiscal.regras.helpers.elegibilidade_dominio import resolver_cst_credito_por_dominio
from app.icms_ipi.icms_helpers import fmt_sped_num, q2, fmt_sped_qtd
from app.icms_ipi.icms_utils_fiscal import _cfop_elegivel_por_dominio
from app.services.dominio_service import resolver_dominio_por_versao
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert
from app.sped.revisao_overlay import LinhaLogica
import logging

logger = logging.getLogger(__name__)
log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.legacy_icms_ipi.icms_ipi_cruzamento_service import DocCtx


def montar_linha_c170_de_icms(
    item,
    *,
    dominio: str,
    contexto: str | None = None,
    fator_base_credito: float | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
):
    vl_item = q2(item.vl_item)
    vl_desc = q2(item.vl_desc)
    vl_icms = q2(item.vl_icms)

    # base padrão
    base = q2(vl_item - vl_desc - vl_icms)
    if base < 0:
        base = Decimal("0.00")

    # modo novo só entra se vier explicitamente
    if fator_base_credito is not None:
        base = q2(base * Decimal(str(fator_base_credito)))

    qtd = getattr(item, "qtd", None)
    unid = getattr(item, "unid", None)
    cst_icms = getattr(item, "cst_icms", None)
    aliq_icms = getattr(item, "aliq_icms", None)
    cod_nat = getattr(item, "cod_nat", None)
    cod_cta = getattr(item, "cod_cta", None)

    cst_pis_credito, cst_cofins_credito = resolver_cst_credito_por_dominio(
        dominio=dominio,
        contexto=contexto,
    )

    aliq_pis_pct = Decimal(str(aliq_pis or fmt_sped_num(ALIQUOTA_PIS_PCT)).replace(",", "."))
    aliq_cofins_pct = Decimal(str(aliq_cofins or fmt_sped_num(ALIQUOTA_COFINS_PCT)).replace(",", "."))

    vl_pis = q2(base * (aliq_pis_pct / Decimal("100")))
    vl_cofins = q2(base * (aliq_cofins_pct / Decimal("100")))

    campos = [
        "C170",
        str(item.num_item or "1"),
        str(item.cod_item or ""),
        str(item.descricao or ""),
        fmt_sped_qtd(qtd),
        unid or "",
        fmt_sped_num(vl_item),
        fmt_sped_num(vl_desc),
        "0",
        str(cst_icms or "").strip(),
        item.cfop or "",
        str(cod_nat or "").strip(),
        fmt_sped_num(vl_item),
        fmt_sped_num(aliq_icms) if aliq_icms not in (None, "") else "0,00",
        fmt_sped_num(vl_icms),
        "0,00",
        "0,00",
        "0,00",
        "",
        "",
        "",
        "0,00",
        "0,00",
        "0,00",
        cst_pis_credito,
        fmt_sped_num(base),
        str(aliq_pis or fmt_sped_num(ALIQUOTA_PIS_PCT)),
        "",
        "",
        fmt_sped_num(vl_pis),
        cst_cofins_credito,
        fmt_sped_num(base),
        str(aliq_cofins or fmt_sped_num(ALIQUOTA_COFINS_PCT)),
        "",
        "",
        fmt_sped_num(vl_cofins),
        (str(cod_cta).strip() if cod_cta else ""),
    ]

    if not item.cod_item:
        log.warning(
            "C170 sem cod_item item_id=%s num_item=%s cfop=%s descricao=%s",
            item.id,
            item.num_item,
            item.cfop,
            item.descricao,
        )

    if base < 0:
        log.warning(
            "C170 com base negativa item_id=%s cod_item=%s vl_item=%s vl_desc=%s base=%s",
            item.id,
            item.cod_item,
            vl_item,
            vl_desc,
            base,
        )

    while len(campos) < 37:
        campos.append("")

    if len(campos) != 37:
        log.error(
            "C170 inválido antes de montar linha item_id=%s cod_item=%s len_campos=%s",
            item.id,
            item.cod_item,
            len(campos),
        )
        raise ValueError(f"C170 inválido: esperado 37 campos, veio {len(campos)}")

    linha = "|" + "|".join(campos) + "|"

    log.debug(
        "C170 montado item_id=%s cod_item=%s cfop=%s cst_pis=%s cst_cofins=%s base=%s vl_pis=%s vl_cofins=%s",
        item.id,
        item.cod_item,
        item.cfop,
        campos[24],
        campos[30],
        campos[25],
        campos[29],
        campos[35],
    )

    return linha


def _registro_insercao_alvo(
    doc_ctx: DocCtx,
    itens_c170: list[Dict[str, Any]],
) -> tuple[int | None, int]:
    """
    Se houver C170, insere após o último C170.
    Senão, insere após o C100.
    Retorna: (registro_id_alvo, linha_ref)
    """
    if itens_c170:
        ultimo = itens_c170[-1]
        return (
            int(ultimo.get("registro_id") or 0) or None,
            int(ultimo.get("linha_num") or 0) or doc_ctx.linha_c100,
        )

    return (
        doc_ctx.registro_id_c100,
        doc_ctx.linha_c100,
    )


def _criar_revisao_insert_c170_faltante_v2(
    db: Session,
    *,
    versao_origem_id: int,
    registro_id_alvo: int | None,
    linha_ref: int | None,
    item_icms: NfIcmsItem,
    contexto: str | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
    cod_cred: str | None = None,
    nat_bc_cred: str | None = None,
    motivo_codigo: str = "CREDITO_NAO_APROVEITADO_V2",
    apontamento_id: int | None = None,
) -> EfdRevisao | None:
    dominio = resolver_dominio_por_versao(db, versao_origem_id) or DOM_GERAL
    cfop_item = str(getattr(item_icms, "cfop", "") or "").strip()

    if not _cfop_elegivel_por_dominio(cfop_item, dominio=dominio):
        logger.info(
            "[INSERT_C170_V2] SKIP CFOP_NAO_ELEGIVEL_DOMINIO | versao=%s | dominio=%s | item=%s | cfop=%s",
            versao_origem_id,
            dominio,
            getattr(item_icms, "id", None),
            cfop_item,
        )
        return None

    if not registro_id_alvo:
        logger.warning(
            "[INSERT_C170_V2] SKIP SEM_REGISTRO_ALVO | versao=%s | item=%s | linha_ref=%s",
            versao_origem_id,
            getattr(item_icms, "id", None),
            linha_ref,
        )
        return None

    linha_nova = montar_linha_c170_de_icms(
        item_icms,
        dominio=dominio,
        contexto=contexto,
        aliq_pis=aliq_pis,
        aliq_cofins=aliq_cofins,
    )

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=int(registro_id_alvo),
        reg="C170",
        acao="INSERT_AFTER",
        revisao_json={
            "linha_nova": linha_nova,
            "linha_referencia": int(linha_ref or 0),
            "nf_icms_item_id": int(item_icms.id),
            "origem": "ICMS_IPI",
            "contexto": contexto,
            "cod_cred": cod_cred,
            "nat_bc_cred": nat_bc_cred,
            "meta": {
                "contexto_credito": contexto,
                "cod_cred": cod_cred,
                "nat_bc_cred": nat_bc_cred,
                "aliq_pis": aliq_pis,
                "aliq_cofins": aliq_cofins,
            },
            "motivo": "Item presente no ICMS/IPI e ausente no C170 da EFD Contribuições.",
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=apontamento_id,
    )

    db.add(rv)
    db.flush()
    return rv

def _ja_existe_revisao_insert_para_item(
    db: Session,
    *,
    versao_origem_id: int,
    nf_icms_item_id: int,
    contexto: str | None = None,
) -> bool:
    qs = (
        db.query(EfdRevisao)
        .filter(EfdRevisao.versao_origem_id == int(versao_origem_id))
        .filter(EfdRevisao.acao.in_(["INSERT_AFTER", "INSERT_BEFORE"]))
    )
    for rv in qs.all():
        j = getattr(rv, "revisao_json", None) or {}
        if int(j.get("nf_icms_item_id") or 0) != int(nf_icms_item_id):
            continue
        if contexto:
            ctx = str(
                j.get("contexto")
                or (j.get("meta") or {}).get("contexto_credito")
                or ""
            ).upper()
            if ctx != str(contexto).upper():
                continue
        return True
    return False

def inserir_c170s_da_nf_encadeados(
    db: Session,
    *,
    versao_origem_id: int,
    nf: NfIcmsBase,
    itens: List[NfIcmsItem],
    linha_c100: LinhaLogica,
    contexto: str | None = None,
    fator_base_credito: float | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
) -> Dict[str, Any]:
    total_inseridos = 0

    registro_id_alvo = getattr(linha_c100, "registro_id", None)
    linha_ref_alvo = int(getattr(linha_c100, "linha", 0) or 0)
    dominio = resolver_dominio_por_versao(db, versao_origem_id) or DOM_GERAL
    acao = "INSERT_AFTER"


    for idx, it in enumerate(itens, start=1):
        item_id = int(getattr(it, "id", 0) or 0)

        if item_id and _ja_existe_revisao_insert_para_item(
                db,
                versao_origem_id=int(versao_origem_id),
                nf_icms_item_id=item_id,
                contexto=contexto,
        ):
            log.info(
                "C170 insert ignorado: revisão já existe | versao=%s item_id=%s contexto=%s",
                versao_origem_id,
                item_id,
                contexto,
            )
            continue

        linha_nova = montar_linha_c170_de_icms(
            it,
            dominio=dominio,
            contexto=contexto,
            fator_base_credito=fator_base_credito,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
        )


        meta = None
        if str(contexto or "").strip().upper() == "LC192":
            meta = {
                "contexto_credito": "LC192",
                "tipo_credito": "COMB_LC192_V1",
                "cod_base_credito": "206",
                "natureza_credito_m": "206",
                "cst_pis": "61",
                "cst_cofins": "61",
            }

        rv = EfdRevisao(
            versao_origem_id=int(versao_origem_id),
            versao_revisada_id=None,
            registro_id=registro_id_alvo,
            reg="C170",
            acao=acao,
            revisao_json={
                "linha_nova": linha_nova,
                "linha_referencia": int(linha_ref_alvo or 0),
                "nf_icms_item_id": int(it.id),
                "nf_icms_base_id": int(nf.id),
                "origem": "ICMS_IPI",
                "contexto": contexto,
                "meta": meta,
            },
            motivo_codigo="CONTRIB_SEM_C170_V1",
        )

        db.add(rv)
        db.flush()


        total_inseridos += 1

        linhas = carregar_linhas_logicas_com_revisoes_e_insert(
            db,
            versao_origem_id=int(versao_origem_id),
            versao_final_id=None,
        )

        linha_c170_inserido = None
        for l in linhas:
            if (
                str(getattr(l, "reg", "")).upper() == "C170"
                and getattr(l, "revisao_id", None) == rv.id
            ):
                linha_c170_inserido = l
                break

        if linha_c170_inserido:

            registro_id_alvo = getattr(linha_c170_inserido, "registro_id", None)
            linha_ref_alvo = int(getattr(linha_c170_inserido, "linha", 0) or 0)
            acao = "INSERT_AFTER"
        else:
            log.warning(
                "C170 pos-overlay miss rv_id=%s nf_id=%s item_id=%s linha_ref_alvo_anterior=%s registro_id_alvo_anterior=%s",
                rv.id,
                getattr(nf, "id", None),
                int(getattr(it, "id", 0) or 0),
                linha_ref_alvo,
                registro_id_alvo,
            )




    return {
        "total_inseridos": total_inseridos,
        "registro_id_fim_bloco": registro_id_alvo,
        "linha_fim_bloco": linha_ref_alvo,
    }


def inserir_c170s_da_nf_encadeados_manual(
    db: Session,
    *,
    versao_origem_id: int,
    nf: NfIcmsBase,
    itens: List[NfIcmsItem],
    linha_c100: LinhaLogica,
    apontamento_id: int | None = None,
    contexto: str | None = None,
) -> Dict[str, Any]:
    total_inseridos = 0

    registro_id_alvo = getattr(linha_c100, "registro_id", None)
    linha_ref_alvo = int(getattr(linha_c100, "linha", 0) or 0)
    dominio = resolver_dominio_por_versao(db, versao_origem_id) or DOM_GERAL
    acao = "INSERT_AFTER"




    for idx, it in enumerate(itens, start=1):
        log.debug(
            "C170 item loop idx=%s nf_id=%s item_id=%s num_item=%s cod_item=%s cfop=%s",
            idx,
            getattr(nf, "id", None),
            int(getattr(it, "id", 0) or 0),
            getattr(it, "num_item", None),
            getattr(it, "cod_item", None),
            getattr(it, "cfop", None),
        )

        linha_nova = montar_linha_c170_de_icms(
            it,
            dominio=dominio,
            contexto="COMBUSTIVEL",
            fator_base_credito=0.75,
            aliq_pis="1,6500",
            aliq_cofins="7,6000",
        )


        meta = None

        if str(contexto or "").strip().upper() == "LC192":
            meta = {
                "contexto_credito": "LC192",
                "tipo_credito": "COMB_LC192_V1",
                "cod_base_credito": "206",
                "natureza_credito_m": "206",
                "cst_pis": "61",
                "cst_cofins": "61",
            }

        rv = EfdRevisao(
            versao_origem_id=int(versao_origem_id),
            versao_revisada_id=None,
            registro_id=registro_id_alvo,
            reg="C170",
            acao=acao,
            revisao_json={
                "linha_nova": linha_nova,
                "linha_referencia": int(linha_ref_alvo or 0),
                "nf_icms_item_id": int(it.id),
                "nf_icms_base_id": int(nf.id),
                "origem": "ICMS_IPI",
                "contexto": contexto,
                "meta": meta,
            },
            motivo_codigo="CONTRIB_SEM_C170_MANUAL_V1"
        )

        db.add(rv)
        db.flush()


        total_inseridos += 1

        linhas = carregar_linhas_logicas_com_revisoes_e_insert(
            db,
            versao_origem_id=int(versao_origem_id),
            versao_final_id=None,
        )

        linha_c170_inserido = None
        for l in linhas:
            if (
                str(getattr(l, "reg", "")).upper() == "C170"
                and getattr(l, "revisao_id", None) == rv.id
            ):
                linha_c170_inserido = l
                break

        if linha_c170_inserido:
            log.debug(
                "C170 pos-overlay ok rv_id=%s nf_id=%s item_id=%s linha=%s registro_id=%s revisao_id=%s",
                rv.id,
                getattr(nf, "id", None),
                int(getattr(it, "id", 0) or 0),
                getattr(linha_c170_inserido, "linha", None),
                getattr(linha_c170_inserido, "registro_id", None),
                getattr(linha_c170_inserido, "revisao_id", None),
            )

            registro_id_alvo = getattr(linha_c170_inserido, "registro_id", None)
            linha_ref_alvo = int(getattr(linha_c170_inserido, "linha", 0) or 0)
            acao = "INSERT_AFTER"
        else:
            log.warning(
                "C170 pos-overlay miss rv_id=%s nf_id=%s item_id=%s linha_ref_alvo_anterior=%s registro_id_alvo_anterior=%s",
                rv.id,
                getattr(nf, "id", None),
                int(getattr(it, "id", 0) or 0),
                linha_ref_alvo,
                registro_id_alvo,
            )

    return {
        "total_inseridos": total_inseridos,
        "registro_id_fim_bloco": registro_id_alvo,
        "linha_fim_bloco": linha_ref_alvo,
    }