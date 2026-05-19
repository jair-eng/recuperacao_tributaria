from __future__ import annotations

from typing import Any, Dict, List
from sqlalchemy.orm import Session

from app.db.models import EfdRevisao
from app.db.models.nf_icms_item import NfIcmsItem
from app.Legacy.fiscal.constants import DOM_GERAL
from app.icms_ipi.icms_c170_utils import montar_linha_c170_de_icms
import logging

from app.services.dominio_service import resolver_dominio_por_versao

logger = logging.getLogger(__name__)


def inserir_bloco_c170s_para_c100_existente(
    db: Session,
    *,
    versao_origem_id: int,
    registro_id_c100: int,
    linha_c100: int,
    itens: List[NfIcmsItem],
    apontamento_id: int | None = None,
    motivo_codigo: str = "CONTRIB_SEM_C170_V1",
    contexto: str | None = None,
    fator_base_credito: float | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
) -> Dict[str, Any]:
    """
    Cria UMA única revisão contendo todas as linhas C170 faltantes da nota.
    Evita colisão de múltiplos INSERT_AFTER no mesmo RID do C100.
    """
    linhas_novas: list[str] = []
    dominio = resolver_dominio_por_versao(db, versao_origem_id) or DOM_GERAL

    for it in itens:
        linha_nova = montar_linha_c170_de_icms(
            it,
            dominio=dominio,
            contexto=contexto,
            fator_base_credito=fator_base_credito,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
        )
        linhas_novas.append(linha_nova)

    if not linhas_novas:
        return {
            "total_inseridos": 0,
            "revisao_id": None,
        }

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=int(registro_id_c100),
        reg="C170",
        acao="INSERT_AFTER",
        revisao_json={
            "linhas_novas": linhas_novas,   # 🔥 bloco inteiro
            "linha_referencia": int(linha_c100),
            "nf_icms_item_ids": [int(it.id) for it in itens],
            "origem": "ICMS_IPI",
            "modo": "BLOCO_C170",
            "contexto": contexto,
            "fator_base_credito": fator_base_credito,
            "aliq_pis": aliq_pis,
            "aliq_cofins": aliq_cofins,
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=int(apontamento_id) if apontamento_id else None,
    )

    db.add(rv)
    db.flush()

    logger.info(
        "[C170_BLOCO] revisão criada | rv_id=%s | versao=%s | c100_id=%s | linha_ref=%s | total_linhas=%s | contexto=%s",
        rv.id,
        versao_origem_id,
        registro_id_c100,
        linha_c100,
        len(linhas_novas),
        contexto,
    )

    return {
        "total_inseridos": len(linhas_novas),
        "revisao_id": int(rv.id),
    }

def inserir_bloco_c170s_para_c100_existente_manual(
    db: Session,
    *,
    versao_origem_id: int,
    registro_id_c100: int,
    linha_c100: int,
    itens: List[NfIcmsItem],
    apontamento_id: int | None = None,
    motivo_codigo: str = "CONTRIB_SEM_C170_MANUAL_V1",
    contexto: str | None = None,
    fator_base_credito: float | None = None,
    aliq_pis: str | None = None,
    aliq_cofins: str | None = None,
) -> Dict[str, Any]:
    """
    Versão MANUAL da inserção em bloco de C170.
    Mantém o fluxo estrutural da função padrão, mas permite
    montar as linhas com parametrização fiscal específica
    (ex.: combustível presumido).
    """
    linhas_novas: list[str] = []
    dominio = resolver_dominio_por_versao(db, versao_origem_id) or DOM_GERAL

    for it in itens:
        linha_nova = montar_linha_c170_de_icms(
            it,
            dominio=dominio,
            contexto=contexto,
            fator_base_credito=fator_base_credito,
            aliq_pis=aliq_pis,
            aliq_cofins=aliq_cofins,
        )
        linhas_novas.append(linha_nova)

    if not linhas_novas:
        return {
            "total_inseridos": 0,
            "revisao_id": None,
        }

    rv = EfdRevisao(
        versao_origem_id=int(versao_origem_id),
        versao_revisada_id=None,
        registro_id=int(registro_id_c100),
        reg="C170",
        acao="INSERT_AFTER",
        revisao_json={
            "linhas_novas": linhas_novas,
            "linha_referencia": int(linha_c100),
            "nf_icms_item_ids": [int(it.id) for it in itens],
            "origem": "ICMS_IPI",
            "modo": "BLOCO_C170_MANUAL",
            "contexto": contexto,
            "fator_base_credito": fator_base_credito,
            "aliq_pis": aliq_pis,
            "aliq_cofins": aliq_cofins,
        },
        motivo_codigo=motivo_codigo,
        apontamento_id=int(apontamento_id) if apontamento_id else None,
    )

    db.add(rv)
    db.flush()

    logger.info(
        "[C170_BLOCO_MANUAL] revisão criada | rv_id=%s | versao=%s | c100_id=%s | linha_ref=%s | total_linhas=%s | contexto=%s | fator=%s",
        rv.id,
        versao_origem_id,
        registro_id_c100,
        linha_c100,
        len(linhas_novas),
        contexto,
        fator_base_credito,
    )

    return {
        "total_inseridos": len(linhas_novas),
        "revisao_id": int(rv.id),
    }