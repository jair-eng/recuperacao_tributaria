from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP
import traceback
from typing import Any, Optional, Dict
from pathlib import Path
from sqlalchemy.orm import Session
from app.config.settings import ALIQUOTA_PIS, ALIQUOTA_COFINS  # 0.0165 / 0.0760
from app.Legacy.fiscal.constants import DOM_GERAL
from app.services.dominio_service import resolver_dominio_por_versao
from app.sped.blocoM.blocoM_m_append_service import bloco_m_tem_valor_relevante, gerar_linhas_m_credito_append, \
    inserir_creditos_no_bloco_m_original
from app.sped.bloco_1.credito_estoque_v2_service import atualizar_credito_estoque_v2, buscar_creditos_estoque_v2
from app.sped.bloco_1.historico_fs import extrair_cnpj_periodo_do_0000
from app.sped.utils_geral import dec_br
from app.legacy_service.revisao_override_m_service import (
    buscar_override_bloco_m,
    extrair_credito_total_do_bloco_m,
)
from app.sped.blocoM.blocoM import construir_bloco_m_v3
from app.sped.bloco_0.bloco_0_0900 import aplicar_0900_se_necessario, recalcular_0990_bloco0
from app.sped.bloco_1.builder import (
     montar_bloco_1_com_estoque_v2
)
from app.db.models import EfdVersao, EfdArquivo, EfdRegistro
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert
from app.sped.blocoM.m_utils import caminho_sped_corrigido, nome_sped_corrigido, _cst_norm, carregar_ajustes_m, \
    _clean_sped_line, _reg_of_line, extrair_cods_cred_bloco_m, map_nat_por_cst_do_m_original
from app.sped.parser import parse_sped_from_lines
from app.sped.utils_hierarquia import resolver_ind_oper_c100_com_fallback
from app.sped.writer import gerar_sped
import app.sped.writer as writer_module
from app.sped.layouts.c170 import LAYOUT_C170
from app.sped.blocoC.c170_utils import _parse_linha_sped_to_reg_dados
from app.sped.logic.consolidador import obter_conteudo_final, eh_pf_por_c100, _q2
from app.sped.bloco_1.utils_1500 import yyyymm_to_mmyyyy
from app.legacy_service.revisao_override_base_service import buscar_override_base_por_cst
import logging

logger = logging.getLogger(__name__)



