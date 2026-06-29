from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.db.models import EfdApontamento, EfdVersao, NfIcmsBase, NfIcmsItem, ItemFiscalConsolidado
from typing import List
import logging
from app.domain.workflow.corretiva_v2_service import aplicar_corretiva_apontamento_v2
from app.legacy_icms_ipi.icms_ipi_insercao_notas_service import _inserir_bloco_nf_icms_na_efd, \
    _resolver_ancora_bloco_c_fim
from app.sped.bloco_0.bloco_0_0190_0200_agregador import _garantir_mestres_para_notas_elegiveis
from app.utils.numbers import fmt_aliq_sped
from app.utils.sped import montar_cache_mestres_logicos

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

        total_alterado_fix = 0
        total_v2_corretivas = 0
        total_v2_erros = 0
        total_v2_skips = 0

        ids_processados_lote: set[int] = set()

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

            # 1) Primeiro resolve em lote os casos de bloco completo C100+C170
            res_lote = _resolver_v2_c100_c170_por_nf(
                db=db,
                versao_id=versao_id,
                apontamentos=aps_v2,
            )

            ids_processados_lote = set(res_lote.get("ids_processados") or [])
            total_v2_corretivas += int(res_lote.get("corretivas") or 0)
            total_v2_erros += int(res_lote.get("erros") or 0)
            total_v2_skips += int(res_lote.get("skips") or 0)

            logger.info(
                "[RESOLVER_TODOS] V2 LOTE C100_C170 | versao_id=%s | nfs=%s | apontamentos=%s | erros=%s",
                versao_id,
                res_lote.get("nfs_processadas"),
                len(ids_processados_lote),
                res_lote.get("erros"),
            )

            # 2) Depois resolve individualmente os demais SO_ICMS

            ########
            logger.warning(
                "[DEBUG APS_V2] total=%s",
                len(aps_v2),
            )

            tipos = {}

            for ap in aps_v2:
                meta = ap.meta_json or {}
                tipo = str(meta.get("tipo_corretiva_v2") or "SEM_TIPO")
                tipos[tipo] = tipos.get(tipo, 0) + 1

            logger.warning(
                "[DEBUG APS_V2 TIPOS] %s",
                tipos,
            )
            #######

            cache_corretiva_v2 = {
                "cache_mestres": montar_cache_mestres_logicos(
                    db,
                    versao_origem_id=versao_id,
                )
            }
            for ap in aps_v2:
                if int(ap.id) in ids_processados_lote:
                    continue

                meta = ap.meta_json or {}

                status_cruzamento = str(meta.get("status_cruzamento") or "").upper()
                tipo_corretiva_v2 = meta.get("tipo_corretiva_v2")

                logger.info(
                    "[RESOLVER_TODOS] V2 candidato | ap=%s status=%s tipo=%s reg_c170=%s item=%s",
                    ap.id,
                    status_cruzamento,
                    tipo_corretiva_v2,
                    meta.get("registro_id_c170") or meta.get("registro_id_ancora"),
                    ap.item_fiscal_consolidado_id,
                )

                if status_cruzamento not in {"SO_ICMS", "MATCH"}:
                    total_v2_skips += 1
                    continue

                if tipo_corretiva_v2 == "INSERIR_C100_C170":
                    total_v2_erros += 1
                    logger.warning(
                        "[RESOLVER_TODOS] V2 C100_C170 NAO AGRUPADO | apontamento_id=%s | item_fiscal_consolidado_id=%s | meta_keys=%s",
                        ap.id,
                        ap.item_fiscal_consolidado_id,
                        list((meta or {}).keys()),
                    )
                    continue

                res_fix = aplicar_corretiva_apontamento_v2(
                    db=db,
                    apontamento_id=int(ap.id),
                    cache=cache_corretiva_v2,
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
                    "[RESOLVER_TODOS] V2 OK | apontamento_id=%s | tipo=%s",
                    ap.id,
                    res_fix.get("tipo_corretiva"),
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

def _resolver_v2_c100_c170_por_nf(
        *,
        db: Session,
        versao_id: int,
        apontamentos: list[EfdApontamento],
) -> dict:
    grupos: dict[int, dict] = {}
    skips = 0
    for ap in apontamentos:
        meta = ap.meta_json or {}

        if meta.get("tipo_corretiva_v2") != "INSERIR_C100_C170":
            continue

        nf_item_id = (
                meta.get("nf_icms_item_id")
                or meta.get("item_icms_id")
        )

        if not nf_item_id and ap.item_fiscal_consolidado_id:
            item_cons = (
                db.query(ItemFiscalConsolidado)
                .filter(ItemFiscalConsolidado.id == int(ap.item_fiscal_consolidado_id))
                .first()
            )

            if item_cons:
                nf_item_id = getattr(item_cons, "nf_icms_item_id", None)

        if not nf_item_id:

            skips += 1
            continue

        nf_item = (
            db.query(NfIcmsItem)
            .filter(NfIcmsItem.id == int(nf_item_id))
            .first()
        )

        if not nf_item:

            skips += 1
            continue

        nf_id = int(getattr(nf_item, "nf_icms_base_id", 0) or 0)

        if not nf_id:
            continue
        logger.warning(
            "[V2 LOTE] grupos_nf=%s apontamentos=%s",
            len(grupos),
            len(apontamentos),
        )
        if nf_id not in grupos:
            grupos[nf_id] = {
                "nf_id": nf_id,
                "apontamentos": [],
                "itens": [],
                "meta_base": meta,
            }


        grupos[nf_id]["apontamentos"].append(ap)
        grupos[nf_id]["itens"].append(nf_item)


    ids_processados: list[int] = []
    erros = 0
    corretivas = 0
    nfs_processadas = 0

    for nf_id, grupo in grupos.items():

        nf = (
            db.query(NfIcmsBase)
            .filter(NfIcmsBase.id == int(nf_id))
            .first()
        )


        if not nf:
            erros += len(grupo["apontamentos"])
            continue

        itens = grupo["itens"]
        apontamentos_grupo = grupo["apontamentos"]
        meta = grupo["meta_base"]

        logger.warning(
            "[DEBUG NF PROCESSAR] nf_id=%s itens=%s apontamentos=%s",
            nf_id,
            len(itens),
            len(apontamentos_grupo),
        )
        enq = meta.get("enquadramento") or {}
        contexto = meta.get("codigo_cenario") or meta.get("cenario")
        aliq_pis = fmt_aliq_sped(enq.get("aliq_pis") or "")
        aliq_cofins = fmt_aliq_sped(enq.get("aliq_cofins") or "")
        res_mestres = None
        try:
            res_mestres = _garantir_mestres_para_notas_elegiveis(
                db,
                versao_origem_id=versao_id,
                notas_elegiveis=[(nf, itens, str(getattr(nf, "chave_nfe", "") or ""))],
            )

            registro_id_alvo, linha_ref_alvo, acao_inicial = _resolver_ancora_bloco_c_fim(
                db,
                versao_origem_id=versao_id,
            )

            res_bloco = _inserir_bloco_nf_icms_na_efd(
                db,
                versao_origem_id=versao_id,
                nf=nf,
                itens=itens,
                registro_id_alvo=registro_id_alvo,
                linha_ref_alvo=linha_ref_alvo,
                acao_inicial=acao_inicial,
                apontamento_id=int(apontamentos_grupo[0].id),
                contexto=contexto,
                aliq_pis=aliq_pis,
                aliq_cofins=aliq_cofins,
                cod_cred=enq.get("cod_cred"),
                nat_bc_cred=enq.get("nat_bc_cred"),
                motivo_codigo="CORRETIVA_V2_SO_ICMS",
            )
            logger.warning(
                "[DEBUG NF OK] nf_id=%s c170=%s apontamentos=%s",
                nf_id,
                res_bloco.get("c170_inseridos"),
                len(apontamentos_grupo),
            )

            for ap in apontamentos_grupo:
                ap.resolvido = True
                db.add(ap)
                ids_processados.append(int(ap.id))

            db.flush()

            corretivas += len(apontamentos_grupo)
            nfs_processadas += 1

            logger.info(
                "[RESOLVER_TODOS] V2 LOTE NF OK | nf_id=%s | apontamentos=%s | c170=%s",
                nf_id,
                len(apontamentos_grupo),
                res_bloco.get("c170_inseridos"),
            )

        except Exception as e:
            erros += len(apontamentos_grupo)
            logger.exception(
                "[RESOLVER_TODOS] V2 LOTE NF ERRO | nf_id=%s | erro=%s",
                nf_id,
                e,
            )
    logger.warning(
        "[V2 LOTE RESUMO] nfs=%s apontamentos=%s itens=%s",
        nfs_processadas,
        len(ids_processados),
        sum(len(g["itens"]) for g in grupos.values()),
    )
    return {
        "ids_processados": ids_processados,
        "corretivas": corretivas,
        "skips": skips,
        "erros": erros,
        "nfs_processadas": nfs_processadas,
    }