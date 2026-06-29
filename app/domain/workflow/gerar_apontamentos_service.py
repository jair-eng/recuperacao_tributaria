from sqlalchemy.orm import Session

from app.db.models import ItemFiscalConsolidado, EfdApontamento
from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.avaliador_cenarios import avaliar_cenarios
from app.domain.fiscal.cenarios.cenario_enriquecimento import (
    enriquecer_cenario_com_enquadramento,)
from app.domain.fiscal.diagnostico.diag_credito_nao_aproveitado import (
    diagnosticar_credito_nao_aproveitado,)
from app.domain.fiscal.meta.meta_item_fiscal import (
    meta_from_item_fiscal,
)
from app.domain.fiscal.score_fiscal_services import calcular_score_fiscal_contabil
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

        enquadramento_diag = meta_diag.get("enquadramento") or {}

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

        tipo_normalizacao = (
            meta_diag.get("tipo_normalizacao")
            or getattr(item, "tipo_normalizacao", None)
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

        stats[f"tipo_corretiva:{tipo_corretiva_v2}"] += 1
        stats[f"status:{status_cruzamento}"] += 1

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
                    "item_fiscal_consolidado_id": item_fiscal_consolidado_id,
                    "registro_id": registro_id,
                    "origem": meta_diag.get("origem") or "CONTEXTO_FISCAL",
                    "score_fiscal": score_result.score,
                    "confianca_fiscal": score_result.confianca,
                    "score_justificativas": score_result.justificativas,

                    # compatível com endpoint/front
                    "score": score_result.score,
                    "bucket": score_result.confianca,
                    "cenario": meta_diag.get("codigo_cenario"),

                    "status_cruzamento": status_cruzamento,
                    "tipo_corretiva_v2": tipo_corretiva_v2,
                    "registro_id_c100": registro_id_c100,
                    "registro_id_c170": registro_id_c170,

                    "reg_ancora": (
                        "C170"
                        if tipo_corretiva_v2 == "PATCH_C170_EXISTENTE"
                        else "C100"
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
        cache_stats = cache.stats()
        db.flush()

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