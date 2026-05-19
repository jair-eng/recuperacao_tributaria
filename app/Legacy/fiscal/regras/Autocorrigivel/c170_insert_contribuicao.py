from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session

from app.db.models.nf_icms_item import NfIcmsItem
from app.legacy_service.versao_overlay_service import carregar_linhas_logicas_com_revisoes_e_insert
from app.sped.blocoC.c100_utils import (patch_c100_totais_imposto,salvar_revisao_c100_automatica,)
from app.sped.blocoC.c170_helpers import inserir_bloco_c170s_para_c100_existente, \
    inserir_bloco_c170s_para_c100_existente_manual
from app.sped.blocoC.c170_utils import _parse_linha_sped_to_reg_dados
import logging
from app.sped.logic.consolidador import calcular_totais_filhos_overlay_por_registro_c100, obter_conteudo_final

logger = logging.getLogger(__name__)


def aplicar_correcao_c170_insert_contribuicao(
    db: Session,
    *,
    versao_origem_id: int,
    apontamento_id: int | None = None,
    nf_icms_item_id: int | None = None,
    nf_icms_item_ids: list[int] | None = None,
    linha_c100: int | None = None,
    registro_id_c100: int | None = None,
    linha_ancora: int | None = None,
    registro_id_ancora: int | None = None,
    motivo_codigo: str = "CONTRIB_SEM_C170_V1",
    contexto: str | None = None,
    fator_base_credito: float | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
) -> Dict[str, Any]:
    """
    Fluxo:
    1) resolve C100 alvo
    2) cria UMA revisão em bloco com todos os C170 faltantes da nota
    3) recarrega overlay
    4) recalcula VL_PIS/VL_COFINS do C100 pai
    5) salva revisão automática do C100
    """
    try:
        registro_id_c100_final = int(registro_id_c100 or registro_id_ancora or 0)
        linha_c100_final = int(linha_c100 or linha_ancora or 0)

        item_ids: list[int] = []
        if nf_icms_item_ids:
            vistos = set()
            for x in nf_icms_item_ids:
                iid = int(x or 0)
                if iid > 0 and iid not in vistos:
                    vistos.add(iid)
                    item_ids.append(iid)
        elif nf_icms_item_id:
            iid = int(nf_icms_item_id or 0)
            if iid > 0:
                item_ids = [iid]

        if not item_ids:
            return {
                "status": "skip",
                "msg": "nf_icms_item_id(s) ausente(s)",
                "insert_criado": 0,
                "c100_recalculado": 0,
            }

        if not registro_id_c100_final:
            return {
                "status": "skip",
                "msg": "registro_id_c100/registro_id_ancora ausente",
                "insert_criado": 0,
                "c100_recalculado": 0,
            }

        if not linha_c100_final:
            return {
                "status": "skip",
                "msg": "linha_c100/linha_ancora ausente",
                "insert_criado": 0,
                "c100_recalculado": 0,
            }

        itens_icms = (
            db.query(NfIcmsItem)
            .filter(NfIcmsItem.id.in_(item_ids))
            .all()
        )
        itens_por_id = {int(x.id): x for x in itens_icms}
        itens_ordenados = [itens_por_id[i] for i in item_ids if i in itens_por_id]

        if not itens_ordenados:
            return {
                "status": "skip",
                "msg": "item_icms não encontrado",
                "insert_criado": 0,
                "c100_recalculado": 0,
                "registro_id_c100": registro_id_c100_final,
            }

        # =========================================================
        # NOVO MODELO: UMA ÚNICA REVISÃO COM BLOCO DE C170
        # =========================================================
        res_bloco = inserir_bloco_c170s_para_c100_existente(
            db,
            versao_origem_id=int(versao_origem_id),
            registro_id_c100=int(registro_id_c100_final),
            linha_c100=int(linha_c100_final),
            itens=itens_ordenados,
            apontamento_id=int(apontamento_id) if apontamento_id else None,
            motivo_codigo=motivo_codigo,
            contexto=contexto,
            fator_base_credito=fator_base_credito,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
        )

        total_inserts = int(res_bloco.get("total_inseridos") or 0)
        if total_inserts <= 0:
            return {
                "status": "skip",
                "msg": "nenhum bloco C170 criado",
                "insert_criado": 0,
                "c100_recalculado": 0,
                "registro_id_c100": registro_id_c100_final,
            }

        db.flush()

        # =========================================================
        # 🔹 RECARREGA OVERLAY
        # =========================================================
        linhas = carregar_linhas_logicas_com_revisoes_e_insert(
            db=db,
            versao_origem_id=int(versao_origem_id),
            versao_final_id=None,
        )

        linha_c100_logica = next(
            (
                ln for ln in linhas
                if str(getattr(ln, "reg", "")).upper() == "C100"
                and int(getattr(ln, "registro_id", 0) or 0) == int(registro_id_c100_final)
            ),
            None,
        )

        if not linha_c100_logica:
            candidatos = sorted(
                linhas,
                key=lambda x: int(getattr(x, "linha", 0) or 0)
            )

            linha_ref = int(linha_c100_final or 0)

            c100_anterior = None
            for ln in candidatos:
                ln_linha = int(getattr(ln, "linha", 0) or 0)
                ln_reg = str(getattr(ln, "reg", "") or "").upper()

                if ln_linha > linha_ref:
                    break

                if ln_reg == "C100":
                    c100_anterior = ln

            if c100_anterior:
                linha_c100_logica = c100_anterior
                registro_id_c100_final = int(getattr(c100_anterior, "registro_id", 0) or 0)
                linha_c100_final = int(getattr(c100_anterior, "linha", 0) or 0)

                logger.warning(
                    "[C170_INSERT_CONTRIBUICAO] C100 corrigido por fallback | novo_c100_id=%s linha=%s",
                    registro_id_c100_final,
                    linha_c100_final,
                )

        conteudo_c100 = obter_conteudo_final(linha_c100_logica) or ""
        reg, dados = _parse_linha_sped_to_reg_dados(conteudo_c100)

        if reg != "C100":
            return {
                "status": "erro",
                "insert_criado": total_inserts,
                "c100_recalculado": 0,
                "registro_id_c100": registro_id_c100_final,
                "msg": f"registro pai no overlay não é C100: {reg}",
            }

        total_pis, total_cofins = calcular_totais_filhos_overlay_por_registro_c100(
            db,
            versao_origem_id=int(versao_origem_id),
            versao_final_id=None,
            registro_c100_id=int(registro_id_c100_final),
        )

        novos_dados = patch_c100_totais_imposto(
            dados,
            float(total_pis),
            float(total_cofins),
        )

        salvar_revisao_c100_automatica(
            db,
            versao_origem_id=int(versao_origem_id),
            motivo_codigo=motivo_codigo,
            c100_id=int(registro_id_c100_final),
            novos_dados=novos_dados,
            apontamento_id=int(apontamento_id) if apontamento_id else None,
        )

        db.flush()

        logger.info(
            "[C170_INSERT_CONTRIBUICAO] OK | versao_id=%s | c100_id=%s | linha_c100=%s | inserts=%s | total_pis=%s | total_cofins=%s",
            versao_origem_id,
            registro_id_c100_final,
            linha_c100_final,
            total_inserts,
            total_pis,
            total_cofins,
        )

        return {
            "status": "ok",
            "insert_criado": total_inserts,
            "c100_recalculado": 1,
            "registro_id_c100": int(registro_id_c100_final),
            "linha_c100": int(linha_c100_final),
            "nf_icms_item_ids": [int(x.id) for x in itens_ordenados],
            "total_pis": str(total_pis),
            "total_cofins": str(total_cofins),
            "msg": f"{total_inserts} C170 inserido(s) em bloco e C100 recalculado com sucesso",
        }

    except Exception as e:
        logger.exception(
            "[C170_INSERT_CONTRIBUICAO] ERRO | versao_id=%s | apontamento_id=%s | registro_id_c100=%s | linha_c100=%s | erro=%s",
            versao_origem_id,
            apontamento_id,
            registro_id_c100,
            linha_c100,
            e,
        )
        return {
            "status": "erro",
            "insert_criado": 0,
            "c100_recalculado": 0,
            "registro_id_c100": int(registro_id_c100 or registro_id_ancora or 0),
            "linha_c100": int(linha_c100 or linha_ancora or 0),
            "nf_icms_item_id": nf_icms_item_id,
            "msg": str(e),
        }

