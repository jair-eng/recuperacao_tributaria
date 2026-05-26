from sqlalchemy.orm import Session

from app.db.models import ItemFiscalConsolidado, EfdApontamento
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.cenarios.avaliador_cenarios import avaliar_cenarios
from app.domain.fiscal.cenarios.cenario_posto_cred_normal import (
    cenario_posto_credito_normal,)
from app.domain.fiscal.cenarios.cenario_enriquecimento import (
    enriquecer_cenario_com_enquadramento,)
from app.domain.fiscal.diagnostico.diag_credito_nao_aproveitado import (
    diagnosticar_credito_nao_aproveitado,)
from app.domain.fiscal.meta.meta_item_fiscal import (
    meta_from_item_fiscal,
)
from app.domain.fiscal.score_fiscal_services import calcular_score_fiscal_contabil
from app.utils.json_utils import json_safe
from app.utils.numbers import calcular_impacto_estimado


def gerar_apontamentos_por_contexto(
    *,
    db: Session,
    versao_id: int,
):
    print(
        "[GERAR_APONTAMENTOS] inicio | versao_id=",
        versao_id,
        flush=True,
    )

    itens = (
        db.query(ItemFiscalConsolidado)
        .filter(ItemFiscalConsolidado.versao_id == versao_id)
        .all()
    )

    print(
        "[GERAR_APONTAMENTOS] itens=",
        len(itens),
        flush=True,
    )
    catalogo = carregar_catalogo_fiscal(db)
    total_diag = 0

    db.query(EfdApontamento).filter(
        EfdApontamento.versao_id == versao_id,
        EfdApontamento.codigo.like("%_V2"),
    ).delete(synchronize_session=False)
    db.flush()

    for item in itens:

        meta = meta_from_item_fiscal(item)
        classificacao = classificar_item_fiscal(
            meta=meta,
            catalogo=catalogo,
        )
        cenario = avaliar_cenarios(
            meta,
            classificacao,
        )

        if not cenario:
            continue
        cenario = enriquecer_cenario_com_enquadramento(
            db,
            cenario,
        )
        diag = diagnosticar_credito_nao_aproveitado(
            meta=meta,
            classificacao=classificacao,
            cenario=cenario,
        )

        if not diag:
            continue

        total_diag += 1

        meta = diag.get("meta") or {}

        registro_id = (
                meta.get("registro_id_c170")
                or meta.get("registro_id_c100")
                or getattr(item, "registro_id_c170", None)
                or getattr(item, "registro_id_c100", None)
        )

        item_fiscal_consolidado_id = (
                meta.get("item_fiscal_consolidado_id")
                or getattr(item, "id", None)
        )

        score_result = calcular_score_fiscal_contabil(item)

        print(
            "[SCORE_FISCAL]"
            f" item={item.cod_item}"
            f" score={score_result.score}"
            f" confianca={score_result.confianca}"
            f" dominio={item.dominio}"
            f" conta={item.ecd_conta_nome}"
            f" justificativas={score_result.justificativas}",
            flush=True,
        )
        enquadramento = meta.get("enquadramento") or {}
        impacto_estimado = calcular_impacto_estimado(
            vl_item=meta.get("vl_item"),
            vl_desc=meta.get("vl_desc"),
            vl_icms=meta.get("vl_icms"),
            aliq_pis=enquadramento.get("aliq_pis"),
            aliq_cofins=enquadramento.get("aliq_cofins"),
        )

        ap = EfdApontamento(
            versao_id=versao_id,
            registro_id=registro_id,
            item_fiscal_consolidado_id=item_fiscal_consolidado_id,
            tipo=diag["tipo"],
            codigo=diag["codigo"],
            descricao=diag["descricao"],
            impacto_financeiro=impacto_estimado,
            prioridade=diag.get("prioridade"),
            meta_json=json_safe({
                **meta,
                "item_fiscal_consolidado_id": item_fiscal_consolidado_id,
                "registro_id": registro_id,
                "registro_id_c100": meta.get("registro_id_c100") or getattr(item, "registro_id_c100", None),
                "registro_id_c170": meta.get("registro_id_c170") or getattr(item, "registro_id_c170", None),
                "status_cruzamento": meta.get("status_cruzamento") or getattr(item, "status_cruzamento", None),
                "origem": meta.get("origem") or "CONTEXTO_FISCAL",
                "score_fiscal": score_result.score,
                "confianca_fiscal": score_result.confianca,
                "score_justificativas": score_result.justificativas,
                # compatível com endpoint/front
                "score": score_result.score,
                "bucket": score_result.confianca,
                "cenario": meta.get("codigo_cenario"),
            }),
        )
        db.add(ap)

    print(
        "[GERAR_APONTAMENTOS] final | total_diag=",
        total_diag,
        flush=True,
    )
    db.flush()
    db.commit()

    return {
        "ok": True,
        "versao_id": versao_id,
        "total_itens": len(itens),
        "total_diagnosticos": total_diag,
        "apontamentos_persistidos": total_diag,
    }