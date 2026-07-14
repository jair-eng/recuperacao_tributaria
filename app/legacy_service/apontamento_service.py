from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.db.models import EfdApontamento, EfdVersao, NfIcmsBase, NfIcmsItem, ItemFiscalConsolidado
from typing import List
import logging
from app.domain.workflow.corretiva_v2_service import aplicar_corretiva_apontamento_v2
from app.legacy_icms_ipi.icms_ipi_insercao_notas_service import _inserir_bloco_nf_icms_na_efd, \
    _resolver_ancora_bloco_c_fim, inserir_notas_icms_ausentes_na_efd_v2
from app.sped.blocoC.listar_c100_ausentes_no_contribuicoes import _nf_icms_pf_skip, _extrair_ind_oper_cod_sit_do_nf
from app.sped.bloco_0.bloco_0_0190_0200_agregador import _garantir_mestres_para_notas_elegiveis
from app.utils.numbers import fmt_aliq_sped
from app.utils.sped import montar_cache_mestres_logicos
from app.utils.strings import only_digits

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
                        "[RESOLVER_TODOS] V2 C100_C170 SOBROU APOS LOTE | "
                        "apontamento_id=%s | item_fiscal_consolidado_id=%s | "
                        "nf_icms_item_id_meta=%s | chave=%s | tipo=%s | status=%s",
                        ap.id,
                        ap.item_fiscal_consolidado_id,
                        meta.get("nf_icms_item_id"),
                        meta.get("chave_nfe"),
                        tipo_corretiva_v2,
                        meta.get("status_cruzamento"),
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
    erros = 0

    for ap in apontamentos:
        meta = ap.meta_json or {}

        if meta.get("tipo_corretiva_v2") != "INSERIR_C100_C170":
            continue

        # trava: se já tem C100, não é fluxo de NF ausente
        if bool(meta.get("contrib_tem_c100")):
            skips += 1
            logger.warning(
                "[V2 LOTE] skip C100_C170 com contrib_tem_c100=True | ap=%s item=%s",
                ap.id,
                ap.item_fiscal_consolidado_id,
            )
            continue

        if not ap.item_fiscal_consolidado_id:
            skips += 1
            logger.warning("[V2 LOTE] NAO AGRUPADO | motivo=sem_item_fiscal_consolidado_id | ap=%s", ap.id)
            continue

        item_cons = (
            db.query(ItemFiscalConsolidado)
            .filter(ItemFiscalConsolidado.id == int(ap.item_fiscal_consolidado_id))
            .first()
        )
        if not item_cons:
            skips += 1
            logger.warning(
                "[V2 LOTE] NAO AGRUPADO | motivo=item_cons_nao_encontrado | ap=%s item_cons_id=%s",
                ap.id,
                ap.item_fiscal_consolidado_id,
            )
            continue

        nf_id_meta = int(meta.get("nf_icms_base_id") or 0)

        nf_item_id = (
                getattr(item_cons, "nf_icms_item_id", None)
                or meta.get("nf_icms_item_id")
        )

        if not nf_item_id:
            skips += 1
            logger.warning(
                "[V2 LOTE] NAO AGRUPADO | motivo=sem_nf_icms_item_id | ap=%s item_cons=%s meta_nf_item=%s",
                ap.id,
                getattr(item_cons, "id", None),
                meta.get("nf_icms_item_id"),
            )
            continue

        nf_item = (
            db.query(NfIcmsItem)
            .filter(NfIcmsItem.id == int(nf_item_id))
            .first()
        )
        if not nf_item:
            skips += 1
            logger.warning(
                "[V2 LOTE] NAO AGRUPADO | motivo=nf_item_nao_encontrado | ap=%s nf_item_id=%s",
                ap.id,
                nf_item_id,
            )
            continue

        nf_id_item = int(getattr(nf_item, "nf_icms_base_id", 0) or 0)
        nf_id_cons = int(getattr(item_cons, "nf_icms_base_id", 0) or 0)

        if nf_id_cons and nf_id_item and nf_id_cons != nf_id_item:
            erros += 1
            logger.warning(
                "[V2 LOTE] vínculo inconsistente item_cons x nf_item | "
                "ap=%s item_cons=%s nf_item=%s nf_id_cons=%s nf_id_item=%s",
                ap.id,
                item_cons.id,
                nf_item.id,
                nf_id_cons,
                nf_id_item,
            )
            continue

        if nf_id_meta and nf_id_item and nf_id_meta != nf_id_item:
            erros += 1
            logger.warning(
                "[V2 LOTE] vínculo inconsistente meta x nf_item | "
                "ap=%s item_cons=%s nf_item=%s nf_id_meta=%s nf_id_item=%s",
                ap.id,
                item_cons.id,
                nf_item.id,
                nf_id_meta,
                nf_id_item,
            )
            continue

        nf_id = nf_id_meta or nf_id_item or nf_id_cons

        if not nf_id:
            skips += 1
            logger.warning(
                "[V2 LOTE] NAO AGRUPADO | motivo=sem_nf_id | ap=%s nf_item=%s item_cons=%s",
                ap.id,
                getattr(nf_item, "id", None),
                getattr(item_cons, "id", None),
            )
            continue

        grupos.setdefault(nf_id, {
            "nf_id": nf_id,
            "itens_ctx": [],
        })

        grupos[nf_id]["itens_ctx"].append({
            "ap": ap,
            "item_cons": item_cons,
            "nf_item": nf_item,
            "meta": meta,
        })

    notas_elegiveis_v2: list[dict] = []
    logger.warning(
        "[V2 LOTE] grupos=%s",
        {
            nf_id: len(grupo["itens_ctx"])
            for nf_id, grupo in grupos.items()
        }
    )

    for nf_id, grupo in grupos.items():
        itens_ctx = grupo["itens_ctx"]
        apontamentos_grupo = [x["ap"] for x in itens_ctx]

        nf = db.query(NfIcmsBase).filter(NfIcmsBase.id == int(nf_id)).first()
        if not nf:
            erros += len(apontamentos_grupo)
            continue

        chave = only_digits(getattr(nf, "chave_nfe", None) or "")
        cod_mod = str(getattr(nf, "cod_mod", None) or getattr(nf, "modelo", None) or "").strip()

        # travas iguais ao listar_c100_ausentes
        if cod_mod and cod_mod != "55":
            skips += len(apontamentos_grupo)
            logger.info("[V2 LOTE] skip NF cod_mod != 55 | nf_id=%s cod_mod=%s", nf_id, cod_mod)
            continue

        if not chave:
            skips += len(apontamentos_grupo)
            logger.info("[V2 LOTE] skip NF sem chave | nf_id=%s", nf_id)
            continue

        ind_oper, cod_sit = _extrair_ind_oper_cod_sit_do_nf(nf)

        if ind_oper != "0":
            skips += len(apontamentos_grupo)
            logger.info("[V2 LOTE] skip NF saída | nf_id=%s ind_oper=%s", nf_id, ind_oper)
            continue

        if cod_sit in {"06", "07"}:
            skips += len(apontamentos_grupo)
            logger.info("[V2 LOTE] skip NF cod_sit | nf_id=%s cod_sit=%s", nf_id, cod_sit)
            continue

        if _nf_icms_pf_skip(nf):
            skips += len(apontamentos_grupo)
            logger.info("[V2 LOTE] skip NF PF | nf_id=%s", nf_id)
            continue

        assinaturas = {
            (
                x["meta"].get("cod_cred")
                or x["meta"].get("tipo_credito_codigo"),

                x["meta"].get("nat_bc_cred")
                or x["meta"].get("base_credito_codigo")
                or x["meta"].get("cod_base_credito"),
            )
            for x in itens_ctx
        }

        if len(assinaturas) != 1:
            erros += len(apontamentos_grupo)

            logger.warning(
                "[V2 LOTE] NF com tratamentos fiscais incompatíveis | "
                "nf_id=%s chave=%s assinaturas=%s",
                nf_id,
                chave,
                assinaturas,
            )
            continue

        meta_base = itens_ctx[0]["meta"]
        enq = meta_base.get("enquadramento") or {}

        contexto = (
            meta_base.get("codigo_cenario")
            or meta_base.get("cenario")
            or meta_base.get("contexto_credito")
        )

        cod_cred = (
            meta_base.get("cod_cred")
            or meta_base.get("tipo_credito_codigo")
            or enq.get("cod_cred")
            or enq.get("tipo_credito_codigo")
        )

        nat_bc_cred = (
            meta_base.get("nat_bc_cred")
            or meta_base.get("base_credito_codigo")
            or meta_base.get("cod_base_credito")
            or enq.get("nat_bc_cred")
            or enq.get("base_credito_codigo")
            or enq.get("cod_base_credito")
        )
        cst_pis_destino = (
                meta_base.get("cst_pis_destino")
                or enq.get("cst_pis_destino")
        )

        cst_cofins_destino = (
                meta_base.get("cst_cofins_destino")
                or enq.get("cst_cofins_destino")
        )

        if (
                not contexto
                or not cod_cred
                or not nat_bc_cred
                or not cst_pis_destino
                or not cst_cofins_destino
        ):
            erros += len(apontamentos_grupo)

            logger.warning(
                "[V2 LOTE] NF sem enquadramento fiscal completo | "
                "nf_id=%s contexto=%s cod_cred=%s nat=%s "
                "cst_pis=%s cst_cofins=%s",
                nf_id,
                contexto,
                cod_cred,
                nat_bc_cred,
                cst_pis_destino,
                cst_cofins_destino,
            )
            continue

        itens_ctx = [
            x for x in itens_ctx
            if x["meta"].get("tipo_corretiva_v2") == "INSERIR_C100_C170"
               and (
                       x["meta"].get("codigo_cenario")
                       or x["meta"].get("cenario")
                       or x["meta"].get("contexto_credito")
               )
               and (
                       x["meta"].get("cod_cred")
                       or x["meta"].get("tipo_credito_codigo")
               )
               and (
                       x["meta"].get("nat_bc_cred")
                       or x["meta"].get("base_credito_codigo")
                       or x["meta"].get("cod_base_credito")
               )
        ]

        itens_ctx = sorted(
            itens_ctx,
            key=lambda x: (
                int(getattr(x["nf_item"], "num_item", 0) or 0),
                int(getattr(x["nf_item"], "id", 0) or 0),
            ),
        )
        # Transporta cenário/fundamento do apontamento até a resolução do 0500.
        # É atributo transitório: não altera o banco nem o bloco de inserção.
        for x in itens_ctx:
            meta_item = x["meta"] or {}
            nf_item = x["nf_item"]

            fundamentos_item = (
                    meta_item.get("fundamento_legal")
                    or meta_item.get("codigo_cenario")
                    or meta_item.get("cenario")
                    or meta_item.get("contexto_credito")
            )

            setattr(
                nf_item,
                "_fundamentos_cenario_v2",
                fundamentos_item,
            )
            logger.warning(
                "[V2 LOTE FUNDAMENTO ITEM] nf_item=%s descricao=%s fundamento=%s",
                getattr(nf_item, "id", None),
                getattr(nf_item, "descricao", None),
                fundamentos_item,
            )

        itens = [x["nf_item"] for x in itens_ctx]

        logger.warning(
            "[V2 LOTE][ENQUADRAMENTO_NOTA] "
            "nf_id=%s chave=%s contexto=%s "
            "cod_cred=%s nat=%s "
            "cst_pis=%s cst_cofins=%s "
            "aliq_pis=%s aliq_cofins=%s",
            nf_id,
            chave,
            contexto,
            cod_cred,
            nat_bc_cred,
            cst_pis_destino,
            cst_cofins_destino,
            enq.get("aliq_pis"),
            enq.get("aliq_cofins"),
        )

        notas_elegiveis_v2.append({
            "nf": nf,
            "itens": itens,
            "chave": chave,
            "contexto": contexto,
            "cod_cred": cod_cred,
            "nat_bc_cred": nat_bc_cred,
            "cst_pis_destino": str(cst_pis_destino).strip().zfill(2),
            "cst_cofins_destino": str(cst_cofins_destino).strip().zfill(2),
            "aliq_pis": fmt_aliq_sped(enq.get("aliq_pis") or ""),
            "aliq_cofins": fmt_aliq_sped(enq.get("aliq_cofins") or ""),
            "apontamento_id": int(apontamentos_grupo[0].id),
            "apontamentos": apontamentos_grupo,
        })

    notas_elegiveis_v2 = sorted(
        notas_elegiveis_v2,
        key=lambda x: (
            str(getattr(x["nf"], "dt_doc", "") or ""),
            str(getattr(x["nf"], "num_doc", "") or ""),
            int(getattr(x["nf"], "id", 0) or 0),
        ),
    )

    ids_processados: list[int] = []
    corretivas = 0
    nfs_processadas = 0

    if notas_elegiveis_v2:
        res_lote = inserir_notas_icms_ausentes_na_efd_v2(
            db,
            versao_origem_id=versao_id,
            notas_elegiveis=notas_elegiveis_v2,
        )

        for nota_ctx in notas_elegiveis_v2:
            for ap in nota_ctx.get("apontamentos") or []:
                ap.resolvido = True
                db.add(ap)
                ids_processados.append(int(ap.id))

            corretivas += len(nota_ctx.get("apontamentos") or [])
            nfs_processadas += 1

        db.flush()

        logger.info(
            "[RESOLVER_TODOS] V2 LOTE OK | nfs=%s c100=%s c170=%s",
            res_lote.get("total_notas_ausentes"),
            res_lote.get("total_c100_insert"),
            res_lote.get("total_c170_insert"),
        )

    logger.warning(
        "[V2 LOTE DEBUG IDS] apontamentos_entrada=%s agrupados=%s processados=%s sobraram=%s",
        len(apontamentos),
        sum(len(g["itens_ctx"]) for g in grupos.values()),
        len(ids_processados),
        len([ap for ap in apontamentos if ap.id not in set(ids_processados)]),
    )

    return {
        "ids_processados": ids_processados,
        "corretivas": corretivas,
        "skips": skips,
        "erros": erros,
        "nfs_processadas": nfs_processadas,
    }