# Essa funcao e para correcao manual

def aplicar_correcao_c170_insert_contribuicao_manual(
    db: Session,
    *,
    versao_origem_id: int,
    apontamento_id: int | None = None,
    nf_icms_item_id: int | None = None,
    nf_icms_item_ids: list[int] | None = None,
    linha_c100: int | None = None,
    registro_id_c100: int | None = None,
    linha_ancora: int | None = None,
    registro_id_ancora: int | None = None,
    motivo_codigo: str = "CONTRIB_SEM_C170_MANUAL_V1",
    contexto: str | None = None,
    fator_base_credito: float | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
) -> Dict[str, Any]:
    """
    Fluxo MANUAL:
    1) resolve C100 alvo
    2) cria UMA revisão em bloco com todos os C170 faltantes da nota
       usando o inseridor manual parametrizado
    3) recarrega overlay
    4) recalcula VL_PIS/VL_COFINS do C100 pai
    5) salva revisão automática do C100
    """
    try:
        registro_id_c100_final = int(registro_id_c100 or registro_id_ancora or 0)
        linha_c100_final = int(linha_c100 or linha_ancora or 0)

        item_ids: list[int] = []
        if nf_icms_item_ids:
            vistos = set()
            for x in nf_icms_item_ids:
                iid = int(x or 0)
                if iid > 0 and iid not in vistos:
                    vistos.add(iid)
                    item_ids.append(iid)
        elif nf_icms_item_id:
            iid = int(nf_icms_item_id or 0)
            if iid > 0:
                item_ids = [iid]

        if not item_ids:
            return {
                "status": "skip",
                "msg": "nf_icms_item_id(s) ausente(s)",
                "insert_criado": 0,
                "c100_recalculado": 0,
            }

        if not registro_id_c100_final:
            return {
                "status": "skip",
                "msg": "registro_id_c100/registro_id_ancora ausente",
                "insert_criado": 0,
                "c100_recalculado": 0,
            }

        if not linha_c100_final:
            return {
                "status": "skip",
                "msg": "linha_c100/linha_ancora ausente",
                "insert_criado": 0,
                "c100_recalculado": 0,
            }

        itens_icms = (
            db.query(NfIcmsItem)
            .filter(NfIcmsItem.id.in_(item_ids))
            .all()
        )
        itens_por_id = {int(x.id): x for x in itens_icms}
        itens_ordenados = [itens_por_id[i] for i in item_ids if i in itens_por_id]

        if not itens_ordenados:
            return {
                "status": "skip",
                "msg": "item_icms não encontrado",
                "insert_criado": 0,
                "c100_recalculado": 0,
                "registro_id_c100": registro_id_c100_final,
            }

        res_bloco = inserir_bloco_c170s_para_c100_existente_manual(
            db,
            versao_origem_id=int(versao_origem_id),
            registro_id_c100=int(registro_id_c100_final),
            linha_c100=int(linha_c100_final),
            itens=itens_ordenados,
            apontamento_id=int(apontamento_id) if apontamento_id else None,
            motivo_codigo=motivo_codigo,
            contexto=contexto,
            fator_base_credito=fator_base_credito,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
        )

        total_inserts = int(res_bloco.get("total_inseridos") or 0)
        if total_inserts <= 0:
            return {
                "status": "skip",
                "msg": "nenhum bloco C170 manual criado",
                "insert_criado": 0,
                "c100_recalculado": 0,
                "registro_id_c100": registro_id_c100_final,
            }

        db.flush()

        linhas = carregar_linhas_logicas_com_revisoes_e_insert(
            db=db,
            versao_origem_id=int(versao_origem_id),
            versao_final_id=None,
        )

        linha_c100_logica = next(
            (
                ln for ln in linhas
                if str(getattr(ln, "reg", "")).upper() == "C100"
                and int(getattr(ln, "registro_id", 0) or 0) == int(registro_id_c100_final)
            ),
            None,
        )

        if not linha_c100_logica:
            return {
                "status": "erro",
                "insert_criado": total_inserts,
                "c100_recalculado": 0,
                "registro_id_c100": registro_id_c100_final,
                "msg": "C100 pai não encontrado no overlay",
            }

        conteudo_c100 = obter_conteudo_final(linha_c100_logica) or ""
        reg, dados = _parse_linha_sped_to_reg_dados(conteudo_c100)

        if reg != "C100":
            return {
                "status": "erro",
                "insert_criado": total_inserts,
                "c100_recalculado": 0,
                "registro_id_c100": registro_id_c100_final,
                "msg": f"registro pai no overlay não é C100: {reg}",
            }

        total_pis, total_cofins = calcular_totais_filhos_overlay_por_registro_c100(
            db,
            versao_origem_id=int(versao_origem_id),
            versao_final_id=None,
            registro_c100_id=int(registro_id_c100_final),
        )

        novos_dados = patch_c100_totais_imposto(
            dados,
            float(total_pis),
            float(total_cofins),
        )

        salvar_revisao_c100_automatica(
            db,
            versao_origem_id=int(versao_origem_id),
            motivo_codigo=motivo_codigo,
            c100_id=int(registro_id_c100_final),
            novos_dados=novos_dados,
            apontamento_id=int(apontamento_id) if apontamento_id else None,
        )

        db.flush()

        logger.info(
            "[C170_INSERT_CONTRIBUICAO_MANUAL] OK | versao_id=%s | c100_id=%s | linha_c100=%s | inserts=%s | total_pis=%s | total_cofins=%s | contexto=%s | fator=%s",
            versao_origem_id,
            registro_id_c100_final,
            linha_c100_final,
            total_inserts,
            total_pis,
            total_cofins,
            contexto,
            fator_base_credito,
        )

        return {
            "status": "ok",
            "insert_criado": total_inserts,
            "c100_recalculado": 1,
            "registro_id_c100": int(registro_id_c100_final),
            "linha_c100": int(linha_c100_final),
            "nf_icms_item_ids": [int(x.id) for x in itens_ordenados],
            "total_pis": str(total_pis),
            "total_cofins": str(total_cofins),
            "msg": f"{total_inserts} C170 manual(is) inserido(s) em bloco e C100 recalculado com sucesso",
        }

    except Exception as e:
        logger.exception(
            "[C170_INSERT_CONTRIBUICAO_MANUAL] ERRO | versao_id=%s | apontamento_id=%s | registro_id_c100=%s | linha_c100=%s | erro=%s",
            versao_origem_id,
            apontamento_id,
            registro_id_c100,
            linha_c100,
            e,
        )
        return {
            "status": "erro",
            "insert_criado": 0,
            "c100_recalculado": 0,
            "registro_id_c100": int(registro_id_c100 or registro_id_ancora or 0),
            "linha_c100": int(linha_c100 or linha_ancora or 0),
            "nf_icms_item_id": nf_icms_item_id,
            "msg": str(e),
        }