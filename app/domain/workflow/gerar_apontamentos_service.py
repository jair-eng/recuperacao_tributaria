from sqlalchemy.orm import Session

from app.db.models import ItemFiscalConsolidado, EfdApontamento
from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd
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
    empresa_id = itens[0].empresa_id if itens else None
    periodo = itens[0].periodo if itens else None

    contexto_gap_ecd = None

    if empresa_id and periodo:
        contexto_gap_ecd = montar_contexto_gap_ecd_efd(
            db=db,
            empresa_id=empresa_id,
            versao_id=versao_id,
            periodo=periodo,
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
        enquadramento = cenario.get("enquadramento") or {}
        nat_bc_cred = enquadramento.get("nat_bc_cred")

        if contexto_gap_ecd and nat_bc_cred:
            meta["ecd_gap"] = (
                contexto_gap_ecd.get("por_natureza", {}).get(str(nat_bc_cred).zfill(2))
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

        enquadramento = meta.get("enquadramento") or {}
        impacto_estimado = calcular_impacto_estimado(
            vl_item=meta.get("vl_item"),
            vl_desc=meta.get("vl_desc"),
            vl_icms=meta.get("vl_icms"),
            aliq_pis=enquadramento.get("aliq_pis"),
            aliq_cofins=enquadramento.get("aliq_cofins"),
        )
        status_cruzamento = (
                meta.get("status_cruzamento")
                or getattr(item, "status_cruzamento", None)
        )

        registro_id_c100 = meta.get("registro_id_c100") or getattr(item, "registro_id_c100", None)
        registro_id_c170 = meta.get("registro_id_c170") or getattr(item, "registro_id_c170", None)

        tipo_normalizacao = (
                meta.get("tipo_normalizacao")
                or getattr(item, "tipo_normalizacao", None)
        )

        if tipo_normalizacao == "CONTRIB_SEM_C170":
            tipo_corretiva_v2 = "INSERIR_C170_EM_C100_EXISTENTE"
            registro_id_alvo = registro_id_c100
            linha_ref = meta.get("linha_c100") or getattr(item, "linha_c100", None)

        elif tipo_normalizacao == "CONTRIB_SEM_C100_C170":
            tipo_corretiva_v2 = "INSERIR_C100_C170"
            registro_id_alvo = None
            linha_ref = None

        elif status_cruzamento == "MATCH" and registro_id_c170:
            tipo_corretiva_v2 = "PATCH_C170_EXISTENTE"
            registro_id_alvo = registro_id_c170
            linha_ref = (
                    meta.get("linha_c170")
                    or getattr(item, "linha_c170", None)
            )

        else:
            tipo_corretiva_v2 = "NAO_SUPORTADO"
            registro_id_alvo = None
            linha_ref = None

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
                "origem": meta.get("origem") or "CONTEXTO_FISCAL",
                "score_fiscal": score_result.score,
                "confianca_fiscal": score_result.confianca,
                "score_justificativas": score_result.justificativas,
                # compatível com endpoint/front
                "score": score_result.score,
                "bucket": score_result.confianca,
                "cenario": meta.get("codigo_cenario"),

                "status_cruzamento": status_cruzamento,
                "tipo_corretiva_v2": tipo_corretiva_v2,
                "registro_id_c100": registro_id_c100,
                "registro_id_c170": registro_id_c170,

                "reg_ancora": (
                "C170" if tipo_corretiva_v2 == "PATCH_C170_EXISTENTE" else "C100"
            ),
                "contrib_tem_c100": bool(registro_id_c100),
                "registro_id_ancora": registro_id_alvo,
                "linha_ancora": linha_ref,

                "tipo_normalizacao": tipo_normalizacao,

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