def exportar_sped(
    *,
    versao_id: int,
    caminho_saida: Optional[str] = None,
    db: Session,
    valor_utilizado_mes: float = 0.0,
    gerar_arquivo: bool = True,
) -> str:
    versao = db.get(EfdVersao, int(versao_id))
    if not versao:
        raise ValueError("Versão não encontrada")

    retifica_de = getattr(versao, "retifica_de_versao_id", None)

    # 🔒 TRAVA: não exporta original
    if not retifica_de:
        raise ValueError(
            "Exportação bloqueada: esta é uma versão ORIGINAL. "
            "Primeiro confirme a revisão para materializar a versão revisada e só então exporte."
        )

    versao_origem_id = int(retifica_de)
    versao_final_id = int(versao.id)

    relatorio_exportacao: Dict[str, Any] = {
        "versao_id": int(versao_id),
        "versao_origem_id": int(versao_origem_id),
        "versao_final_id": int(versao_final_id),
        "arquivo_saida": None,
        "c170_creditaveis": 0,
        "pf_bloqueados": 0,
        "cfop_fora_escopo": 0,
        "nao_entrada": 0,
        "sem_pai": 0,
        "base_total": "0.00",
        "credito_pis": "0.00",
        "credito_cofins": "0.00",
        "credito_total": "0.00",
        "override_bloco_m": False,
        "override_base_por_cst": False,
        "ajustes_m": 0,
    }
    mensagens: list[str] = []

    logger.info(
        "EXPORT iniciado | versao_id=%s | origem=%s | final=%s",
        versao_id,
        versao_origem_id,
        versao_final_id,
    )

    # 1) carrega linhas com overlay aplicado
    linhas = carregar_linhas_logicas_com_revisoes_e_insert(
        db=db,
        versao_origem_id=versao_origem_id,
        versao_final_id=versao_final_id,
    )

    # 2) configurações do arquivo
    arquivo = db.get(EfdArquivo, int(versao.arquivo_id))
    if not arquivo:
        raise ValueError("Arquivo não encontrado para a versão")

    nome_arquivo = nome_sped_corrigido(arquivo, versao)

    if not caminho_saida:
        caminho_saida = caminho_sped_corrigido(nome_arquivo)

    final_path = Path(caminho_saida)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    line_ending = getattr(arquivo, "line_ending", "CRLF")
    newline = "\r\n" if str(line_ending).upper() == "CRLF" else "\n"

    CST_CREDITO = {"50", "51", "52", "53", "54", "55", "56","61"}

    try:

        dominio_export = resolver_dominio_por_versao(db, versao_final_id) or DOM_GERAL
        dominio_export = str(dominio_export).strip().upper()
        logger.info("EXPORT dominio=%s", dominio_export)

        # 3) soma C170 por CST (layout-driven) - já com overlay aplicado - separando o Natureza op
        base_por_nat_cst: Dict[str, Dict[str, Decimal]] = {}
        base_delta_por_cod_cred_nat_cst: Dict[str, Dict[str, Dict[str, Decimal]]] = {}
        qtd_itens_delta = 0
        qtd_itens = 0
        qtd_pf = 0

        # DEBUG (sem dict): conta quantas linhas suspeitas entraram na soma
        dbg_cfop_fora = 0
        dbg_nao_entrada = 0
        dbg_sem_pai = 0

        conteudo_linhas = [
            obter_conteudo_final(l) or ""
            for l in linhas
        ]

        linhas_m_originais = [
            ln
            for ln in conteudo_linhas
            if (ln or "").lstrip().startswith("|M")
        ]

        nat_por_cst_m_original = map_nat_por_cst_do_m_original(
            linhas_m_originais
        )

        for ln in linhas:
            conteudo = obter_conteudo_final(ln) or ""

            if "|C170|" not in conteudo:
                continue

            try:
                reg, dados = _parse_linha_sped_to_reg_dados(conteudo)
            except Exception:
                continue

            if reg != "C170":
                continue

            # CST PIS
            if len(dados) <= LAYOUT_C170.idx_cst_pis:
                continue

            cst_pis = _cst_norm(dados[LAYOUT_C170.idx_cst_pis])
            if cst_pis not in CST_CREDITO:
                continue

            # trava PF
            registro_id = getattr(ln, "registro_id", None)
            rid_int = int(registro_id) if registro_id else 0

            if rid_int and eh_pf_por_c100(db, versao_origem_id, rid_int):
                qtd_pf += 1
                continue

            # VL_ITEM
            if len(dados) <= LAYOUT_C170.idx_vl_item:
                continue

            vl_item = dec_br(dados[LAYOUT_C170.idx_vl_item])
            if vl_item <= 0:
                continue

            vl_desc = dec_br(dados[LAYOUT_C170.idx_vl_desc]) if len(dados) > LAYOUT_C170.idx_vl_desc else Decimal(
                "0.00")
            vl_icms = dec_br(dados[LAYOUT_C170.idx_vl_icms]) if len(dados) > LAYOUT_C170.idx_vl_icms else Decimal(
                "0.00")

            base_liquida = vl_item - vl_desc - vl_icms
            if base_liquida <= 0:
                continue

            # ---------------------------
            # CFOP + ENTRADA (guard-rails)
            # ---------------------------
            cfop = ""
            try:
                if len(dados) > LAYOUT_C170.idx_cfop:
                    cfop = str(dados[LAYOUT_C170.idx_cfop] or "").strip()
            except Exception:
                cfop = ""


            # NAT_BC_CRED fallback
            meta_ln = getattr(ln, "meta", None) or {}
            rev_json = getattr(ln, "revisao_json", None) or {}

            meta_rev = {}
            if isinstance(rev_json, dict):
                meta_rev = (
                    rev_json.get("meta")
                    if isinstance(rev_json.get("meta"), dict)
                    else rev_json
                )

            revisao_id = int(getattr(ln, "revisao_id", 0) or 0)

            nat = str(
                (meta_ln.get("nat_bc_cred") if isinstance(meta_ln, dict) else None)
                or (meta_ln.get("base_credito_codigo") if isinstance(meta_ln, dict) else None)
                or (meta_ln.get("cod_base_credito") if isinstance(meta_ln, dict) else None)
                or (meta_ln.get("natureza_credito_m") if isinstance(meta_ln, dict) else None)
                or meta_rev.get("nat_bc_cred")
                or meta_rev.get("base_credito_codigo")
                or meta_rev.get("cod_base_credito")
                or meta_rev.get("natureza_credito_m")
                or ""
            ).strip()

            if not nat:
                if revisao_id > 0:
                    logger.warning(
                        "DEBUG DELTA | revisao_id=%s meta_ln=%s rev_json=%s",
                        revisao_id,
                        meta_ln,
                        rev_json,
                    )
                    raise RuntimeError(
                        f"DELTA sem nat/base_credito | rid={rid_int} cfop={cfop}"
                    )
                nat = nat_por_cst_m_original.get(cst_pis, "")

            # 2) Só ENTRADAS (IND_OPER do C100 pai == "0")
            ind_oper = resolver_ind_oper_c100_com_fallback(
                db=db,
                linha=ln,
                rid=rid_int,
                linhas=linhas,
            )


            # Conservador: se não achou pai/ind_oper, NÃO soma
            if not ind_oper:
                dbg_sem_pai += 1
                logger.debug(
                    "BASE_SKIP_SEM_PAI | rid=%s cfop=%s cst=%s vl_item=%s",
                    rid_int or "?",
                    cfop or "?",
                    cst_pis,
                    vl_item,
                )
                continue

            if ind_oper != "0":
                dbg_nao_entrada += 1
                logger.debug(
                    "BASE_SKIP_SAIDA | ind_oper=%s cfop=%s rid=%s cst=%s vl_item=%s",
                    ind_oper,
                    cfop or "?",
                    rid_int or "?",
                    cst_pis,
                    vl_item,
                )
                continue

            # ---------------------------
            # Soma (agora já filtrado)
            # ---------------------------
            base_por_nat_cst.setdefault(nat, {})
            base_por_nat_cst[nat][cst_pis] = (
                    base_por_nat_cst[nat].get(cst_pis, Decimal("0.00")) + base_liquida
            )
            qtd_itens += 1

            # --------------------------------------------------
            # DELTA: somente linhas criadas/alteradas pelo motor
            # --------------------------------------------------
            revisao_id = int(getattr(ln, "revisao_id", 0) or 0)

            eh_delta_motor = revisao_id > 0

            # opcional/conservador: exige meta ou contexto
            if eh_delta_motor:
                meta_rev = {}
                if isinstance(rev_json, dict):
                    meta_rev = (
                        rev_json.get("meta")
                        if isinstance(rev_json.get("meta"), dict)
                        else rev_json
                    )

                cod_cred_delta = str(
                    (meta_ln.get("cod_cred") if isinstance(meta_ln, dict) else None)
                    or (meta_ln.get("tipo_credito_codigo") if isinstance(meta_ln, dict) else None)
                    or meta_rev.get("cod_cred")
                    or meta_rev.get("tipo_credito_codigo")
                    or ""
                ).strip()

                nat_delta = str(
                    (meta_ln.get("nat_bc_cred") if isinstance(meta_ln, dict) else None)
                    or (meta_ln.get("base_credito_codigo") if isinstance(meta_ln, dict) else None)
                    or (meta_ln.get("cod_base_credito") if isinstance(meta_ln, dict) else None)
                    or meta_rev.get("nat_bc_cred")
                    or meta_rev.get("base_credito_codigo")
                    or meta_rev.get("cod_base_credito")
                    or meta_rev.get("natureza_credito_m")
                    or nat
                ).strip()

                if not cod_cred_delta:
                    raise RuntimeError(
                        f"DELTA sem cod Credito!"
                    )

                if not nat_delta:
                    nat_delta = nat

                base_delta_por_cod_cred_nat_cst.setdefault(cod_cred_delta, {})
                base_delta_por_cod_cred_nat_cst[cod_cred_delta].setdefault(nat_delta, {})
                base_delta_por_cod_cred_nat_cst[cod_cred_delta][nat_delta][cst_pis] = (
                        base_delta_por_cod_cred_nat_cst[cod_cred_delta][nat_delta].get(cst_pis, Decimal("0.00"))
                        + base_liquida
                )
                logger.warning(
                    "[MAPA_M] cod_cred=%s nat=%s cst=%s base=%s revisao=%s",
                    cod_cred_delta,
                    nat_delta,
                    cst_pis,
                    base_liquida,
                    revisao_id,
                )

                qtd_itens_delta += 1


        base_total = sum(
            (base for mapa_cst in base_por_nat_cst.values() for base in mapa_cst.values()),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"), ROUND_HALF_UP)
        credito_pis = (base_total * Decimal("0.0165")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        credito_cofins = (base_total * Decimal("0.0760")).quantize(Decimal("0.01"), ROUND_HALF_UP)
        credito_total_calc = (credito_pis + credito_cofins).quantize(Decimal("0.01"), ROUND_HALF_UP)
        #Relatorio da exportacao
        relatorio_exportacao["c170_creditaveis"] = int(qtd_itens)
        relatorio_exportacao["pf_bloqueados"] = int(qtd_pf)
        relatorio_exportacao["cfop_fora_escopo"] = int(dbg_cfop_fora)
        relatorio_exportacao["nao_entrada"] = int(dbg_nao_entrada)
        relatorio_exportacao["sem_pai"] = int(dbg_sem_pai)
        relatorio_exportacao["base_total"] = str(base_total)
        relatorio_exportacao["credito_pis"] = str(credito_pis)
        relatorio_exportacao["credito_cofins"] = str(credito_cofins)
        relatorio_exportacao["credito_total"] = str(credito_total_calc)

        logger.info(
            "EXPORT resumo base | versao_id=%s base_total=%s pis=%s cofins=%s cred_total=%s c170_creditaveis=%s pf_bloqueados=%s cfop_fora=%s nao_entrada=%s sem_pai=%s",
            versao_id,
            base_total,
            credito_pis,
            credito_cofins,
            credito_total_calc,
            qtd_itens,
            qtd_pf,
            dbg_cfop_fora,
            dbg_nao_entrada,
            dbg_sem_pai,
        )

        # 4) remove COMPLETAMENTE M* do conteúdo (por linha, não por reg do objeto)
        conteudo_linhas = [(obter_conteudo_final(l) or "") for l in linhas]
        conteudo_sem_m = [ln for ln in conteudo_linhas if not (ln or "").lstrip().startswith("|M")]

        linhas_m_originais = [
            ln for ln in conteudo_linhas
            if (ln or "").lstrip().startswith("|M")
        ]
        m_original_tem_valor = bloco_m_tem_valor_relevante(linhas_m_originais)
        logger.info(
            "BLOCO M original | qtd=%s | tem_valor=%s ",
            len(linhas_m_originais),
            m_original_tem_valor,
        )

        # 5) histórico (1100/1500) + captura CNPJ/período do 0000
        cnpj_empresa, periodo_0000 = extrair_cnpj_periodo_do_0000(conteudo_sem_m)

        if not cnpj_empresa:
            logger.warning("HISTÓRICO | CNPJ não encontrado no 0000. Histórico desativado.")

        # >>> Bloco 0900 (layout PVA real) <<<
        conteudo_sem_m = aplicar_0900_se_necessario(
            linhas_sped=conteudo_sem_m,
            periodo_yyyymm=int(periodo_0000) if periodo_0000 else None,
        )

        conteudo_sem_m = recalcular_0990_bloco0(conteudo_sem_m)


        # Parse do conteúdo final (já com 0900 se inserido)
        parsed = parse_sped_from_lines(conteudo_sem_m)

        # carregar ajustes para M zerado
        ajustes_m = carregar_ajustes_m(db, versao_id=versao_final_id)
        relatorio_exportacao["ajustes_m"] = len(ajustes_m or [])

        if ajustes_m:
            logger.info(
                "AJUSTE_M carregados | total=%s | tipos_top=%s",
                len(ajustes_m),
                [a.get("tipo") for a in ajustes_m[:3]],
            )
        else:
            logger.info("AJUSTE_M | nenhum ajuste encontrado")

        # 6) Override de BASE por CST
        override_base = buscar_override_base_por_cst(
            db,
            versao_origem_id=versao_origem_id,
            versao_final_id=versao_final_id,
        )

        # ✅ regra: OVERRIDE_BASE_POR_CST só entra se NÃO houver AJUSTE_M de exportação
        # (porque exportação é delta e já está em AJUSTE_M; evitar "replace" e evitar duplicar)
        tem_ajuste_export = any(
            isinstance(a, dict)
            and isinstance(a.get("meta"), dict)
            and str(a["meta"].get("tipo") or "").strip().upper() == "EXPORTACAO_RESSARCIMENTO"
            for a in (ajustes_m or [])
        )

        if override_base is not None and not tem_ajuste_export:
            relatorio_exportacao["override_base_por_cst"] = True
            logger.info("BASE_POR_CST | usando override do banco")

        elif override_base is not None and tem_ajuste_export:
            logger.info("BASE_POR_CST | override ignorado por exportação via AJUSTE_M")

        # 6a) Bloco M: override do banco > fallback construir_bloco_m_v3
        override_db = buscar_override_bloco_m(
            db,
            versao_origem_id=versao_origem_id,
            versao_final_id=versao_final_id,
        )

        if override_db is not None:
            relatorio_exportacao["override_bloco_m"] = True
            logger.info("BLOCO M | usando override do banco")
            bloco_m_override = override_db
            # se override existir, crédito do 1100 deve refletir ele (não o cálculo)
            credito_total_1100 = extrair_credito_total_do_bloco_m(bloco_m_override)
        else:
            logger.debug(
                "M_BASE | base_por_nat_cst=%s",
                {
                    nat: {cst: str(v) for cst, v in mapa.items()}
                    for nat, mapa in (base_por_nat_cst or {}).items()
                },
            )
            try:
                for nat, mapa in (base_por_nat_cst or {}).items():
                    for cst, base in (mapa or {}).items():
                        base_dec = Decimal(str(base or "0"))
                        pis = _q2(base_dec * ALIQUOTA_PIS)
                        cofins = _q2(base_dec * ALIQUOTA_COFINS)
                        total = _q2(pis + cofins)
                        logger.info(
                            "BLOCO_M_RESUMO | nat=%s cst=%s base=%s pis=%s cofins=%s total=%s",
                            nat,
                            cst,
                            base_dec,
                            pis,
                            cofins,
                            total,
                        )
            except Exception:
                logger.exception("BLOCO_M_RESUMO | erro ao calcular resumo")
            tem_delta = bool(base_delta_por_cod_cred_nat_cst)

            if m_original_tem_valor and tem_delta:
                logger.info("BLOCO M | preservando original e inserindo créditos delta")

                linhas_append = []

                for cod_cred_delta, base_por_nat_cst_delta in sorted(
                        base_delta_por_cod_cred_nat_cst.items()
                ):
                    linhas_append.extend(
                        gerar_linhas_m_credito_append(
                            base_por_nat_cst_delta,
                            cod_cred=str(cod_cred_delta),
                        )
                    )
                bloco_m_override = inserir_creditos_no_bloco_m_original(
                    linhas_m_originais,
                    linhas_append,
                )
            else:
                logger.info("BLOCO M | M inexistente/zerado, gerando pelo motor v3")

                if base_delta_por_cod_cred_nat_cst:
                    blocos_m_por_cod: list[str] = []
                    logger.warning(
                        "[MAPA_M_FINAL] %s",
                        {
                            cod: {
                                nat: {
                                    cst: str(base)
                                    for cst, base in mapa_cst.items()
                                }
                                for nat, mapa_cst in mapa_nat.items()
                            }
                            for cod, mapa_nat in base_delta_por_cod_cred_nat_cst.items()
                        },
                    )

                    for cod_cred_delta, base_por_nat_cst_delta in sorted(
                            base_delta_por_cod_cred_nat_cst.items()
                    ):
                        logger.warning(
                            "[BLOCO_M_V3][ENTRADA] cod_cred=%s mapa=%s",
                            cod_cred_delta,
                            {
                                nat: {
                                    cst: str(base)
                                    for cst, base in mapa.items()
                                }
                                for nat, mapa in base_por_nat_cst_delta.items()
                            },
                        )

                        bloco_tmp = construir_bloco_m_v3(
                            linhas_sped=conteudo_sem_m,
                            parsed=parsed,
                            base_por_nat_cst=base_por_nat_cst_delta,
                            cod_cred=str(cod_cred_delta),
                            ajustes_m=ajustes_m,
                        )
                        logger.warning(
                            "[BLOCO_M_V3][SAIDA] cod_cred=%s regs=%s",
                            cod_cred_delta,
                            [
                                _reg_of_line(_clean_sped_line(l))
                                for l in bloco_tmp
                            ],
                        )

                        for l in bloco_tmp:
                            logger.warning("[BLOCO_M_V3] %s", l)

                        for ln in bloco_tmp:
                            ln = _clean_sped_line(ln)
                            if not ln:
                                continue

                            reg = _reg_of_line(ln)

                            # mantém só o corpo M; M001/M990 serão recompostos no final
                            if reg in {"M001", "M990"}:
                                continue

                            blocos_m_por_cod.append(ln)

                    bloco_m_override = ["|M001|0|"]
                    bloco_m_override.extend(list(dict.fromkeys(blocos_m_por_cod)))
                    bloco_m_override.append(f"|M990|{len(bloco_m_override) + 1}|")

                if not base_delta_por_cod_cred_nat_cst:
                    logger.info(
                        "Nenhum delta fiscal encontrado. "
                        "Mantendo bloco M original." )

                    bloco_m_override = linhas_m_originais

            credito_total_1100 = extrair_credito_total_do_bloco_m(bloco_m_override)

        # 7) Bloco 1 (1100/1500) - NOVO ESTOQUE V2
        periodo_atual = getattr(arquivo, "periodo", None)
        if not periodo_atual:
            raise ValueError("EfdArquivo.periodo não preenchido (YYYYMM).")

        periodo_atual = str(periodo_atual)

        estoques_v2 = buscar_creditos_estoque_v2(
            db=db,
            empresa_id=int(versao.empresa_id),
            periodo_atual=periodo_atual,
        )

        linhas_bloco_1_originais = [
            ln for ln in conteudo_linhas
            if (ln or "").lstrip().startswith("|1")
        ]

        bloco_1_override = montar_bloco_1_com_estoque_v2(
            linhas_sped=linhas_bloco_1_originais,
            periodo_atual=periodo_atual,
            estoques_v2=estoques_v2,
        )

        logger.warning("DBG BLOCO_1_V2 | estoque_qtd=%s", len(estoques_v2 or []))
        logger.warning("DBG BLOCO_1_V2 | linhas_originais=%s", len(linhas_bloco_1_originais or []))
        logger.warning("DBG BLOCO_1_V2 | linhas_final=%s", len(bloco_1_override or []))
        logger.warning("DBG BLOCO_1_V2 | primeira=%s", bloco_1_override[0] if bloco_1_override else None)
        logger.warning("DBG BLOCO_1_V2 | ultima=%s", bloco_1_override[-1] if bloco_1_override else None)

        if not bloco_1_override:
            raise RuntimeError("EXPORT bloqueado: bloco_1_override vazio.")

        if not bloco_1_override[0].startswith("|1001|"):
            raise RuntimeError(
                f"EXPORT bloqueado: Bloco 1 sem 1001. Primeira={bloco_1_override[0]}"
            )

        if not bloco_1_override[-1].startswith("|1990|"):
            raise RuntimeError(
                f"EXPORT bloqueado: Bloco 1 sem 1990. Última={bloco_1_override[-1]}"
            )

        logger.debug("BLOCO_M linhas=%s", len(bloco_m_override or []))

        if bloco_m_override:
            logger.debug("BLOCO_M primeira_linha=%s", bloco_m_override[0])
            logger.debug("BLOCO_M contem_M100=%s", any(l.startswith("|M100|") for l in bloco_m_override))
            logger.debug("BLOCO_M contem_M500=%s", any(l.startswith("|M500|") for l in bloco_m_override))

        # 8) escreve
        logger.debug("SPED writer=%s", writer_module.__file__)
        gerar_sped(
            conteudo_sem_m,
            str(final_path),
            newline=newline,
            bloco_m_override=bloco_m_override,
            bloco_1_override=bloco_1_override,
        )

        atualizar_credito_estoque_v2(
            db=db,
            empresa_id=int(versao.empresa_id),
            versao_exportada_id=int(versao.id),
            periodo_origem=periodo_atual,
            base_delta_por_cod_cred_nat_cst=base_delta_por_cod_cred_nat_cst,
        )

        logger.warning(
            "ESTOQUE_V2 ATUALIZADO | empresa_id=%s | versao=%s | periodo=%s | cods=%s",
            int(versao.empresa_id),
            int(versao.id),
            periodo_atual,
            list((base_delta_por_cod_cred_nat_cst or {}).keys()),
        )

        # status/caminho
        try:
            versao.status = "EXPORTADA"
            if hasattr(versao, "caminho_exportado"):
                versao.caminho_exportado = str(final_path)
            db.add(versao)
            db.commit()
        except Exception as _e:
            db.rollback()
            print("⚠️ Não consegui persistir status/caminho_exportado:", repr(_e))

        relatorio_exportacao["arquivo_saida"] = str(final_path)

        mensagens.append(f"SPED exportado com sucesso")
        mensagens.append(f"Arquivo gerado: {final_path.name}")
        mensagens.append(f"{qtd_itens} registros C170 creditáveis considerados")
        mensagens.append(f"Base total calculada: {base_total}")
        mensagens.append(f"Crédito PIS calculado: {credito_pis}")
        mensagens.append(f"Crédito COFINS calculado: {credito_cofins}")

        if relatorio_exportacao["ajustes_m"]:
            mensagens.append(f"{relatorio_exportacao['ajustes_m']} ajustes de Bloco M aplicados")

        if relatorio_exportacao["override_bloco_m"]:
            mensagens.append("Bloco M gerado via override de revisão")
        else:
            mensagens.append("Bloco M gerado pelo motor padrão")

        logger.info("EXPORT concluída com sucesso | versao_id=%s | arquivo=%s", versao_id, final_path)

        if not gerar_arquivo:
            return {
                "ok": True,
                "mensagens": mensagens,
                "relatorio_exportacao": relatorio_exportacao,
            }

        return str(final_path)

    except Exception as e:
        print(f"❌ ERRO ao construir/exportar SPED: {e}")
        traceback.print_exc()

        raise  # <-- sem fallback durante debug