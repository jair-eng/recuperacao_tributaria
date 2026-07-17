from sqlalchemy.orm import Session

from app.db.models import ItemFiscalConsolidado, EfdApontamento
from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd
from app.domain.fiscal.catalogo.bloqueio_classificacao_por_dominio import item_bloqueado_classificacao
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.diagnostico.diag_credito_nao_aproveitado import (
    diagnosticar_credito_nao_aproveitado,)
from app.domain.fiscal.meta.meta_item_fiscal import (
    meta_from_item_fiscal)
from app.utils.cached_utils import FiscalRuntimeCache
from app.utils.json_utils import json_safe
from app.utils.numbers import calcular_impacto_estimado
import time
import logging
logger = logging.getLogger(__name__)
from collections import Counter

def gerar_apontamentos_por_contexto(
    *,
    db: Session,
    versao_id: int,
):
    t0 = time.perf_counter()
    logger.info("## [GERAR_AP v%s] inicio ##", versao_id)

    # --------------------------------------------------
    # 1) Carrega itens
    # --------------------------------------------------
    itens = (
        db.query(ItemFiscalConsolidado)
        .filter(ItemFiscalConsolidado.versao_id == int(versao_id))
        .all()
    )

    total_itens = len(itens)
    empresa_id = itens[0].empresa_id if itens else None
    periodo = itens[0].periodo if itens else None

    logger.info(
        "## [GERAR_AP v%s] itens carregados=%s tempo=%.3fs ##",
        versao_id,
        total_itens,
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 2) Contexto GAP ECD
    # --------------------------------------------------
    contexto_gap_ecd = None

    if empresa_id and periodo:
        contexto_gap_ecd = montar_contexto_gap_ecd_efd(
            db=db,
            empresa_id=empresa_id,
            versao_id=int(versao_id),
            periodo=periodo,
        )

    logger.info(
        "## [GERAR_AP v%s] contexto_gap_ecd=%s tempo=%.3fs ##",
        versao_id,
        bool(contexto_gap_ecd),
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 3) Catálogo/cache
    # --------------------------------------------------
    catalogo = carregar_catalogo_fiscal(db)
    cache = FiscalRuntimeCache(catalogo=catalogo)

    classif_cache = {}
    cenario_cache = {}
    enquadramento_cache = {}
    score_cache = {}

    logger.info(
        "## [GERAR_AP v%s] catalogo carregado tempo=%.3fs ##",
        versao_id,
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 4) Limpa apontamentos V2 antigos em lotes
    # --------------------------------------------------
    total_del = 0

    while True:
        ids = [
            row[0]
            for row in (
                db.query(EfdApontamento.id)
                .filter(
                    EfdApontamento.versao_id == int(versao_id),
                    EfdApontamento.codigo.like("%_V2"),
                )
                .order_by(EfdApontamento.id.asc())
                .limit(500)
                .all()
            )
        ]

        if not ids:
            break

        apagados = (
            db.query(EfdApontamento)
            .filter(EfdApontamento.id.in_(ids))
            .delete(synchronize_session=False)
        )
        total_del += int(apagados or 0)
        db.flush()

    logger.info(
        "## [GERAR_AP v%s] apontamentos V2 antigos apagados=%s tempo=%.3fs ##",
        versao_id,
        total_del,
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 5) Loop principal
    # --------------------------------------------------
    novos_apontamentos = []
    total_diag = 0
    stats = Counter()

    por_natureza_gap = (
        (contexto_gap_ecd or {}).get("por_natureza") or {}
        if contexto_gap_ecd
        else {}
    )

    for item in itens:
        meta = meta_from_item_fiscal(item)

        # --------------------------------------------------
        # Trava de contaminação
        # --------------------------------------------------
        if item_bloqueado_classificacao(
                dominio=meta.get("dominio"),
                descricao=(
                        meta.get("descr_item")
                        or meta.get("descricao_item")
                        or meta.get("descricao")
                        or ""
                ),
        ):
            stats["bloqueado_contaminacao"] += 1
            continue

        classificacao = cache.classificar(meta)
        stats["classificados"] += 1

        cenario = cache.avaliar_cenario(meta, classificacao)

        if not cenario:
            stats["sem_cenario"] += 1

            continue

        cenario = cache.enriquecer_cenario(db, cenario)

        enquadramento = cenario.get("enquadramento") or {}
        nat_bc_cred = enquadramento.get("nat_bc_cred")

        if por_natureza_gap and nat_bc_cred:
            meta["ecd_gap"] = por_natureza_gap.get(
                str(nat_bc_cred).zfill(2)
            )

        diag = diagnosticar_credito_nao_aproveitado(
            meta=meta,
            classificacao=classificacao,
            cenario=cenario,
        )

        if not diag:
            stats["sem_diag"] += 1
            continue

        total_diag += 1
        stats["com_diag"] += 1

        meta_diag = diag.get("meta") or {}

        codigo_cenario = (
                cenario.get("codigo")
                or cenario.get("codigo_cenario")
                or cenario.get("cenario")
                or meta_diag.get("codigo_cenario")
                or meta_diag.get("cenario")
        )

        enquadramento_diag = (
                meta_diag.get("enquadramento")
                or cenario.get("enquadramento")
                or {}
        )

        cod_cred = (
                enquadramento_diag.get("tipo_credito_codigo")
                or enquadramento_diag.get("cod_cred")
                or enquadramento_diag.get("tipo_credito")
        )

        nat_bc_cred = (
                enquadramento_diag.get("base_credito_codigo")
                or enquadramento_diag.get("nat_bc_cred")
                or enquadramento_diag.get("cod_base_credito")
        )

        registro_id = (
            meta_diag.get("registro_id_c170")
            or meta_diag.get("registro_id_c100")
            or getattr(item, "registro_id_c170", None)
            or getattr(item, "registro_id_c100", None)
        )

        item_fiscal_consolidado_id = (
            meta_diag.get("item_fiscal_consolidado_id")
            or getattr(item, "id", None)
        )

        score_result = cache.score(item)

        impacto_estimado = calcular_impacto_estimado(
            vl_item=meta_diag.get("vl_item"),
            vl_desc=meta_diag.get("vl_desc"),
            vl_icms=meta_diag.get("vl_icms"),
            aliq_pis=enquadramento_diag.get("aliq_pis"),
            aliq_cofins=enquadramento_diag.get("aliq_cofins"),
        )

        status_cruzamento = (
            meta_diag.get("status_cruzamento")
            or getattr(item, "status_cruzamento", None)
        )

        registro_id_c100 = (
            meta_diag.get("registro_id_c100")
            or getattr(item, "registro_id_c100", None)
        )
        registro_id_c170 = (
            meta_diag.get("registro_id_c170")
            or getattr(item, "registro_id_c170", None)
        )

        meta_item = getattr(item, "meta", None) or {}

        tipo_normalizacao = (
                meta_diag.get("tipo_normalizacao")
                or meta_item.get("tipo_normalizacao")
                or getattr(item, "tipo_normalizacao", None)
        )

        tipo_corretiva_v2_meta = (
                meta_diag.get("tipo_corretiva_v2")
                or meta_item.get("tipo_corretiva_v2")
        )

        registro_id_ancora_meta = (
                meta_diag.get("registro_id_ancora")
                or meta_item.get("registro_id_ancora")
        )

        linha_ancora_meta = (
                meta_diag.get("linha_ancora")
                or meta_item.get("linha_ancora")
        )

        reg_ancora_meta = (
                meta_diag.get("reg_ancora")
                or meta_item.get("reg_ancora")
        )
        fundamento_legal = (
                meta_diag.get("fundamento_legal")
                or cenario.get("fundamento_legal")
                or []
        )

        justificativa_cenario = (
                meta_diag.get("justificativa")
                or cenario.get("justificativa")
                or []
        )

        if not tipo_normalizacao and status_cruzamento == "SO_ICMS":
            tipo_normalizacao = (
                "CONTRIB_SEM_C170"
                if registro_id_c100
                else "CONTRIB_SEM_C100_C170"
            )

        if tipo_normalizacao == "CONTRIB_SEM_C170":
            tipo_corretiva_v2 = "INSERIR_C170_EM_C100_EXISTENTE"
            registro_id_alvo = registro_id_c100
            linha_ref = (
                meta_diag.get("linha_c100")
                or getattr(item, "linha_c100", None)
            )

        elif tipo_normalizacao == "CONTRIB_SEM_C100_C170":
            tipo_corretiva_v2 = "INSERIR_C100_C170"
            registro_id_alvo = None
            linha_ref = None

        elif status_cruzamento == "MATCH" and registro_id_c170:
            tipo_corretiva_v2 = "PATCH_C170_EXISTENTE"
            registro_id_alvo = registro_id_c170
            linha_ref = (
                meta_diag.get("linha_c170")
                or getattr(item, "linha_c170", None)
            )

        else:
            tipo_corretiva_v2 = "NAO_SUPORTADO"
            registro_id_alvo = None
            linha_ref = None

        # Se o materializar já definiu a corretiva/âncora, ele é a fonte principal.
        if tipo_corretiva_v2_meta:
            tipo_corretiva_v2 = tipo_corretiva_v2_meta

        if registro_id_ancora_meta is not None:
            registro_id_alvo = registro_id_ancora_meta

        if linha_ancora_meta is not None:
            linha_ref = linha_ancora_meta

        stats[f"tipo_corretiva:{tipo_corretiva_v2}"] += 1
        stats[f"status:{status_cruzamento}"] += 1

        cst_pis_destino = enquadramento_diag.get("cst_pis_destino")
        cst_cofins_destino = enquadramento_diag.get("cst_cofins_destino")

        aliq_pis = enquadramento_diag.get("aliq_pis")
        aliq_cofins = enquadramento_diag.get("aliq_cofins")

        meta_fiscal = {
            "codigo_cenario": codigo_cenario,
            "cenario": codigo_cenario,
            "enquadramento": enquadramento_diag,
            "cod_cred": cod_cred,
            "tipo_credito_codigo": cod_cred,
            "nat_bc_cred": nat_bc_cred,
            "base_credito_codigo": nat_bc_cred,
            "cod_base_credito": nat_bc_cred,
            "contexto_credito": codigo_cenario,
            "natureza_credito_m": nat_bc_cred,

            "cst_pis_destino": cst_pis_destino,
            "cst_cofins_destino": cst_cofins_destino,

            "aliq_pis": aliq_pis,
            "aliq_cofins": aliq_cofins,

            "fundamento_legal": fundamento_legal,
            "justificativa_cenario": justificativa_cenario,
        }
        meta_item = getattr(item, "meta", None) or {}

        novos_apontamentos.append(
            EfdApontamento(
                versao_id=int(versao_id),
                registro_id=registro_id,
                item_fiscal_consolidado_id=item_fiscal_consolidado_id,
                tipo=diag["tipo"],
                codigo=diag["codigo"],
                descricao=diag["descricao"],
                impacto_financeiro=impacto_estimado,
                prioridade=diag.get("prioridade"),
                meta_json=json_safe({
                    **meta_diag,
                    **meta_fiscal,
                    "meta_fiscal": meta_fiscal,
                    "item_fiscal_consolidado_id": item_fiscal_consolidado_id,
                    "registro_id": registro_id,
                    "origem": meta_diag.get("origem") or meta_item.get("origem") or "CONTEXTO_FISCAL",

                    "nf_icms_base_id": meta_diag.get("nf_icms_base_id") or meta_item.get("nf_icms_base_id"),
                    "nf_icms_item_id": meta_diag.get("nf_icms_item_id") or meta_item.get("nf_icms_item_id"),

                    "score_fiscal": score_result.score,
                    "confianca_fiscal": score_result.confianca,
                    "score_justificativas": score_result.justificativas,

                    # compatível com endpoint/front
                    "score": score_result.score,
                    "bucket": score_result.confianca,

                    "status_cruzamento": status_cruzamento,
                    "tipo_corretiva_v2": tipo_corretiva_v2,
                    "registro_id_c100": registro_id_c100,
                    "registro_id_c170": registro_id_c170,

                    "reg_ancora": (
                        reg_ancora_meta
                        or (
                            "C170"
                            if tipo_corretiva_v2 == "PATCH_C170_EXISTENTE"
                            else "C100"
                        )
                    ),
                    "contrib_tem_c100": bool(registro_id_c100),
                    "registro_id_ancora": registro_id_alvo,
                    "linha_ancora": linha_ref,

                    "tipo_normalizacao": tipo_normalizacao,
                }),
            )
        )

    logger.info(
        "## [GERAR_AP v%s] loop fim | total_diag=%s | novos=%s | stats=%s | tempo=%.3fs ##",
        versao_id,
        total_diag,
        len(novos_apontamentos),
        dict(stats),
        time.perf_counter() - t0,
    )

    # --------------------------------------------------
    # 6) Bulk insert
    # --------------------------------------------------
    if novos_apontamentos:
        db.bulk_save_objects(novos_apontamentos)
        db.flush()

    cache_stats = cache.stats()

    logger.info(
        "## [GERAR_AP v%s] fim | total_itens=%s | total_diag=%s | "
        "cache_classif=%s | cache_cenario=%s | cache_enq=%s | cache_score=%s | tempo=%.3fs ##",
        versao_id,
        total_itens,
        total_diag,
        cache_stats["cache_classif"],
        cache_stats["cache_cenario"],
        cache_stats["cache_enquadramento"],
        cache_stats["cache_score"],
        time.perf_counter() - t0,
    )

    db.commit()

    return {
        "ok": True,
        "versao_id": int(versao_id),
        "total_itens": int(total_itens),
        "total_diagnosticos": int(total_diag),
        "apontamentos_persistidos": int(total_diag),
        **cache_stats,
        "stats": dict(stats),
    }