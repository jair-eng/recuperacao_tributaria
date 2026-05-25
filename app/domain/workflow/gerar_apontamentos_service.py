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
from app.utils.json_utils import json_safe


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

        ap = EfdApontamento(
            versao_id=versao_id,
            registro_id=diag["meta"].get("registro_id_c170")
                        or diag["meta"].get("registro_id_c100")
                        or item.registro_id_c170
                        or item.registro_id_c100,
            tipo=diag.get("tipo", "OPORTUNIDADE"),
            codigo=diag.get("codigo"),
            descricao=diag.get("descricao"),
            impacto_financeiro=diag.get("impacto_financeiro"),
            prioridade=diag.get("prioridade"),
            resolvido=False,
            meta_json=json_safe(diag.get("meta") or {}),
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