from __future__ import annotations

import time
from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, List,Tuple
from sqlalchemy.orm import Session
from app.db.models import EfdRegistro, EfdApontamento
from app.fiscal.constants import DOM_SUP, DOM_GERAL, DOMINIOS_VALIDOS
from app.fiscal.dto import RegistroFiscalDTO
from app.fiscal.regras.Diagnostico.insumos.lc192_helpers import consolidar_achados_comb_lc192_v1
from app.db.models.efd_versao import EfdVersao
from app.db.models.efd_arquivo import EfdArquivo
from app.fiscal.scanners.c100_entrada import montar_c100_entrada_relevante_agg
from app.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.fiscal.scanners.exportacao import montar_c170_export_agg, \
    montar_c170_ind_torrado_agg, montar_c170_insumo_agg, montar_c170_saida_agg
from app.fiscal.scanners.scanner_helpers import key_apontamento, norm_codigo, norm_prioridade, prioridade_por_impacto, \
    safe_float, consolidar_achados_cfop_sem_credito_v1
from app.fiscal.scanners.util_scan import aplicar_contexto
from app.fiscal.varredura import executar_varredura
from app.fiscal.regras.Diagnostico.achado import Achado
from app.fiscal.scanners.exportacao import montar_meta_fiscal
from app.icms_ipi.icms_ipi_cruzamento_service import cruzar_versao_com_icms_ipi
from app.services.versao_overlay_service import carregar_linhas_logicas_com_revisoes
from app.sped.blocoC.c100_utils import consolidar_apontamentos_contrib_sem_c100
from app.sped.blocoC.c170_utils import linhas_para_rows_like, consolidar_apontamentos_contrib_sem_c170
from app.fiscal.contexto import set_fiscal_context
import logging

from app.sped.blocoC.listar_c100_ausentes_no_contribuicoes import listar_c100_ausentes
from app.sped.bloco_D.d100_icms_contribuicao_cruzamento import cruzar_d100_icms_com_contribuicoes
from app.sped.bloco_D.d100_parser import parse_d100
from app.sped.bloco_D.d100_utils import carregar_d100_icms, consolidar_achados_transp_cred_pres_v1
from app.sped.logic.consolidador import popular_pai_id, filtrar_apontamentos_contrib_sem_c170
from app.sped.utils_geral import consolidar_achados_c170_insumo_v2, _safe_json

logger = logging.getLogger(__name__)

