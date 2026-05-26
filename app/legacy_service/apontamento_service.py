from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.db.models import EfdApontamento, EfdVersao
from typing import List
from app.Legacy.fiscal.regras.Autocorrigivel.agro import aplicar_correcao_ind_agro_cst51
from app.Legacy.fiscal.regras.Autocorrigivel.c170_insert_contribuicao import aplicar_correcao_c170_insert_contribuicao
from app.Legacy.fiscal.regras.Autocorrigivel.cafe import aplicar_correcao_ind_cafe_cst51
from app.Legacy.fiscal.regras.Autocorrigivel.lc192_corretiva_c170Existente import aplicar_correcao_lc192_c170_existente
from app.Legacy.fiscal.regras.Autocorrigivel.posto_corretiva_c170Existente import aplicar_correcao_posto_credito_normal_c170
from app.Legacy.fiscal.regras.Autocorrigivel.supermercado import aplicar_correcao_sup_embalagens_cst51_hibrido
from app.Legacy.fiscal.regras.Autocorrigivel.transportadora import aplicar_correcao_transp_insumo_c170
import logging

from app.domain.workflow.corretiva_v2_service import aplicar_corretiva_apontamento_v2
from app.legacy_icms_ipi.icms_ipi_insercao_notas_service import inserir_notas_icms_ausentes_na_efd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolverTodosResult:
    versao_id: int
    updated_total: int
    pendentes_restantes: int
    contrib_sem_c170_inseridos: int = 0
    v2_corretivas: int = 0
    v2_skips: int = 0
    v2_erros: int = 0

class ApontamentoService:
    @staticmethod
    def resolver_todos_pendentes_por_versao(db: Session, *, versao_id: int) -> ResolverTodosResult:
        versao_id = int(versao_id)

        # 0) Descobre códigos pendentes antes de resolver
        codigos_pendentes: List[str] = [
            str(x[0])
            for x in (
                db.query(EfdApontamento.codigo)
                .filter(EfdApontamento.versao_id == versao_id)
                .filter(EfdApontamento.resolvido.is_(False))
                .distinct()
                .all()
            )
            if x and x[0]
        ]

        logger.info(
            "[RESOLVER_TODOS] INICIO | versao_id=%s | codigos_pendentes=%s",
            versao_id,
            codigos_pendentes,
        )

        # 1) AUTO-FIX — CAFÉ (prioridade) + AGRO (quando você quiser habilitar)
        total_alterado_fix = 0

        total_v2_corretivas = 0
        total_v2_erros = 0
        total_v2_skips = 0

        if "CREDITO_NAO_APROVEITADO_V2" in codigos_pendentes:
            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX CREDITO_NAO_APROVEITADO_V2: INICIO | versao_id=%s",
                versao_id,
            )

            aps_v2 = (
                db.query(EfdApontamento)
                .filter(EfdApontamento.versao_id == versao_id)
                .filter(EfdApontamento.codigo == "CREDITO_NAO_APROVEITADO_V2")
                .filter(EfdApontamento.resolvido.is_(False))
                .all()
            )
            chaves_v2_processadas = set()

            for ap in aps_v2:
                meta = ap.meta_json or {}
                status_cruzamento = str(meta.get("status_cruzamento") or "").upper()

                if status_cruzamento != "SO_ICMS":
                    total_v2_skips += 1
                    logger.info(
                        "[RESOLVER_TODOS] V2 skip | apontamento_id=%s | status_cruzamento=%s",
                        ap.id,
                        status_cruzamento,
                    )
                    continue

                chave_nfe = str(meta.get("chave_nfe") or "").strip()

                if chave_nfe and chave_nfe in chaves_v2_processadas:
                    total_v2_skips += 1
                    logger.info(
                        "[RESOLVER_TODOS] V2 skip NF já processada | apontamento_id=%s | chave_nfe=%s",
                        ap.id,
                        chave_nfe,
                    )
                    continue

                if chave_nfe:
                    chaves_v2_processadas.add(chave_nfe)

                res_fix = aplicar_corretiva_apontamento_v2(
                    db=db,
                    apontamento_id=int(ap.id),
                )
                db.flush()

                if not res_fix.get("ok"):
                    total_v2_erros += 1
                    logger.warning(
                        "[RESOLVER_TODOS] V2 erro | apontamento_id=%s | retorno=%s",
                        ap.id,
                        res_fix,
                    )
                    continue

                total_v2_corretivas += 1

                logger.info(
                    "[RESOLVER_TODOS] V2 OK | apontamento_id=%s | tipo=%s | retorno=%s",
                    ap.id,
                    res_fix.get("tipo_corretiva"),
                    res_fix,
                )

            total_alterado_fix += total_v2_corretivas

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX CREDITO_NAO_APROVEITADO_V2: FIM | "
                "versao_id=%s | corretivas=%s | skips=%s | erros=%s",
                versao_id,
                total_v2_corretivas,
                total_v2_skips,
                total_v2_erros,
            )

        # 2) Marca tudo como resolvido (comportamento atual)
        updated = (
            db.query(EfdApontamento)
            .filter(EfdApontamento.versao_id == versao_id)
            .filter(EfdApontamento.resolvido.is_(False))
            .update({EfdApontamento.resolvido: True}, synchronize_session=False)
        )

        pendentes_restantes = (
            db.query(EfdApontamento)
            .filter(EfdApontamento.versao_id == versao_id)
            .filter(EfdApontamento.resolvido.is_(False))
            .count()
        )
        logger.info(
            "[RESOLVER_TODOS] RESUMO | versao_id=%s | updated_total=%s | pendentes_restantes=%s | total_alterado_fix=%s | v2_corretivas=%s | v2_skips=%s | v2_erros=%s",
            versao_id,
            int(updated or 0),
            int(pendentes_restantes or 0),
            int(total_alterado_fix),
            int(total_v2_corretivas),
            int(total_v2_skips),
            int(total_v2_erros),
        )

        return ResolverTodosResult(
            versao_id=versao_id,
            updated_total=int(updated or 0),
            pendentes_restantes=int(pendentes_restantes or 0),
            v2_corretivas=int(total_v2_corretivas),
            v2_skips=int(total_v2_skips),
            v2_erros=int(total_v2_erros),
        )