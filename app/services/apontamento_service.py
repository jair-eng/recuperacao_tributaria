from dataclasses import dataclass
from sqlalchemy.orm import Session
from app.db.models import EfdApontamento, EfdVersao, EfdArquivo, NfIcmsItem
from typing import List
from app.fiscal.regras.Autocorrigivel.agro import aplicar_correcao_ind_agro_cst51
from app.fiscal.regras.Autocorrigivel.c170_insert_contribuicao import aplicar_correcao_c170_insert_contribuicao
from app.fiscal.regras.Autocorrigivel.cafe import aplicar_correcao_ind_cafe_cst51
from app.fiscal.regras.Autocorrigivel.lc192_corretiva_c170Existente import aplicar_correcao_lc192_c170_existente
from app.fiscal.regras.Autocorrigivel.posto_corretiva_c170Existente import aplicar_correcao_posto_credito_normal_c170
from app.fiscal.regras.Autocorrigivel.supermercado import aplicar_correcao_sup_limpeza_cst51_hibrido, \
    aplicar_correcao_sup_embalagens_cst51_hibrido
from app.fiscal.regras.Autocorrigivel.transp_cred_presu_ctes import aplicar_correcao_transp_credito_presumido
from app.fiscal.regras.Autocorrigivel.transportadora import aplicar_correcao_transp_insumo_c170
from app.icms_ipi.icms_c170_utils import _criar_revisao_insert_c170_faltante
import logging

