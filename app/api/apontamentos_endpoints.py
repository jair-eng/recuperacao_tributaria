from __future__ import annotations

from app.db.models.efd_revisao import EfdRevisao
from typing import Optional, Literal, List, Set
from fastapi import APIRouter, Depends, Query
from app.db.session import get_db
from app.db.models import EfdVersao, EfdArquivo
from app.db.models import EfdApontamento, EfdRegistro
from sqlalchemy.orm import Session
from sqlalchemy import update, or_ , delete, case , Integer, select, func, exists
from pydantic import BaseModel
import time
from typing import Any, Dict
from fastapi import HTTPException, status

from app.domain.fiscal.diagnostico.consolidacao import consolidar_apontamentos
from app.domain.workflow.preparar_revisao_service import preparar_revisao
from app.legacy_service.workflow_service import WorkflowService
from app.schemas.workflow import ApontamentosBatchPayload
from app.legacy_service.apontamento_service import ApontamentoService

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflow", tags=["Apontamentos"])


class ReprocessarPayload(BaseModel):
    preservar_resolvidos: bool = True
    motivo: Optional[str] = None
    aplicar_revisoes: bool = True

@router.post("/versao/{versao_id}/reprocessar", status_code=status.HTTP_200_OK)
def reprocessar_apontamentos(
    versao_id: int,
    payload: ReprocessarPayload = ReprocessarPayload(),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    versao = db.query(EfdVersao).filter(EfdVersao.id == versao_id).first()
    print(
        f"[REPROCESSAR_V2] iniciando reprocessamento de apontamentos | Versao={ versao}",
        flush=True,
    )

    if not versao:
        raise HTTPException(status_code=404, detail="Versão não encontrada")

    if versao.status == "EXPORTADA":
        raise HTTPException(
            status_code=400,
            detail="Versão EXPORTADA é congelada.",
        )

    try:
        print("[DBG REPROCESSAR] antes preparar_revisao", flush=True)
        resultado = preparar_revisao(
            db=db,
            versao_id=versao_id,
        )


        print(
            "[DBG REPROCESSAR] depois preparar_revisao",
            resultado,
            flush=True,
        )

        return {
            "ok": True,
            "versao_id": versao_id,
            "status": versao.status,
            "message": "Reprocessamento concluído pelo pipeline novo.",
            "mensagens": [
                "Mesa fiscal materializada.",
                "Apontamentos recriados pelo pipeline novo.",
            ],
            "relatorio": resultado,
        }


    except Exception as e:

        import traceback

        print("[DBG REPROCESSAR][ERRO]", repr(e), flush=True)

        traceback.print_exc()

        db.rollback()

        raise HTTPException(

            status_code=500,

            detail=f"Erro ao reprocessar pelo pipeline novo: {e}",

        )

@router.get(
    "/versao/{versao_id}/apontamentos",
    status_code=status.HTTP_200_OK,

)
def listar_apontamentos(
        versao_id: int,
        db: Session = Depends(get_db),
        tipo: Optional[Literal["ERRO", "OPORTUNIDADE"]] = Query(default=None),
        resolvido: Optional[bool] = Query(default=None),
        bucket: Optional[Literal["ALTA_CHANCE", "REVISAR", "BAIXA"]] = Query(default=None),
        cenario: Optional[Literal["SEM_RESSARC", "COM_RESSARC"]] = Query(default=None),
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
) -> Dict[str, Any]:

    """
    Lista apontamentos da versão.
    Filtros:
      - tipo: ERRO | OPORTUNIDADE
      - resolvido: true | false
    Paginação:
      - limit, offset
    Retorna também dados do registro associado (linha/reg).
    """
    try:
        tem_revisao_sq = exists().where(
            (EfdRevisao.versao_origem_id == versao_id) &
            (EfdRevisao.registro_id == EfdApontamento.registro_id)
        )

        last_revisao_id_sq = (
            select(EfdRevisao.id)
            .where(
                (EfdRevisao.versao_origem_id == versao_id) &
                (EfdRevisao.registro_id == EfdApontamento.registro_id)
            )
            .order_by(EfdRevisao.id.desc())
            .limit(1)
            .scalar_subquery()
        )

        last_versao_revisada_id_sq = (
            select(EfdRevisao.versao_revisada_id)
            .where(
                (EfdRevisao.versao_origem_id == versao_id) &
                (EfdRevisao.registro_id == EfdApontamento.registro_id)
            )
            .order_by(EfdRevisao.id.desc())
            .limit(1)
            .scalar_subquery()
        )

        q = (
            db.query(
                EfdApontamento,
                EfdRegistro,
                tem_revisao_sq.label("tem_revisao"),
                last_revisao_id_sq.label("revisao_id"),
                last_versao_revisada_id_sq.label("versao_revisada_id"),
            )
            .outerjoin(EfdRegistro, EfdRegistro.id == EfdApontamento.registro_id)
            .filter(EfdApontamento.versao_id == versao_id)
        )

        if tipo is not None:
            q = q.filter(EfdApontamento.tipo == tipo)

        if resolvido is not None:
            if resolvido is True:
                q = q.filter(EfdApontamento.resolvido.is_(True))
            else:
                q = q.filter(or_(EfdApontamento.resolvido.is_(False), EfdApontamento.resolvido.is_(None)))

        total = q.count()

        # -------- filtros via meta_json --------
        if bucket is not None:
            q = q.filter(
                func.JSON_UNQUOTE(
                    func.JSON_EXTRACT(EfdApontamento.meta_json, "$.bucket")
                ) == bucket
            )

        if cenario is not None:
            q = q.filter(
                func.JSON_UNQUOTE(
                    func.JSON_EXTRACT(EfdApontamento.meta_json, "$.cenario")
                ) == cenario
            )


        prioridade_ordem = case(
            (EfdApontamento.prioridade == "ALTA", 1),
            (EfdApontamento.prioridade == "MEDIA", 2),
            (EfdApontamento.prioridade == "BAIXA", 3),
            else_=4,
        )

        # substitui NULLS LAST
        impacto_nulls_last = case(
            (EfdApontamento.impacto_financeiro.is_(None), 1),
            else_=0,
        )

        # score no meta_json (NULLs last)
        score_expr = func.JSON_UNQUOTE(
            func.JSON_EXTRACT(EfdApontamento.meta_json, "$.score")
        )
        score_int = func.CAST(score_expr, Integer)

        score_nulls_last = case(
            (score_expr.is_(None), 1),
            else_=0,
        )


        rows = (
            q.order_by(
                EfdApontamento.resolvido.asc(),  # pendentes primeiro
                prioridade_ordem.asc(),  # ALTA -> MEDIA -> BAIXA
                score_nulls_last.asc(),  # score NULL por último
                score_int.desc(),  # score maior primeiro
                impacto_nulls_last.asc(),  # NULL por último
                EfdApontamento.impacto_financeiro.desc(),  # impacto maior primeiro
                EfdRegistro.linha.asc(),  # linha crescente
                EfdApontamento.id.desc(),  # desempate
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        itens: List[Dict[str, Any]] = []
        for a, r, tem_revisao, revisao_id, versao_revisada_id in rows:
            itens.append(
                {
                    "id": int(a.id),
                    "versao_id": int(a.versao_id),
                    "registro_id": int(a.registro_id) if a.registro_id is not None else None,
                    "item_fiscal_consolidado_id": (
                        int(a.item_fiscal_consolidado_id)
                        if getattr(a, "item_fiscal_consolidado_id", None) is not None
                        else None
                    ),
                    "tipo": a.tipo,
                    "codigo": a.codigo,
                    "descricao": a.descricao,
                    "impacto_financeiro": float(a.impacto_financeiro) if a.impacto_financeiro is not None else None,
                    "prioridade": getattr(a, "prioridade", None),
                    "resolvido": bool(a.resolvido) if a.resolvido is not None else False,
                    # ✅ expose meta completo pro front
                    "meta": dict(a.meta_json or {}),
                    "score": (a.meta_json or {}).get("score") if getattr(a, "meta_json", None) else None,
                    "bucket": (a.meta_json or {}).get("bucket") if getattr(a, "meta_json", None) else None,
                    "cenario": (a.meta_json or {}).get("cenario") if getattr(a, "meta_json", None) else None,
                    "registro": (
                        {"linha": int(r.linha), "reg": str(r.reg)}
                        if r is not None
                        else None
                    ),
                    "tem_revisao": bool(tem_revisao),
                    "revisao_id": int(revisao_id) if revisao_id is not None else None,
                    "versao_revisada_id": int(versao_revisada_id) if versao_revisada_id is not None else None,
                }
            )
        items_consolidados = consolidar_apontamentos(
            itens,
            campos_chave=[
                "codigo",
                "cenario",
            ],
            campos_soma=[
                "impacto_financeiro",
            ],
        )

        return {
            "versao_id": versao_id,
            "total": int(total),
            "limit": int(limit),
            "offset": int(offset),
            "items": itens,
            "items_consolidados": items_consolidados,
            "total_consolidado": len(items_consolidados),
        }


    except Exception as e:

        raise HTTPException(status_code=500, detail=f"Erro interno ao listar apontamentos: {e}")



@router.patch(
    "/apontamento/{apontamento_id}/resolver",
    status_code=status.HTTP_200_OK,
)
def resolver_apontamento(
    apontamento_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Marca um apontamento como resolvido.
    """
    ap = (
        db.query(EfdApontamento)
        .filter(EfdApontamento.id == apontamento_id)
        .first()
    )

    if not ap:
        raise HTTPException(status_code=404, detail="Apontamento não encontrado")

    # o context manager cuida de commit/rollback

    ap.resolvido = True
    db.add(ap)
    db.flush()

    return {
        "id": int(ap.id),
        "versao_id": int(ap.versao_id),
        "resolvido": True,
        "status": "Resolvido",
    }



@router.patch(
    "/apontamento/{apontamento_id}/reabrir",
    status_code=status.HTTP_200_OK,
)
def reabrir_apontamento(
        apontamento_id: int,
        db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Marca um apontamento como NÃO resolvido (reabre).
    """
    try:
        ap = db.query(EfdApontamento).filter(EfdApontamento.id == apontamento_id).first()
        if not ap:
            raise HTTPException(status_code=404, detail="Apontamento não encontrado")

        ap.resolvido = False
        db.add(ap)
        db.commit()

        return {
            "id": int(ap.id),
            "versao_id": int(ap.versao_id),
            "resolvido": False,
            "status": "Pendente",
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/apontamento/batch", status_code=status.HTTP_200_OK)
def aplicar_apontamentos_em_lote(
    payload: ApontamentosBatchPayload,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Aplica resolver/reabrir em lote (performático) e retorna auditoria do que foi aplicado.
    Reabrir ganha se um ID estiver em ambos.
    """
    try:
        versao_id = int(payload.versao_id)

        to_resolver: Set[int] = set(map(int, payload.to_resolver or []))
        to_reabrir: Set[int] = set(map(int, payload.to_reabrir or []))

        # reabrir ganha
        to_resolver -= to_reabrir

        requested = len(to_resolver) + len(to_reabrir)

        updated_resolver = 0
        updated_reabrir = 0

        if to_resolver:
            res = db.execute(
                update(EfdApontamento)
                .where(
                    EfdApontamento.versao_id == versao_id,
                    EfdApontamento.id.in_(to_resolver),
                )
                .values(resolvido=True)
            )
            updated_resolver = int(res.rowcount or 0)

        if to_reabrir:
            res = db.execute(
                update(EfdApontamento)
                .where(
                    EfdApontamento.versao_id == versao_id,
                    EfdApontamento.id.in_(to_reabrir),
                )
                .values(resolvido=False)
            )
            updated_reabrir = int(res.rowcount or 0)

        db.commit()

        pendentes = db.execute(
            select(func.count())
            .select_from(EfdApontamento)
            .where(
                EfdApontamento.versao_id == versao_id,
                (EfdApontamento.resolvido.is_(False) | EfdApontamento.resolvido.is_(None)),
            )
        ).scalar_one()

        updated_total = updated_resolver + updated_reabrir

        return {
            "versao_id": versao_id,
            "requested": requested,
            "to_resolver": len(to_resolver),
            "to_reabrir": len(to_reabrir),
            "updated_resolver": updated_resolver,
            "updated_reabrir": updated_reabrir,
            "updated_total": updated_total,
            "nao_encontrados_ou_outra_versao": int(requested - updated_total),
            "pendentes_restantes": int(pendentes),
            "status": "OK",
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))



@router.patch("/versao/{versao_id}/resolver_todos", status_code=200)
def resolver_todos_pendentes(versao_id: int, db: Session = Depends(get_db)):

    with db.begin():
        r = ApontamentoService.resolver_todos_pendentes_por_versao(db, versao_id=int(versao_id))

    return {
        "versao_id": r.versao_id,
        "updated_total": r.updated_total,
        "pendentes_restantes": r.pendentes_restantes,
        "status": "OK",
    }