class FiscalScanner:
    @staticmethod
    def scan_versao(
        db: Session,
        *,
        versao_id: int,
        empresa_id: int,
        preservar_resolvidos: bool = True,
        aplicar_revisoes: bool = True,
    ) -> Dict[str, Any]:
        """
        Scanner fiscal:
        - Carrega registros da versão
        - (Opcional) aplica revisões overlay
        - Expurga registros vinculados a participante PF (CPF 11 dígitos) para regras/agrupadores
        - Monta DTOs com contexto (versao_id/empresa_id)
        - Injeta META_FISCAL e agregadores
        - Executa motor fiscal
        - Persiste apontamentos preservando resolvidos (merge por chave lógica)
        """
        logger.info(
            "SCAN iniciado | versao_id=%s | empresa_id=%s | aplicar_revisoes=%s",
            versao_id,
            empresa_id,
            aplicar_revisoes,
        )

        scan_report: Dict[str, Any] = {
            "versao_id": int(versao_id),
            "empresa_id": int(empresa_id) if empresa_id else None,
            "rows_base": 0,
            "rows_agg": 0,
            "rows_limpas": 0,
            "dtos_total": 0,
            "dtos_c170": 0,
            "pf_bloqueados": 0,
            "c100_sit_skip": 0,
            "agregadores_criados": [],
        }

        # -----------------------------
        # 0) Normalizações e contexto
        # -----------------------------
        versao_id = int(versao_id)
        popular_pai_id(db, versao_id)

        if empresa_id is None:
            versao = db.get(EfdVersao, versao_id)
            empresa_id = getattr(versao, "empresa_id", None)
            if empresa_id is None and versao and getattr(versao, "arquivo_id", None):
                arquivo = db.get(EfdArquivo, int(versao.arquivo_id))
                empresa_id = getattr(arquivo, "empresa_id", None)

        empresa_id_ctx = int(empresa_id) if empresa_id is not None else None
        if empresa_id_ctx is None:
            raise ValueError("empresa_id não pôde ser resolvido para scan_versao")

        set_fiscal_context(db, empresa_id_ctx)

        # -----------------------------
        # 1) Buscar registros originais (Fonte da Verdade)
        # -----------------------------
        rows: List[EfdRegistro] = (
            db.query(EfdRegistro)
            .filter(EfdRegistro.versao_id == versao_id)
            .order_by(EfdRegistro.linha.asc())
            .all()
        )
        scan_report["rows_base"] = len(rows)

        rid_to_pai_id = {int(r.id): int(getattr(r, "pai_id", 0) or 0) for r in rows}
        linha_to_registro_id = {int(r.linha): int(r.id) for r in rows}

        # --- [OTIMIZAÇÃO DE PERFORMANCE: MAPAS EM MEMÓRIA] ---
        # 1.1) Mapa de Participantes: Classifica quem é PF (CPF com 11 dígitos)
        participantes_pf: dict[str, bool] = {}
        for r in rows:
            if (r.reg or "").strip() == "0150":
                dados_0150 = (r.conteudo_json or {}).get("dados") or []
                if len(dados_0150) > 4:
                    cod_part = str(dados_0150[0]).strip()
                    cpf_limpo = "".join(filter(str.isdigit, str(dados_0150[4] or "")))
                    participantes_pf[cod_part] = (len(cpf_limpo) == 11)

        # 1.2) Mapa de Hierarquia: ID do C100 -> COD_PART
        mapa_pai_participante: dict[str, str] = {}
        for r in rows:
            if (r.reg or "").strip() == "C100":
                dados_c100 = (r.conteudo_json or {}).get("dados") or []
                if len(dados_c100) > 2:
                    mapa_pai_participante[str(r.id)] = str(dados_c100[2]).strip()

        # 2) Aplicar Revisões (Merge em memória)
        if aplicar_revisoes:

            logger.info("[DBG LOADER CALL] scanner.py linha 136 | antes carregar_linhas_logicas_com_revisoes")
            linhas = carregar_linhas_logicas_com_revisoes(db, versao_origem_id=int(versao_id))
            logger.info("[DBG LOADER CALL] scanner.py linha 136 | depois | linhas=%s", len(linhas or []))
            rows_agg = linhas_para_rows_like(linhas)  # para agregadores
            fonte_base = linhas  # para DTOs
        else:
            rows_agg = rows
            fonte_base = rows
        scan_report["rows_agg"] = len(rows_agg)
        # --- 2.0 FILTRO POR SITUAÇÃO DO DOCUMENTO (C100 COD_SIT) ---
        # COD_SIT: 06 = complementar / 07 = cancelada
        c100_sit_skip_ids: set[int] = set()

        for r in rows_agg:
            reg_nome = str(getattr(r, "reg", "")).strip().upper()
            if reg_nome != "C100":
                continue

            dados = (getattr(r, "conteudo_json", None) or {}).get("dados") or []
            # no seu padrão: dados[4] = COD_SIT (porque dados[0]=IND_OPER, dados[2]=COD_PART, dados[4]=COD_SIT)
            cod_sit = str(dados[4]).strip() if len(dados) > 4 else ""

            if cod_sit in {"06", "07"}:
                rid_c100 = int(getattr(r, "registro_id", 0) or getattr(r, "id", 0) or 0)
                if rid_c100:
                    c100_sit_skip_ids.add(rid_c100)

        # --- 2.1) FILTRAGEM DE SEGURANÇA (O CORTE PF) ---
        rows_limpas: list[Any] = []
        ids_pf_detectados: set[int] = set()

        c100_pf_ids: set[int] = set()
        for r in rows_agg:
            reg_nome = str(getattr(r, "reg", "")).strip().upper()
            is_pf = False

            if reg_nome == "C100":
                dados = (getattr(r, "conteudo_json", None) or {}).get("dados") or []
                rid_c100 = int(getattr(r, "registro_id", 0) or getattr(r, "id", 0) or 0)

                # ✅ NOVO: corta documento por COD_SIT (complementar/cancelada)
                if rid_c100 and rid_c100 in c100_sit_skip_ids:
                    continue  # não deixa agregadores verem esse C100
                cod_part = str(dados[2]).strip() if len(dados) > 2 else None
                is_pf = participantes_pf.get(cod_part, False)
                if is_pf:
                    if rid_c100:
                        c100_pf_ids.add(rid_c100)
                #  mantém C100 (não-PF) no fluxo normal
                rows_limpas.append(r)
                continue

            elif reg_nome == "C170":
                pai_id = int(getattr(r, "pai_id", 0) or 0)
                #  NOVO: se pai C100 é complementar/cancelado, corta C170
                if pai_id and pai_id in c100_sit_skip_ids:
                    continue

                #  regra de ouro: se pai C100 é PF, corta C170
                if pai_id and pai_id in c100_pf_ids:
                    rid_pf = int(getattr(r, "registro_id", 0) or getattr(r, "id", 0) or 0)
                    if rid_pf:
                        ids_pf_detectados.add(rid_pf)
                    continue
                # fallback antigo...
                id_pai = str(pai_id) if pai_id else str(getattr(r, "pai_id", ""))
                cod_part = mapa_pai_participante.get(id_pai)
                is_pf = participantes_pf.get(cod_part, False)
                if is_pf:
                    rid_pf = int(getattr(r, "registro_id", 0) or getattr(r, "id", 0) or 0)
                    if rid_pf:
                        ids_pf_detectados.add(rid_pf)
                    continue
                rows_limpas.append(r)
                continue

            # outros registros: mantém
            rows_limpas.append(r)

        # --- 2.2 ENRIQUECER rows_like com registro_id real (quando aplicar_revisoes=True) ---
        # Isso garante anchor_registro_id e evita registro_id=0 nos AGGs.

        for r in rows_limpas:
            try:
                linha_r = int(getattr(r, "linha", 0) or 0)
                if linha_r <= 0:
                    continue

                # --- registro_id real (DB) ---
                rid = int(getattr(r, "registro_id", 0) or 0)
                if rid <= 0:
                    rid = int(linha_to_registro_id.get(linha_r, 0) or 0)
                    if rid > 0:
                        setattr(r, "registro_id", rid)

                # --- id real (compat) ---
                rid_id = int(getattr(r, "id", 0) or 0)
                if rid_id <= 0 and rid > 0:
                    setattr(r, "id", rid)

                # ✅ --- pai_id real (o que falta hoje) ---
                pai_atual = int(getattr(r, "pai_id", 0) or 0)
                if pai_atual <= 0:
                    # usa o rid real (registro_id) como chave
                    pai_db = int(rid_to_pai_id.get(int(rid), 0) or 0)
                    if pai_db > 0:
                        setattr(r, "pai_id", pai_db)

            except Exception:
                pass
        scan_report["rows_limpas"] = len(rows_limpas)
        scan_report["pf_bloqueados"] = len(ids_pf_detectados)
        scan_report["c100_sit_skip"] = len(c100_sit_skip_ids)
        # -------------------------------------------------
        # 2.3) Mapa 0200 (COD_ITEM -> NCM) usando fonte_base
        # -------------------------------------------------
        item_to_ncm: dict[str, str] = {}

        for l in fonte_base:
            reg_nome_l = str(getattr(l, "reg", "")).strip().upper()
            if reg_nome_l != "0200":
                continue

            raw_dados_0200 = getattr(l, "dados", None)

            if not raw_dados_0200:
                cj = getattr(l, "conteudo_json", None) or {}
                if isinstance(cj, dict):
                    raw_dados_0200 = cj.get("dados")

            if not raw_dados_0200:
                rj = getattr(l, "revisao_json", None) or {}
                if isinstance(rj, dict):
                    raw_dados_0200 = rj.get("dados")

            dados_0200 = list(raw_dados_0200 or [])
            cod_item = str(dados_0200[0]).strip() if len(dados_0200) > 0 else ""
            ncm_raw = str(dados_0200[6] or "") if len(dados_0200) > 6 else ""
            ncm = "".join(filter(str.isdigit, ncm_raw))

            if cod_item and ncm:
                item_to_ncm[cod_item] = ncm
        # nova implementaçõa para enriquecer o meta com periodo e regime
        versao_ctx = db.get(EfdVersao, versao_id)
        arquivo_ctx = getattr(versao_ctx, "arquivo", None)
        periodo_ctx = str(getattr(arquivo_ctx, "periodo", "") or "").strip() or None

        cod_inc_trib_ctx = None
        regime_apuracao_ctx = None

        for l_ctx in fonte_base:
            if str(getattr(l_ctx, "reg", "") or "").strip().upper() != "0110":
                continue

            dados_0110 = list(getattr(l_ctx, "dados", []) or [])
            if not dados_0110:
                cj = getattr(l_ctx, "conteudo_json", None) or {}
                if isinstance(cj, dict):
                    dados_0110 = list(cj.get("dados") or [])

            cod_inc_trib_ctx = str(dados_0110[0]).strip() if len(dados_0110) > 0 else None
            regime_apuracao_ctx = str(dados_0110[2]).strip() if len(dados_0110) > 2 else None
            break

        dominio = DOM_GERAL
        try:
            versao = db.get(EfdVersao, versao_id)
            if not versao:
                raise ValueError("versao not found")

            # override opcional (se existir a coluna na tabela)
            dom_versao = (getattr(versao, "dominio", None) or "").strip().upper()

            if dom_versao:
                dominio = dom_versao
            else:
                emp = getattr(getattr(versao, "arquivo", None), "empresa", None)
                dom_emp = (getattr(emp, "dominio", None) or "").strip().upper()
                dominio = dom_emp or DOM_GERAL

        except Exception:
            dominio = DOM_GERAL

        if dominio not in DOMINIOS_VALIDOS:
            dominio = DOM_GERAL

        # 3) Converter para DTO (LIMPO E ROBUSTO COM REVISÕES)
        dtos: List[RegistroFiscalDTO] = []

        # COD_SIT: 06 complementar / 07 cancelada
        c100_sit_skip_ids: set[int] = set()
        for l in fonte_base:
            rid_real = int(getattr(l, "registro_id", 0) or 0)
            if rid_real <= 0:
                rid_real = linha_to_registro_id.get(int(getattr(l, "linha", 0) or 0), 0)

            reg_nome = str(getattr(l, "reg", "")).strip().upper()

            is_pessoa_fisica = False
            if reg_nome == "C100":
                if rid_real in c100_pf_ids:
                    is_pessoa_fisica = True
            elif reg_nome == "C170":
                pai_id = int(getattr(l, "pai_id", 0) or 0)
                if pai_id in c100_pf_ids or rid_real in ids_pf_detectados:
                    is_pessoa_fisica = True
            # ✅ DADOS robusto (EfdRegistro e LinhaLogica)
            raw_dados = getattr(l, "dados", None)

            if not raw_dados:
                cj = getattr(l, "conteudo_json", None) or {}
                if isinstance(cj, dict):
                    raw_dados = cj.get("dados")

            if not raw_dados:
                rj = getattr(l, "revisao_json", None) or {}
                if isinstance(rj, dict):
                    raw_dados = rj.get("dados")

            dados_list = list(raw_dados or [])
            # -------------------------------------------------
            # ✅ FILTRO POR SITUAÇÃO DO DOCUMENTO (COD_SIT)
            # - C100 COD_SIT 06/07: ignora documento e marca pai
            # - C170 cujo pai está marcado: ignora item
            # -------------------------------------------------
            if reg_nome == "C100":
                cod_sit = str(dados_list[4]).strip() if len(dados_list) > 4 else ""
                if cod_sit in {"06", "07"}:
                    if rid_real > 0:
                        c100_sit_skip_ids.add(int(rid_real))


            elif reg_nome == "C170":
                pai_id = int(getattr(l, "pai_id", 0) or 0)
                # fallback: se overlay não trouxe pai_id, busca no mapa do DB pelo rid_real
                if pai_id <= 0 and rid_real > 0:
                    pai_id = int(rid_to_pai_id.get(int(rid_real), 0) or 0)

                if pai_id and pai_id in c100_sit_skip_ids:
                    continue  # não cria DTO para item de doc complementar/cancelado

            meta: dict[str, Any] = {}

            if reg_nome == "C170":
                cod_item = str(dados_list[1]).strip() if len(dados_list) > 1 else ""
                ncm = item_to_ncm.get(cod_item)
                if ncm:
                    meta["ncm"] = ncm

                if cod_item:
                    meta["cod_item"] = cod_item

            #enriquecendo o meta
            meta["fonte_base"] = "overlay" if aplicar_revisoes else "original"
            meta["versao_id"] = int(versao_id)
            meta["empresa_id"] = int(empresa_id_ctx)

            # opcional: se quiser rastrear origem
            meta["fonte_base"] = "overlay" if aplicar_revisoes else "original"

            meta["periodo"] = periodo_ctx
            meta["cod_inc_trib"] = cod_inc_trib_ctx
            meta["regime_apuracao"] = regime_apuracao_ctx
            meta["dominio"] = dominio
            meta["dominio_aplicado"] = dominio
            meta["dominio_versao"] = dominio


            dtos.append(
                RegistroFiscalDTO(
                    id=int(rid_real),
                    reg=reg_nome,
                    linha=int(getattr(l, "linha", 0) or 0),
                    dados=dados_list,
                    is_pf=is_pessoa_fisica,
                    versao_id=int(versao_id),
                    empresa_id=int(empresa_id),
                    meta=meta,
                )
            )
            scan_report["dtos_total"] = len(dtos)

        # -----------------------------
        # 4) Injetar META_FISCAL e agregadores (sempre usando rows_limpas)
        # -----------------------------
        cat = None
        try:
            # já existe set_fiscal_context(db, empresa_id_ctx) antes, então:
            cat = carregar_catalogo_fiscal(db, empresa_id=empresa_id_ctx)
        except Exception:
            cat = None

        meta_fiscal = montar_meta_fiscal(rows_limpas, catalogo=cat, debug=False)

        if isinstance(meta_fiscal, RegistroFiscalDTO):
            meta_fiscal.versao_id = versao_id
            meta_fiscal.empresa_id = empresa_id_ctx

            dtos.append(meta_fiscal)
            scan_report["agregadores_criados"].append("META_FISCAL")

        c100_ent = montar_c100_entrada_relevante_agg(rows_limpas)
        if c100_ent:
            aplicar_contexto(c100_ent, versao_id, empresa_id_ctx)
            dtos.append(c100_ent)
            scan_report["agregadores_criados"].append("C100_ENT_AGG")

        c170_saida = montar_c170_saida_agg(rows_limpas)
        if c170_saida:
            aplicar_contexto(c170_saida, versao_id, empresa_id_ctx)
            dtos.append(c170_saida)
            scan_report["agregadores_criados"].append("C170_SAIDA_AGG")

        c170_insumo = montar_c170_insumo_agg(rows_limpas)
        if c170_insumo:
            aplicar_contexto(c170_insumo, versao_id, empresa_id_ctx)

            meta = c170_insumo.meta or {}
            meta.update({
                "dominio": dominio,
                "dominio_aplicado": dominio,
                "empresa_id": empresa_id_ctx,
                "versao_id": versao_id,
                "fonte_base": "C170_INSUMO_AGG",
            })
            c170_insumo.meta = meta

            if c170_insumo.dados and isinstance(c170_insumo.dados[0], dict):
                c170_insumo.dados[0].setdefault("_meta", {})
                c170_insumo.dados[0]["_meta"].update(meta)

            dtos.append(c170_insumo)
            scan_report["agregadores_criados"].append("C170_INSUMO_AGG")

        c170_exp = montar_c170_export_agg(rows_limpas)
        if c170_exp:
            aplicar_contexto(c170_exp, versao_id, empresa_id_ctx)
            dtos.append(c170_exp)
            scan_report["agregadores_criados"].append("C170_EXPORT_AGG")

        c170_ind = montar_c170_ind_torrado_agg(rows_limpas)
        if c170_ind:
            aplicar_contexto(c170_ind, versao_id, empresa_id_ctx)
            dtos.append(c170_ind)
            scan_report["agregadores_criados"].append("C170_IND_AGG")

        # -----------------------------
        # 5) Executar motor fiscal
        # -----------------------------
        for d in dtos:
            if (d.reg or "").strip() == "META_FISCAL":
                logger.debug(
                    "META_FISCAL DTO | versao_id=%s | dados=%s",
                    versao_id,
                    d.dados,
                )
                break

        # -----------------------------
        # 5.1) Cruzamento ICMS/IPI -> DTOs diagnósticos
        # -----------------------------
        try:
            t_cruz_ini = time.perf_counter()

            versao = db.get(EfdVersao, versao_id)
            arquivo = getattr(versao, "arquivo", None)
            periodo = str(getattr(arquivo, "periodo", "") or "").strip() or None if arquivo else None

            t0 = time.perf_counter()
            res_cruz = cruzar_versao_com_icms_ipi(
                db=db,
                versao_origem_id=int(versao_id),
                empresa_id=int(empresa_id_ctx),
                periodo=periodo,
                usar_overlay=aplicar_revisoes,
                aplicar_revisoes_insert=False,
            )
            logger.info(
                "TEMPO SCAN 5.1 | cruzar_versao_com_icms_ipi=%.2fs | docs=%s | itens=%s",
                time.perf_counter() - t0,
                len(res_cruz.get("documentos") or []),
                len(res_cruz.get("itens") or []),
            )

            qtd_cruz_dtos_item = 0
            qtd_cruz_dtos_nf = 0

            # --------------------------------------------------
            # 5.1.1) DTOs diagnósticos de ITEM
            # --------------------------------------------------
            t0 = time.perf_counter()
            dtos_cruz_item: list[RegistroFiscalDTO] = []

            for item in res_cruz.get("itens", []):
                dtos_cruz_item.append(
                    RegistroFiscalDTO(
                        id=int(item.get("registro_id_ancora") or item.get("c170_registro_id") or 0),
                        reg="ICMS_IPI_CRUZAMENTO_ITEM",
                        linha=int(item.get("linha_ancora") or item.get("c170_linha") or 0),
                        dados=[],
                        is_pf=False,
                        versao_id=int(versao_id),
                        empresa_id=int(empresa_id_ctx),
                        meta={
                            "origem": "ICMS_IPI_CRUZAMENTO",
                            **item,
                        },
                    )
                )

            logger.info(
                "TEMPO SCAN 5.1.1 | montar DTOs item=%.2fs | dtos_brutos=%s",
                time.perf_counter() - t0,
                len(dtos_cruz_item),
            )

            t0 = time.perf_counter()
            dtos_cruz_item = filtrar_apontamentos_contrib_sem_c170(
                db,
                versao_id=int(versao_id),
                candidatos=dtos_cruz_item,
            )
            logger.info(
                "TEMPO SCAN 5.1.1 | filtrar CONTRIB_SEM_C170=%.2fs | dtos_filtrados=%s",
                time.perf_counter() - t0,
                len(dtos_cruz_item),
            )

            t0 = time.perf_counter()
            dtos.extend(dtos_cruz_item)
            qtd_cruz_dtos_item += len(dtos_cruz_item)
            logger.info(
                "TEMPO SCAN 5.1.1 | extend dtos=%.2fs | dtos_total_agora=%s",
                time.perf_counter() - t0,
                len(dtos),
            )

            if qtd_cruz_dtos_item:
                scan_report["agregadores_criados"].append("ICMS_IPI_CRUZAMENTO_ITEM")
                logger.info(
                    "SCAN cruzamento ICMS/IPI ITEM | versao_id=%s | dtos_item=%s",
                    versao_id,
                    qtd_cruz_dtos_item,
                )

            # --------------------------------------------------
            # 5.1.2) DTOs diagnósticos de D100
            # --------------------------------------------------
            try:
                if dominio != "TRANSP":
                    logger.info(
                        "SCAN D100 ignorado | versao_id=%s | dominio=%s",
                        versao_id,
                        dominio,
                    )
                else:
                    lista_d100_icms = carregar_d100_icms(
                        db,
                        empresa_id=int(empresa_id_ctx),
                        periodo=periodo,
                    )

                    logger.info(
                        "SCAN D100 carregados | versao_id=%s | qtd=%s",
                        versao_id,
                        len(lista_d100_icms or []),
                    )

                    dtos_cruz_d100 = cruzar_d100_icms_com_contribuicoes(
                        dtos_icms=lista_d100_icms,
                        versao_id=int(versao_id),
                        empresa_id=int(empresa_id_ctx),
                        dominio=dominio,
                    )

                    if dtos_cruz_d100:
                        dtos.extend(dtos_cruz_d100)
                        scan_report["agregadores_criados"].append("ICMS_IPI_CRUZAMENTO_D100")

                        logger.info(
                            "SCAN cruzamento ICMS/IPI D100 | versao_id=%s | dtos_d100=%s",
                            versao_id,
                            len(dtos_cruz_d100),
                        )

            except Exception as e_d100:
                logger.warning(
                    "SCAN cruzamento ICMS/IPI D100 falhou | versao_id=%s | erro=%s",
                    versao_id,
                    e_d100,
                )

            # --------------------------------------------------
            # 5.1.3) DTOs diagnósticos de NF ausente no C100
            # --------------------------------------------------
            try:
                notas_faltantes = listar_c100_ausentes(
                    db,
                    versao_origem_id=int(versao_id),
                    empresa_id=int(empresa_id_ctx),
                    periodo=periodo,
                    # filtro_item_extra=seu_filtro_cpc_aqui,  # ligar depois, se quiser
                )

                # monta mapa 0200 uma vez
                map_0200: dict[str, dict[str, str]] = {}

                for linha in linhas:
                    if str(getattr(linha, "reg", "") or "").strip().upper() != "0200":
                        continue

                    dados_0200 = list(getattr(linha, "dados", []) or [])
                    cod_item_0200 = str(dados_0200[0] if len(dados_0200) > 0 else "").strip()
                    descr_0200 = str(dados_0200[1] if len(dados_0200) > 1 else "").strip()
                    ncm_0200 = str(dados_0200[6] if len(dados_0200) > 6 else "").strip()

                    if cod_item_0200:
                        map_0200[cod_item_0200] = {
                            "descricao": descr_0200,
                            "ncm": ncm_0200,
                        }

                # mapas de âncora
                map_0200_ancora: dict[str, tuple[int, int]] = {}
                map_0150_ancora: dict[str, tuple[int, int]] = {}
                ancora_0000: tuple[int, int] | None = None

                for linha in linhas:
                    reg = str(getattr(linha, "reg", "") or "").strip().upper()
                    dados = list(getattr(linha, "dados", []) or [])
                    registro_id = int(getattr(linha, "registro_id", 0) or 0)
                    linha_num = int(getattr(linha, "linha", 0) or 0)

                    if reg == "0000" and registro_id > 0 and ancora_0000 is None:
                        ancora_0000 = (registro_id, linha_num)

                    elif reg == "0200":
                        cod_item = str(dados[0] if len(dados) > 0 else "").strip()
                        if cod_item and registro_id > 0:
                            map_0200_ancora[cod_item] = (registro_id, linha_num)

                    elif reg == "0150":
                        cod_part = str(dados[0] if len(dados) > 0 else "").strip()
                        if cod_part and registro_id > 0:
                            map_0150_ancora[cod_part] = (registro_id, linha_num)

                for nf in notas_faltantes:
                    itens_ctx = list(nf.get("itens_contexto") or [])
                    itens_ctx_enriquecidos = []

                    for item in itens_ctx:
                        cod_item = str(item.get("cod_item") or "").strip()
                        ref_0200 = map_0200.get(cod_item, {})

                        novo_item = {
                            **item,
                            "descricao": str(item.get("descricao") or ref_0200.get("descricao") or "").strip(),
                            "ncm": str(item.get("ncm") or ref_0200.get("ncm") or "").strip(),
                        }
                        itens_ctx_enriquecidos.append(novo_item)

                    nf["itens_contexto"] = itens_ctx_enriquecidos

                    # opcional: recalcular listas derivadas
                    nf["ncms"] = sorted({
                        str(it.get("ncm") or "").strip()
                        for it in itens_ctx_enriquecidos
                        if str(it.get("ncm") or "").strip()
                    })
                    nf["descricoes_itens"] = [
                        str(it.get("descricao") or "").strip()
                        for it in itens_ctx_enriquecidos
                    ]

                    # --------------------------------------------------
                    # NOVO: resolver âncora real do DTO
                    # --------------------------------------------------
                    registro_id_ancora = None
                    linha_ancora = 0

                    # 1) tenta por 0200 dos itens
                    for item in itens_ctx_enriquecidos:
                        cod_item = str(item.get("cod_item") or "").strip()
                        anc = map_0200_ancora.get(cod_item)
                        if anc:
                            registro_id_ancora, linha_ancora = anc
                            break

                    # 2) tenta por 0150 do participante
                    if not registro_id_ancora:
                        cod_part_nf = str(nf.get("cod_part") or "").strip()
                        anc = map_0150_ancora.get(cod_part_nf)
                        if anc:
                            registro_id_ancora, linha_ancora = anc

                    # 3) fallback no 0000
                    if not registro_id_ancora and ancora_0000:
                        registro_id_ancora, linha_ancora = ancora_0000

                    nf["registro_id_ancora"] = registro_id_ancora
                    nf["linha_ancora"] = linha_ancora

                    cod_mod_nf = nf.get("cod_mod") or nf.get("modelo") or "55"
                    num_doc_nf = nf.get("num_doc") or nf.get("numero") or nf.get("nro_doc") or ""
                    dtos.append(
                        RegistroFiscalDTO(
                            id=int(nf.get("registro_id_ancora") or 0),
                            reg="ICMS_IPI_CRUZAMENTO_NF",
                            linha=int(nf.get("linha_ancora") or 0),
                            dados=[],
                            is_pf=False,
                            versao_id=int(versao_id),
                            empresa_id=int(empresa_id_ctx),
                            meta={
                                **nf,
                                "origem": "ICMS_IPI_CRUZAMENTO",
                                "dominio": dominio,
                                "versao_id": int(versao_id),
                                "empresa_id": int(empresa_id_ctx),
                                "cod_mod": str(cod_mod_nf),
                                "num_doc": str(num_doc_nf),

                            },
                        )
                    )
                    qtd_cruz_dtos_nf += 1

                if qtd_cruz_dtos_nf:
                    scan_report["agregadores_criados"].append("ICMS_IPI_CRUZAMENTO_NF")
                    logger.info(
                        "SCAN cruzamento ICMS/IPI NF | versao_id=%s | dtos_nf=%s",
                        versao_id,
                        qtd_cruz_dtos_nf,
                    )

            except Exception as e_nf:
                logger.warning(
                    "SCAN cruzamento ICMS/IPI NF falhou | versao_id=%s | erro=%s",
                    versao_id,
                    e_nf,
                )

            if qtd_cruz_dtos_item or qtd_cruz_dtos_nf:
                logger.info(
                    "SCAN cruzamento ICMS/IPI resumo | versao_id=%s | dtos_item=%s | dtos_nf=%s | total=%s",
                    versao_id,
                    qtd_cruz_dtos_item,
                    qtd_cruz_dtos_nf,
                    qtd_cruz_dtos_item + qtd_cruz_dtos_nf,
                )

        except Exception as e:
            logger.warning(
                "SCAN cruzamento ICMS/IPI falhou | versao_id=%s | erro=%s",
                versao_id,
                e,
            )

            # Varredura
        result = executar_varredura(dtos, capturar_erros=True, dominio=dominio)

        # Consolidando os apontamentos em apenas um no front
        result.apontamentos = consolidar_apontamentos_contrib_sem_c100(result.apontamentos)
        result.apontamentos = consolidar_apontamentos_contrib_sem_c170(result.apontamentos)


        for e in result.erros:
            print("[DBG ERRO_REGRA]", e, flush=True)

        logger.info(
            "SCAN varredura concluída | versao_id=%s | dominio=%s | apontamentos_brutos=%s | erros_regras=%s",
            versao_id,
            dominio,
            len(result.apontamentos),
            len(result.erros),
        )

                # -----------------------------
        # 6) Limpeza profissional (apaga pendentes e preserva resolvidos se solicitado)
        # -----------------------------
        q_del = db.query(EfdApontamento).filter(EfdApontamento.versao_id == versao_id)
        if preservar_resolvidos:
            q_del = q_del.filter(EfdApontamento.resolvido == False)  # noqa: E712
        q_del.delete(synchronize_session=False)

        existing_resolved: Dict[Tuple[int, str, str], EfdApontamento] = {}
        if preservar_resolvidos:
            resolved_rows: List[EfdApontamento] = (
                db.query(EfdApontamento)
                .filter(
                    EfdApontamento.versao_id == versao_id,
                    EfdApontamento.resolvido == True,  # noqa: E712
                )
                .all()
            )
            for ap in resolved_rows:
                existing_resolved[key_apontamento(ap.registro_id, ap.tipo, ap.codigo)] = ap


        consolidar_achados_c170_insumo_v2(result)
        consolidar_achados_cfop_sem_credito_v1(result)
        consolidar_achados_transp_cred_pres_v1(result)
        consolidar_achados_comb_lc192_v1(result)

        # -----------------------------
        # 7) Inserir/atualizar apontamentos
        # -----------------------------
        tem_cafe = any(norm_codigo(x.codigo) == "CAFE_C190_V1" for x in result.apontamentos)

        to_insert: List[EfdApontamento] = []
        to_update_mappings: List[dict] = []

        descartados_sem_fk = 0

        for a in result.apontamentos:
            rid = None
            if getattr(a, "registro_id", None) is not None:
                try:
                    rid = int(a.registro_id)
                except Exception:
                    rid = None

            raw_meta = getattr(a, "meta", None) or {}
            meta = dict(raw_meta) if isinstance(raw_meta, dict) else {}

            tipo = str(getattr(a, "tipo", "") or "").strip() or "OPORTUNIDADE"
            codigo_norm = norm_codigo(getattr(a, "codigo", None)) or None
            descricao = str(getattr(a, "descricao", "") or "").strip()
            impacto = getattr(a, "impacto_financeiro", None)

            # fallback: tenta resolver pelo meta["linha"]
            if not rid or rid <= 0:
                linha_meta = meta.get("linha") or meta.get("linha_num") or meta.get("linha_referencia")
                try:
                    linha_i = int(linha_meta) if linha_meta is not None else None
                except Exception:
                    linha_i = None
                if linha_i is not None:
                    rid = linha_to_registro_id.get(linha_i)

            # fallback: ancora no primeiro C170 da versão se tiver fonte_base
            if not rid:
                fonte_base = meta.get("fonte_base") or meta.get("fonte")
                if fonte_base:
                    rid = next((int(r.id) for r in rows if (r.reg or "").strip().upper() == "C170"), None)

            if not rid:
                descartados_sem_fk += 1
                logger.warning(
                    "DESCARTADO sem FK | codigo=%s | tipo=%s | fonte=%s",
                    codigo_norm,
                    tipo,
                    meta.get("fonte_base") or meta.get("fonte"),
                )
                continue

            prio_regra = norm_prioridade(getattr(a, "prioridade", None))
            prioridade = prio_regra or prioridade_por_impacto(impacto) or "BAIXA"

            k = key_apontamento(rid, tipo, codigo_norm)

            if preservar_resolvidos and k in existing_resolved:
                ap_exist = existing_resolved[k]
                to_update_mappings.append(
                    {
                        "id": ap_exist.id,
                        "descricao": descricao,
                        "impacto_financeiro": safe_float(impacto),
                        "prioridade": prioridade,
                        "meta_json": meta,
                    }
                )
                continue

            to_insert.append(
                EfdApontamento(
                    versao_id=versao_id,
                    registro_id=rid,
                    tipo=tipo,
                    codigo=codigo_norm,
                    descricao=descricao,
                    impacto_financeiro=safe_float(impacto),
                    prioridade=prioridade,
                    resolvido=False,
                    meta_json=_safe_json(meta),
                )
            )

        if to_update_mappings:
            db.bulk_update_mappings(EfdApontamento, to_update_mappings)

        if to_insert:
            db.bulk_save_objects(to_insert)

        logger.warning(
            "SCAN descartes sem FK | versao_id=%s | descartados_sem_fk=%s",
            versao_id,
            descartados_sem_fk,
        )
        # -----------------------------
        # retorno final (telemetria)
        # -----------------------------
        total_c170_processados = len([d for d in dtos if d.reg == "C170" and not getattr(d, "is_pf", False)])

        scan_report["dtos_c170"] = len(
            [d for d in dtos if d.reg == "C170" and not getattr(d, "is_pf", False)]
        )

        logger.info(
            "SCAN resumo | versao_id=%s | rows_base=%s | rows_agg=%s | rows_limpas=%s | dtos_total=%s | c170_processados=%s | apontamentos_gerados=%s | atualizados_preservados=%s | descartados_sem_fk=%s",
            versao_id,
            scan_report["rows_base"],
            scan_report["rows_agg"],
            scan_report["rows_limpas"],
            scan_report["dtos_total"],
            scan_report["dtos_c170"],
            len(to_insert),
            len(to_update_mappings),
            descartados_sem_fk,
        )
        return {
            "apontamentos_gerados": len(to_insert),
            "erros_regras": result.erros,
            "atualizados_preservados": len(to_update_mappings),
            "descartados_sem_fk": int(descartados_sem_fk),
            "total_c170_processados": int(total_c170_processados),
            "relatorio": scan_report,
        }