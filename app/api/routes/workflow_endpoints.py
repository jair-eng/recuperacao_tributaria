from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.models.efd_revisao import EfdRevisao
from app.Legacy.fiscal.regras.Diagnostico.registry import get_regra_por_codigo
from app.services.revisao_reset_service import limpar_revisoes_automaticas_da_versao
from app.legacy_service.revision_service import materializar_versao_revisada
from app.legacy_service.workflow_service import WorkflowService
from app.db.session import get_db
from app.db.models import EfdVersao, EfdApontamento
from app.schemas.workflow import RevisaoFiscal, ConfirmarRevisaoBody
from sqlalchemy import or_, func
from typing import Optional, Any, Dict, List, Tuple
from fastapi import Body

import logging
logger = logging.getLogger(__name__)


router = APIRouter(prefix="/workflow", tags=["Workflow Fiscal"])

def _exec(db: Session, versao_id: int, acao: str) -> dict:
    try:
        if acao == "revisar":
            WorkflowService.iniciar_revisao(versao_id, db)
            novo_status = "EM_REVISAO"
        elif acao == "validar":
            WorkflowService.validar_versao(versao_id, db)
            novo_status = "VALIDADA"
        else:
            raise HTTPException(status_code=400, detail="Ação inválida")

        db.commit()
        return {"versao_id": versao_id, "acao": acao, "status": novo_status}

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/versao/{versao_id}/revisar", status_code=status.HTTP_200_OK)
def iniciar_revisao(versao_id: int, db: Session = Depends(get_db)):
    versao = db.get(EfdVersao, versao_id)
    if not versao:
        raise HTTPException(status_code=404, detail="Versão não encontrada")

    if versao.status != "GERADA":
        raise HTTPException(status_code=400, detail="Apenas versões GERADAS podem entrar em revisão")

    versao.status = "EM_REVISAO"
    db.add(versao)
    db.commit()

    return {"versao_id": versao_id, "status": versao.status}