from app.icms_ipi.icms_ipi_insercao_notas_service import inserir_notas_icms_ausentes_na_efd

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResolverTodosResult:
    versao_id: int
    updated_total: int
    pendentes_restantes: int
    contrib_sem_c170_inseridos: int = 0


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

        # 1.1) CAFÉ
        if "IND_CAFE_V1" in codigos_pendentes:
            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX IND_CAFE_V1: INICIO | versao_id=%s",
                versao_id,
            )

            res_fix = aplicar_correcao_ind_cafe_cst51(
                db,
                versao_origem_id=versao_id,
                incluir_revenda=True,  # café: pode ser agressivo mesmo
                csts_origem=["70", "73", "75", "98", "99", "06", "07", "08"],
                apontamento_id=None,  # resolve-todos (batch)
            )
            db.flush()

            if str(res_fix.get("status")) == "erro":
                raise ValueError(f"AUTO-FIX IND_CAFE falhou: {res_fix.get('msg')}")

            alterados = int(res_fix.get("total_alterado") or 0)
            total_alterado_fix += alterados

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX IND_CAFE_V1: FIM | versao_id=%s | alterados=%s",
                versao_id,
                alterados,
            )

            # ✅ guard-rail: 0 alterações = SKIP (não é erro) e NÃO marca resolvidos
            if alterados <= 0:
                res_fix["status"] = "skip"
                res_fix["msg"] = res_fix.get("msg") or "0 alterações (nada a aplicar). Mantendo apontamentos pendentes."
                # opcional: você pode querer registrar em um acumulador de skips
                # total_skips += 1


        # 1.2) AGRO
        # ✅ aqui você decide: por enquanto pode deixar DESLIGADO (comentado),
        # ou deixar ligado mas conservador (sem revenda).
        if "IND_AGRO_V1" in codigos_pendentes:

            res_fix = aplicar_correcao_ind_agro_cst51(
                db,
                versao_origem_id=versao_id,
                incluir_revenda=False,  # ✅ conservador: só 1101/2101/3101
                # opcional: se quiser travar por NCM via catálogo, passe prefixos:
                # ncm_prefixos_permitidos=["0901", "1001", "1201", "1208"],  # exemplo
                ncm_prefixos_permitidos=None,
                csts_origem=["70", "73", "75", "98", "99", "06", "07", "08"],
                apontamento_id=None,
                motivo_codigo="IND_AGRO_V1",
            )
            db.flush()

            if str(res_fix.get("status")) == "erro":
                raise ValueError(f"AUTO-FIX IND_AGRO falhou: {res_fix.get('msg')}")

            alterados = int(res_fix.get("total_alterado") or 0)
            total_alterado_fix += alterados


            # ✅ guard-rail: se a regra existe como pendente mas não alterou nada, não marca tudo resolvido
            if alterados <= 0:
                raise ValueError(
                    "AUTO-FIX IND_AGRO não alterou nenhum registro. "
                    "Não vou marcar apontamentos como resolvidos."
                )

        # 1.3) EMBALAGEM (depende de IND_AGRO/IND_CAFE existir; a própria regra só cria apontamento nesse caso)

        if "EMB_INSUMO_V1" in codigos_pendentes:

            res_fix = aplicar_correcao_sup_embalagens_cst51_hibrido(
                db,
                versao_origem_id=versao_id,
                incluir_revenda=False,  # ✅ conservador (pode ligar depois se quiser)
                csts_origem=["70", "73", "75", "98", "99", "06", "07", "08"],
                apontamento_id=None,
                motivo_codigo="EMB_INSUMO_V1",
            )
            db.flush()

            if str(res_fix.get("status")) == "erro":
                raise ValueError(f"AUTO-FIX EMBALAGEM falhou: {res_fix.get('msg')}")

            alterados = int(res_fix.get("total_alterado") or 0)
            total_alterado_fix += alterados


            if alterados <= 0:
                raise ValueError(
                    "AUTO-FIX EMBALAGEM não alterou nenhum registro. "
                    "Não vou marcar apontamentos como resolvidos."
                )

        # 1.4) C170 EXISTENTE LC192

        total_lc192_alterados = 0
        total_lc192_skips = 0
        total_lc192_erros = 0

        if {"COMB_LC192_V1", "COMB_LC192_AGR_V1"} & set(codigos_pendentes):

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX COMB_LC192_V1: INICIO | versao_id=%s",
                versao_id,
            )

            aps_lc192 = (
                db.query(EfdApontamento)
                .filter(EfdApontamento.versao_id == versao_id)
                .filter(EfdApontamento.codigo.in_(["COMB_LC192_V1", "COMB_LC192_AGR_V1"]))
                .filter(EfdApontamento.resolvido.is_(False))
                .all()
            )

            for ap in aps_lc192:
                meta = ap.meta_json or {}
                registro_ids = meta.get("registro_ids") or []
                itens = [{"registro_id": int(x)} for x in registro_ids if x]

                if not itens:
                    registro_id = (
                            meta.get("c170_registro_id")
                            or meta.get("registro_id")
                            or getattr(ap, "registro_id", None)
                    )
                    if not registro_id:
                        total_lc192_skips += 1
                        continue
                    itens = [{"registro_id": int(registro_id)}]

                res_fix = aplicar_correcao_lc192_c170_existente(
                    db,
                    versao_origem_id=int(versao_id),
                    itens=itens,
                    apontamento_id=int(ap.id),
                )
                db.flush()
                status = str(res_fix.get("status") or "").lower()
                if status == "erro":
                    total_lc192_erros += 1
                    logger.warning(
                        "[RESOLVER_TODOS] COMB_LC192_V1 erro | apontamento_id=%s | msg=%s",
                        ap.id,
                        res_fix.get("msg"),
                    )
                    continue
                if status in ("skip", "vazio"):
                    total_lc192_skips += 1
                    continue

                total_lc192_alterados += int(res_fix.get("total_alterado") or 0)

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX COMB_LC192_V1: FIM | versao_id=%s | alterados=%s | skips=%s | erros=%s",
                versao_id,
                total_lc192_alterados,
                total_lc192_skips,
                total_lc192_erros,
            )

        # 1.5) C170 faltante na contribuição
        total_contrib_sem_c170_inseridos = 0
        total_contrib_sem_c170_recalc_c100 = 0
        total_contrib_sem_c170_erros = 0
        total_contrib_sem_c170_skips = 0

        if "CONTRIB_SEM_C170_V1" in codigos_pendentes:

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX CONTRIB_SEM_C170_V1: INICIO | versao_id=%s",
                versao_id,
            )

            aps_c170 = (
                db.query(EfdApontamento)
                .filter(EfdApontamento.versao_id == versao_id)
                .filter(EfdApontamento.codigo == "CONTRIB_SEM_C170_V1")
                .all()
            )

            grupos: dict[tuple[int, int], dict] = {}

            for ap in aps_c170:
                meta = ap.meta_json or {}

                if meta.get("acao_sugerida_lc192") == "INSERIR_C170_LC192":
                    nf_icms_item_ids = meta.get("nf_icms_item_ids") or []

                    if not nf_icms_item_ids and meta.get("nf_icms_item_id"):
                        nf_icms_item_ids = [meta.get("nf_icms_item_id")]

                    res_fix = aplicar_correcao_c170_insert_contribuicao(
                        db,
                        versao_origem_id=versao_id,
                        apontamento_id=int(ap.id),
                        nf_icms_item_ids=nf_icms_item_ids,
                        registro_id_c100=meta.get("registro_id_c100") or meta.get("registro_id_ancora"),
                        linha_c100=meta.get("linha_c100") or meta.get("linha_ancora"),
                        motivo_codigo="COMB_LC192_V1",
                        contexto="LC192",
                        aliq_pis="1.65",
                        aliq_cofins="7.60",
                    )
                    db.flush()

                    status_fix = str(res_fix.get("status") or "").lower()

                    if status_fix == "erro":
                        total_contrib_sem_c170_erros += 1
                        logger.warning(
                            "[RESOLVER_TODOS] CONTRIB_SEM_C170_LC192 erro | apontamento_id=%s | msg=%s",
                            ap.id,
                            res_fix.get("msg"),
                        )
                        continue

                    if status_fix in ("skip", "vazio"):
                        total_contrib_sem_c170_skips += 1
                        continue

                    total_contrib_sem_c170_inseridos += int(res_fix.get("insert_criado") or 0)
                    total_contrib_sem_c170_recalc_c100 += int(res_fix.get("c100_recalculado") or 0)

                    continue

                reg_c100 = int(meta.get("registro_id_c100") or meta.get("registro_id_ancora") or 0)
                lin_c100 = int(meta.get("linha_c100") or meta.get("linha_ancora") or 0)
                item_id = int(meta.get("nf_icms_item_id") or 0)

                if not reg_c100 or not lin_c100 or not item_id:
                    continue

                chave = (reg_c100, lin_c100)
                if chave not in grupos:
                    grupos[chave] = {
                        "registro_id_c100": reg_c100,
                        "linha_c100": lin_c100,
                        "nf_icms_item_ids": [],
                        "apontamento_ids": [],
                    }

                if item_id not in grupos[chave]["nf_icms_item_ids"]:
                    grupos[chave]["nf_icms_item_ids"].append(item_id)
                grupos[chave]["apontamento_ids"].append(int(ap.id))

            for _, g in grupos.items():
                res_fix = aplicar_correcao_c170_insert_contribuicao(
                    db,
                    versao_origem_id=versao_id,
                    apontamento_id=None,
                    nf_icms_item_ids=g["nf_icms_item_ids"],
                    registro_id_c100=g["registro_id_c100"],
                    linha_c100=g["linha_c100"],
                    motivo_codigo="CONTRIB_SEM_C170_V1",
                )
                if "CONTRIB_SEM_C170_V1" in codigos_pendentes:
                    print(
                        "[DBG CONTRIB_SEM_C170 RES]",
                        {
                            "grupo": g,
                            "res_fix": res_fix,
                        },
                        flush=True,
                    )
                db.flush()

                status_fix = str(res_fix.get("status") or "").lower()

                if status_fix == "erro":
                    total_contrib_sem_c170_erros += 1
                    logger.warning(
                        "[RESOLVER_TODOS] CONTRIB_SEM_C170_V1 erro | apontamento_id=%s | msg=%s",
                        ap.id,
                        res_fix.get("msg"),
                    )
                    continue

                if status_fix in ("skip", "vazio"):
                    total_contrib_sem_c170_skips += 1
                    continue

                total_contrib_sem_c170_inseridos += int(res_fix.get("insert_criado") or 0)
                total_contrib_sem_c170_recalc_c100 += int(res_fix.get("c100_recalculado") or 0)

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX CONTRIB_SEM_C170_V1: FIM | versao_id=%s | inseridos=%s | c100_recalc=%s | skips=%s | erros=%s",
                versao_id,
                total_contrib_sem_c170_inseridos,
                total_contrib_sem_c170_recalc_c100,
                total_contrib_sem_c170_skips,
                total_contrib_sem_c170_erros,
            )
        # 1.6) TRANSP_INSUMO_V1
        total_transp_alterados = 0
        total_transp_erros = 0
        total_transp_skips = 0

        if "TRANSP_INSUMO_V1" in codigos_pendentes:
            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX TRANSP_INSUMO_V1: INICIO | versao_id=%s",
                versao_id,
            )

            res_fix = aplicar_correcao_transp_insumo_c170(
                db,
                versao_origem_id=versao_id,
                apontamento_id=None,
            )
            db.flush()

            if str(res_fix.get("status")) == "erro":
                raise ValueError(f"AUTO-FIX TRANSP_INSUMO_V1 falhou: {res_fix.get('msg')}")

            alterados = int(res_fix.get("total_alterado") or 0)
            total_alterado_fix += alterados

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX TRANSP_INSUMO_V1: FIM | versao_id=%s | alterados=%s",
                versao_id,
                alterados,
            )

            if alterados <= 0:
                res_fix["status"] = "skip"
                res_fix["msg"] = res_fix.get("msg") or "0 alterações (nada a aplicar). Mantendo apontamentos pendentes."

        # 1.7) POSTO_CREDITO_NORMAL_V1
        total_posto_normal_alterados = 0
        total_posto_normal_erros = 0
        total_posto_normal_skips = 0

        if "POSTO_CREDITO_NORMAL_V1" in codigos_pendentes:
            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX POSTO_CREDITO_NORMAL_V1: INICIO | versao_id=%s",
                versao_id,
            )

            res_fix = aplicar_correcao_posto_credito_normal_c170(
                db,
                versao_origem_id=versao_id,
                apontamento_id=None,
            )
            db.flush()

            if str(res_fix.get("status")) == "erro":
                raise ValueError(
                    f"AUTO-FIX POSTO_CREDITO_NORMAL_V1 falhou: {res_fix.get('msg')}"
                )

            alterados = int(res_fix.get("total_alterado") or 0)
            erros = int(res_fix.get("total_erros") or 0)
            skips = int(
                res_fix.get("ignorados_sem_registro") or 0
            ) + int(
                res_fix.get("ignorados_nao_autofix") or 0
            ) + int(
                res_fix.get("ignorados_sem_oportunidade") or 0
            )

            total_posto_normal_alterados += alterados
            total_posto_normal_erros += erros
            total_posto_normal_skips += skips
            total_alterado_fix += alterados

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX POSTO_CREDITO_NORMAL_V1: FIM | "
                "versao_id=%s | candidatos=%s | alterados=%s | skips=%s | erros=%s | status=%s",
                versao_id,
                res_fix.get("candidatos"),
                alterados,
                skips,
                erros,
                res_fix.get("status"),
            )

            if alterados <= 0:
                res_fix["status"] = "skip"
                res_fix["msg"] = (
                        res_fix.get("msg")
                        or "0 alterações (nada a aplicar). Mantendo apontamentos pendentes."
                )

        # 1.8 Inserir C100s faltantes no contribuicoes

        total_contrib_sem_c100_inseridos = 0
        total_contrib_sem_c100_lc192_inseridos = 0
        total_contrib_sem_c100_lc192_c170 = 0
        total_contrib_sem_c100_lc192_erros = 0
        total_contrib_sem_c100_lc192_skips = 0

        versao = db.get(EfdVersao, int(versao_id))
        if not versao:
            raise ValueError(f"Versão {versao_id} não encontrada")

        arquivo = getattr(versao, "arquivo", None)
        empresa_id_ctx = getattr(arquivo, "empresa_id", None)

        if not empresa_id_ctx:
            raise ValueError(f"empresa_id não encontrado para versao_id={versao_id}")
        periodo_lc192 = (
                meta.get("periodo_lc192")
                or meta.get("periodo")
                or meta.get("periodo_arquivo")
        )

        if "CONTRIB_SEM_C100_V1" in codigos_pendentes:
            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX CONTRIB_SEM_C100_V1: INICIO | versao_id=%s",
                versao_id,
            )

            aps_c100 = (
                db.query(EfdApontamento)
                .filter(EfdApontamento.versao_id == versao_id)
                .filter(EfdApontamento.codigo == "CONTRIB_SEM_C100_V1")
                .filter(EfdApontamento.resolvido.is_(False))
                .all()
            )
            alterados = 0
            for ap in aps_c100:
                meta = dict(ap.meta_json or {})
                nf_icms_base_ids = meta.get("nf_icms_base_ids") or []
                nf_icms_base_ids = [int(x) for x in nf_icms_base_ids if x]

                if not nf_icms_base_ids:
                    logger.warning(...)
                    continue

                #  LC192 primeiro
                if meta.get("acao_sugerida_lc192") == "INSERIR_C100_C170_LC192":
                    res_fix = inserir_notas_icms_ausentes_na_efd(
                        db,
                        versao_origem_id=int(versao_id),
                        empresa_id=int(empresa_id_ctx),
                        periodo=None,
                        apontamento_id=int(ap.id),
                        nf_icms_base_ids=nf_icms_base_ids,
                        contexto="LC192",
                        aliq_pis="1.65",
                        aliq_cofins="7.60",
                        motivo_codigo="COMB_LC192_V1",
                        periodo_lc192=periodo_lc192,
                        regime_lc192=meta.get("regime_lc192") or "1",
                    )
                    db.flush()

                    if not res_fix.get("ok", False):
                        total_contrib_sem_c100_lc192_erros += 1
                        logger.warning(
                            "[RESOLVER_TODOS] CONTRIB_SEM_C100_LC192 erro | apontamento_id=%s | retorno=%s",
                            ap.id,
                            res_fix,
                        )
                        continue

                    qtd_c100 = int(res_fix.get("total_c100_insert") or 0)
                    qtd_c170 = int(res_fix.get("total_c170_insert") or 0)

                    total_contrib_sem_c100_lc192_inseridos += qtd_c100
                    total_contrib_sem_c100_lc192_c170 += qtd_c170
                    alterados += qtd_c100
                    if qtd_c100 <= 0:
                        total_contrib_sem_c100_lc192_skips += 1
                        logger.warning(
                            "[RESOLVER_TODOS] CONTRIB_SEM_C100_LC192 SKIP sem inserção | apontamento_id=%s | nf_ids=%s | retorno=%s",
                            ap.id,
                            nf_icms_base_ids,
                            res_fix,
                        )
                        continue
                    logger.info(
                        "[RESOLVER_TODOS] CONTRIB_SEM_C100_LC192 OK | versao_id=%s | apontamento_id=%s | nf_ids=%s | c100=%s | c170=%s",
                        versao_id,
                        ap.id,
                        nf_icms_base_ids,
                        qtd_c100,
                        qtd_c170,
                    )
                    continue

                # fluxo normal
                res_fix = inserir_notas_icms_ausentes_na_efd(
                    db,
                    versao_origem_id=int(versao_id),
                    empresa_id=int(empresa_id_ctx),
                    periodo=None,
                    apontamento_id=int(ap.id),
                    nf_icms_base_ids=nf_icms_base_ids,
                )
                db.flush()

                if not res_fix.get("ok", False):
                    raise ValueError(
                        f"AUTO-FIX CONTRIB_SEM_C100 falhou | apontamento_id={ap.id} | retorno={res_fix}"
                    )

                qtd_c100 = int(res_fix.get("total_c100_insert") or 0)
                qtd_c170 = int(res_fix.get("total_c170_insert") or 0)

                alterados += qtd_c100

                logger.info(
                    "[RESOLVER_TODOS] CONTRIB_SEM_C100_V1 OK | versao_id=%s | apontamento_id=%s | nf_ids=%s | c100=%s | c170=%s",
                    versao_id,
                    ap.id,
                    nf_icms_base_ids,
                    qtd_c100,
                    qtd_c170,
                )

            total_alterado_fix += alterados
            total_contrib_sem_c100_inseridos += alterados

            logger.info(
                "[RESOLVER_TODOS] AUTO-FIX CONTRIB_SEM_C100_V1: FIM | versao_id=%s | alterados=%s",
                versao_id,
                alterados,
            )

            if alterados <= 0:
                raise ValueError(
                    "AUTO-FIX CONTRIB_SEM_C100 não alterou nenhum registro. "
                    "Não vou marcar apontamentos como resolvidos."
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
            "[RESOLVER_TODOS] RESUMO | versao_id=%s | updated_total=%s | pendentes_restantes=%s | total_alterado_fix=%s | contrib_sem_c170_inseridos=%s",
            versao_id,
            int(updated or 0),
            int(pendentes_restantes or 0),
            int(total_alterado_fix),
            int(total_contrib_sem_c170_inseridos),
        )

        return ResolverTodosResult(
            versao_id=versao_id,
            updated_total=int(updated or 0),
            pendentes_restantes=int(pendentes_restantes or 0),
            contrib_sem_c170_inseridos=int(total_contrib_sem_c170_inseridos),
        )