@router.post("/versao/{versao_id}/confirmar-revisao", status_code=status.HTTP_200_OK)
def confirmar_revisao(
    versao_id: int,
    body: Optional[ConfirmarRevisaoBody] = Body(default=None),
    db: Session = Depends(get_db),
):
    """
    Confirma a revisão de uma versão:

    - aplica resolvido/reabrir quando houver payload;
    - bloqueia a confirmação enquanto houver ERRO pendente;
    - gera revisões automáticas para apontamentos resolvidos;
    - salva as revisões como pendentes de materialização;
    - materializa a versão revisada;
    - vincula a versão revisada à versão de origem;
    - confirma a transação.
    """
    payload = body.payload if body else None

    relatorio_confirmacao: Dict[str, Any] = {
        "versao_id": int(versao_id),
        "apontamentos_resolvidos": 0,
        "regras_processadas": 0,
        "revisoes_automaticas_geradas": 0,
        "versao_revisada_id": None,
    }

    mensagens: List[str] = []

    try:
        versao = (
            db.query(EfdVersao)
            .filter(EfdVersao.id == int(versao_id))
            .first()
        )

        if not versao:
            raise HTTPException(
                status_code=404,
                detail="Versão não encontrada.",
            )

        # A versão já foi materializada anteriormente.
        if getattr(versao, "versao_revisada_id", None):
            return {
                "ok": True,
                "versao_id": int(versao_id),
                "status": str(versao.status),
                "pendentes_erro": 0,
                "versao_revisada_id": int(
                    versao.versao_revisada_id
                ),
                "mensagens": [
                    "A versão revisada já havia sido materializada."
                ],
                "relatorio": {
                    **relatorio_confirmacao,
                    "versao_revisada_id": int(
                        versao.versao_revisada_id
                    ),
                },
            }

        if str(getattr(versao, "status", "")) != "EM_REVISAO":
            raise HTTPException(
                status_code=400,
                detail=(
                    "Versão precisa estar EM_REVISAO para confirmar. "
                    f"Status atual: {versao.status}"
                ),
            )

        # --------------------------------------------------
        # 1) Compatibilidade: aplica resolver/reabrir
        # --------------------------------------------------
        if payload is not None:
            to_resolver = {
                int(apontamento_id)
                for apontamento_id in (payload.to_resolver or [])
            }

            to_reabrir = {
                int(apontamento_id)
                for apontamento_id in (payload.to_reabrir or [])
            }

            alteracoes = getattr(payload, "alteracoes", None) or []

            for alteracao in alteracoes:
                apontamento_id = int(alteracao.apontamento_id)

                if bool(alteracao.resolvido):
                    to_resolver.add(apontamento_id)
                else:
                    to_reabrir.add(apontamento_id)

            # Reabrir prevalece caso o mesmo ID apareça nas duas listas.
            to_resolver -= to_reabrir

            if to_resolver:
                (
                    db.query(EfdApontamento)
                    .filter(
                        EfdApontamento.versao_id == int(versao_id),
                        EfdApontamento.id.in_(list(to_resolver)),
                    )
                    .update(
                        {
                            EfdApontamento.resolvido: True,
                        },
                        synchronize_session=False,
                    )
                )

            if to_reabrir:
                (
                    db.query(EfdApontamento)
                    .filter(
                        EfdApontamento.versao_id == int(versao_id),
                        EfdApontamento.id.in_(list(to_reabrir)),
                    )
                    .update(
                        {
                            EfdApontamento.resolvido: False,
                        },
                        synchronize_session=False,
                    )
                )

            db.flush()

        # --------------------------------------------------
        # 2) Bloqueia somente ERRO pendente
        # --------------------------------------------------
        pendentes_erro = (
            db.query(func.count(EfdApontamento.id))
            .filter(
                EfdApontamento.versao_id == int(versao_id),
                EfdApontamento.tipo == "ERRO",
                or_(
                    EfdApontamento.resolvido.is_(False),
                    EfdApontamento.resolvido.is_(None),
                ),
            )
            .scalar()
            or 0
        )

        if int(pendentes_erro) > 0:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Ainda existem {int(pendentes_erro)} "
                    "apontamentos de ERRO pendentes."
                ),
            )

        # --------------------------------------------------
        # 3) Busca apontamentos resolvidos
        # --------------------------------------------------
        apontamentos_resolvidos: List[EfdApontamento] = (
            db.query(EfdApontamento)
            .filter(
                EfdApontamento.versao_id == int(versao_id),
                EfdApontamento.resolvido.is_(True),
            )
            .order_by(EfdApontamento.id.asc())
            .all()
        )

        relatorio_confirmacao["apontamentos_resolvidos"] = len(
            apontamentos_resolvidos
        )

        # Guarda o apontamento original junto da revisão produzida.
        revisoes_para_salvar: List[
            Tuple[int, "RevisaoFiscal", str]
        ] = []

        ja_processadas: set[str] = set()
        total_regras_processadas = 0
        total_revisoes_automaticas = 0

        # --------------------------------------------------
        # 4) Executa os geradores de revisão
        # --------------------------------------------------
        for apontamento in apontamentos_resolvidos:
            codigo = str(
                apontamento.codigo or ""
            ).strip().upper()

            if not codigo:
                continue

            # Mantém o comportamento anterior:
            # cada código de regra é processado uma vez.
            if codigo in ja_processadas:
                continue

            ja_processadas.add(codigo)

            regra = get_regra_por_codigo(codigo)

            if not regra:
                logger.warning(
                    "[CONFIRMAR_REVISAO] regra não encontrada "
                    "| versao=%s codigo=%s apontamento=%s",
                    versao_id,
                    codigo,
                    apontamento.id,
                )
                continue

            total_regras_processadas += 1

            ctx: Dict[str, Any] = {
                "db": db,
                "versao": versao,
                "apontamento": apontamento,
            }

            # Mantido por compatibilidade com as regras existentes.
            # Em uma próxima refatoração, esse método pode receber
            # um nome genérico como gerar_revisoes().
            gerador = getattr(
                regra,
                "gerar_revisoes_exp_ressarc_v1",
                None,
            )

            if not callable(gerador):
                logger.debug(
                    "[CONFIRMAR_REVISAO] regra sem gerador automático "
                    "| versao=%s codigo=%s apontamento=%s",
                    versao_id,
                    codigo,
                    apontamento.id,
                )
                continue

            # Remove revisões automáticas anteriores deste mesmo
            # apontamento antes de recriá-las.
            (
                db.query(EfdRevisao)
                .filter(
                    EfdRevisao.versao_origem_id == int(versao.id),
                    EfdRevisao.motivo_codigo == codigo,
                    EfdRevisao.apontamento_id == int(
                        apontamento.id
                    ),
                    EfdRevisao.versao_revisada_id.is_(None),
                )
                .delete(synchronize_session=False)
            )

            novas_revisoes = gerador(ctx) or []

            total_revisoes_automaticas += len(
                novas_revisoes
            )

            for revisao in novas_revisoes:
                revisoes_para_salvar.append(
                    (
                        int(apontamento.id),
                        revisao,
                        codigo,
                    )
                )

        relatorio_confirmacao["regras_processadas"] = int(
            total_regras_processadas
        )

        relatorio_confirmacao[
            "revisoes_automaticas_geradas"
        ] = int(total_revisoes_automaticas)

        # --------------------------------------------------
        # 5) Persiste revisões pendentes
        # --------------------------------------------------
        for apontamento_id, revisao, codigo_regra in revisoes_para_salvar:
            operacao = str(
                getattr(revisao, "operacao", "") or ""
            ).strip()

            if not operacao:
                logger.warning(
                    "[CONFIRMAR_REVISAO] revisão ignorada sem operação "
                    "| versao=%s codigo=%s apontamento=%s",
                    versao_id,
                    codigo_regra,
                    apontamento_id,
                )
                continue

            revisao_json = {
                "linha_referencia": getattr(
                    revisao,
                    "linha_referencia",
                    None,
                ),
                "linha_antes": getattr(
                    revisao,
                    "linha_antes",
                    None,
                ),
                "linha_hash": getattr(
                    revisao,
                    "linha_hash",
                    None,
                ),
                "linha_nova": getattr(
                    revisao,
                    "conteudo",
                    None,
                ),
            }

            registro_id = getattr(
                revisao,
                "registro_id",
                None,
            )

            registro = getattr(
                revisao,
                "registro",
                None,
            )

            motivo_codigo = str(
                getattr(
                    revisao,
                    "regra_codigo",
                    None,
                )
                or codigo_regra
            ).strip()

            db.add(
                EfdRevisao(
                    versao_origem_id=int(versao.id),
                    versao_revisada_id=None,
                    registro_id=(
                        int(registro_id)
                        if registro_id
                        else None
                    ),
                    reg=(
                        str(registro)
                        if registro
                        else None
                    ),
                    acao=operacao,
                    revisao_json=revisao_json,
                    motivo_codigo=motivo_codigo,
                    apontamento_id=int(apontamento_id),
                )
            )

        db.flush()

        # --------------------------------------------------
        # 6) Materializa a versão revisada
        # --------------------------------------------------
        versao_revisada_id = materializar_versao_revisada(
            db=db,
            versao_origem_id=int(versao_id),
        )

        relatorio_confirmacao["versao_revisada_id"] = int(
            versao_revisada_id
        )

        versao.versao_revisada_id = int(
            versao_revisada_id
        )

        db.add(versao)
        db.flush()

        # --------------------------------------------------
        # 7) Mensagens e confirmação
        # --------------------------------------------------
        mensagens.append(
            f"{len(apontamentos_resolvidos)} apontamentos "
            "resolvidos considerados na confirmação"
        )

        mensagens.append(
            f"{total_regras_processadas} regras automáticas "
            "processadas"
        )

        mensagens.append(
            f"{total_revisoes_automaticas} revisões automáticas "
            "geradas"
        )

        mensagens.append(
            f"Versão revisada {int(versao_revisada_id)} "
            "criada com sucesso"
        )

        mensagens.append(
            "Revisões materializadas e SPED pronto para exportação"
        )

        logger.info(
            "[CONFIRMAR_REVISAO] concluído "
            "| versao_origem=%s versao_revisada=%s "
            "apontamentos=%s regras=%s revisoes=%s",
            versao_id,
            versao_revisada_id,
            len(apontamentos_resolvidos),
            total_regras_processadas,
            total_revisoes_automaticas,
        )

        db.commit()

        return {
            "ok": True,
            "versao_id": int(versao_id),
            "status": str(versao.status),
            "pendentes_erro": int(pendentes_erro),
            "versao_revisada_id": int(
                versao_revisada_id
            ),
            "mensagens": mensagens,
            "relatorio": relatorio_confirmacao,
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as exc:
        db.rollback()

        logger.exception(
            "Erro em confirmar_revisao versao_id=%s",
            versao_id,
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )

@router.post("/versao/{versao_id}/validar")
def validar_versao(versao_id: int, db: Session = Depends(get_db)):
    versao = db.query(EfdVersao).filter(EfdVersao.id == versao_id).first()
    if not versao:
        raise HTTPException(404, "Versão não encontrada.")

    if versao.status not in ("GERADA", "EM_REVISAO"):
        raise HTTPException(
            400,
            f"Versão precisa estar GERADA ou EM_REVISAO para validar. Status atual: {versao.status}"
        )

    pendentes_erro = (
                         db.query(func.count(EfdApontamento.id))
                         .filter(EfdApontamento.versao_id == versao_id)
                         .filter(EfdApontamento.tipo == "ERRO")
                         .filter(or_(EfdApontamento.resolvido.is_(False), EfdApontamento.resolvido.is_(None)))
                         .scalar()
                     ) or 0

    if int(pendentes_erro) > 0:
        raise HTTPException(400, f"Ainda existem {int(pendentes_erro)} apontamentos de ERRO pendentes.")

    # aqui entram suas regras finais (placeholder)
    # ex: checar registros obrigatórios, coerências, somatórios, etc.

    versao.status = "VALIDADA"
    db.commit()

    return {"versao_id": versao_id, "status": versao.status, "message": "Versão validada com sucesso."}



@router.delete(
    "/versao/{versao_id}/revisoes-automaticas",
    status_code=status.HTTP_200_OK,
)
def limpar_revisoes_automaticas_da_versao_endpoint(
    versao_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Remove revisões automáticas da família ICMS/EFD da versão informada.
    Não remove revisões manuais.
    """
    try:
        res = limpar_revisoes_automaticas_da_versao(
            db,
            versao_origem_id=int(versao_id),
        )
        db.commit()
        return res

    except ValueError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao limpar revisões automáticas da versão: {e}",
        )