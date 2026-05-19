from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.Legacy.fiscal.regras.Autocorrigivel.c170_insert_contribuicao import \
    aplicar_correcao_c170_insert_contribuicao_manual
from app.legacy_service.c170_service import revisar_c170_lote
import logging

logger = logging.getLogger(__name__)


def aplicar_correcao_combustivel_c170_manual(
    db: Session,
    *,
    versao_origem_id: int,
    itens: List[Dict[str, Any]],
    apontamento_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Corretiva manual de C170 para combustíveis (presumido).

    Estratégia:
    - CST 51 (crédito presumido)
    - base reduzida (75%)
    - alíquotas cheias (1,65 / 7,60)

    Entrada esperada:
    - itens: lista com pelo menos {"registro_id": int}
    """

    lote: List[Dict[str, Any]] = []

    for item in itens:
        registro_id = item.get("registro_id")
        if not registro_id:
            continue

        lote.append({
            "registro_id": int(registro_id),

            # não mexer em CFOP agora
            "cfop": None,

            # crédito presumido
            "cst_pis": "51",
            "cst_cofins": "51",

            #  novo comportamento
            "fator_base_credito": 0.75,
            "aliq_pis": "1,6500",
            "aliq_cofins": "7,6000",
            "contexto": "COMBUSTIVEL",
        })

    if not lote:
        return {
            "status": "vazio",
            "msg": "Nenhum item válido para correção.",
        }

    # chama motor já validado
    resultado = revisar_c170_lote(
        db,
        versao_origem_id=int(versao_origem_id),
        alteracoes=lote,
        motivo_codigo="TRANSP_COMBUSTIVEL_C170_MANUAL_V1",
        apontamento_id=apontamento_id,
    )

    return resultado

# C170 Faltante Combustivel

def aplicar_correcao_c170_faltante_manual(
    db: Session,
    *,
    versao_origem_id: int,
    itens: List[Dict[str, Any]],
    apontamento_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Corretiva manual para C170 faltante.

    Estratégia:
    - agrupa os itens por C100 alvo
    - chama o motor existente uma vez por grupo
    - recalcula o C100 pai via função já validada

    Entrada esperada:
    itens = [
        {
            "nf_icms_item_id": 123,
            "registro_id_c100": 456,
            "linha_c100": 78,
            # opcionais:
            "registro_id_ancora": 456,
            "linha_ancora": 78,
        },
        ...
    ]
    """
    logger.warning(
        "[MANUAL_C170_FIX] INICIO | versao=%s | apontamento=%s | total_itens=%s | itens=%s",
        versao_origem_id,
        apontamento_id,
        len(itens or []),
        itens,
    )

    if not itens:
        logger.warning(
            "[MANUAL_C170_FIX] SAIDA_VAZIA | motivo=sem_itens"
        )
        return {
            "status": "vazio",
            "msg": "Nenhum item informado para inserção manual de C170.",
            "total_alterado": 0,
            "total_grupos": 0,
            "total_skips": 0,
            "detalhes": [],
        }

    # agrupa por C100 alvo
    grupos: dict[tuple[int, int], dict[str, Any]] = {}
    total_descartados = 0

    for idx, it in enumerate(itens, start=1):
        nf_icms_item_id = int(it.get("nf_icms_item_id") or 0)
        registro_id_c100 = int(
            it.get("registro_id_c100")
            or it.get("registro_id_ancora")
            or 0
        )
        linha_c100 = int(
            it.get("linha_c100")
            or it.get("linha_ancora")
            or 0
        )

        logger.warning(
            "[MANUAL_C170_FIX] ITEM_BRUTO | idx=%s | nf_icms_item_id=%s | registro_id_c100=%s | linha_c100=%s | item=%s",
            idx,
            nf_icms_item_id,
            registro_id_c100,
            linha_c100,
            it,
        )

        if nf_icms_item_id <= 0:
            total_descartados += 1
            logger.warning(
                "[MANUAL_C170_FIX] ITEM_DESCARTADO | idx=%s | motivo=nf_icms_item_id_invalido | item=%s",
                idx,
                it,
            )
            continue

        if registro_id_c100 <= 0:
            total_descartados += 1
            logger.warning(
                "[MANUAL_C170_FIX] ITEM_DESCARTADO | idx=%s | motivo=registro_id_c100_invalido | item=%s",
                idx,
                it,
            )
            continue

        if linha_c100 <= 0:
            total_descartados += 1
            logger.warning(
                "[MANUAL_C170_FIX] ITEM_DESCARTADO | idx=%s | motivo=linha_c100_invalida | item=%s",
                idx,
                it,
            )
            continue

        chave = (registro_id_c100, linha_c100)

        if chave not in grupos:
            grupos[chave] = {
                "registro_id_c100": registro_id_c100,
                "linha_c100": linha_c100,
                "registro_id_ancora": int(it.get("registro_id_ancora") or 0) or None,
                "linha_ancora": int(it.get("linha_ancora") or 0) or None,
                "nf_icms_item_ids": [],
            }
            logger.warning(
                "[MANUAL_C170_FIX] NOVO_GRUPO | chave=%s | grupo=%s",
                chave,
                grupos[chave],
            )

        if nf_icms_item_id not in grupos[chave]["nf_icms_item_ids"]:
            grupos[chave]["nf_icms_item_ids"].append(nf_icms_item_id)
            logger.warning(
                "[MANUAL_C170_FIX] ITEM_ADICIONADO_GRUPO | chave=%s | nf_icms_item_id=%s | grupo_item_ids=%s",
                chave,
                nf_icms_item_id,
                grupos[chave]["nf_icms_item_ids"],
            )
        else:
            logger.warning(
                "[MANUAL_C170_FIX] ITEM_DUPLICADO_IGNORADO | chave=%s | nf_icms_item_id=%s",
                chave,
                nf_icms_item_id,
            )

    logger.warning(
        "[MANUAL_C170_FIX] GRUPOS_MONTADOS | total_grupos=%s | total_descartados=%s | grupos=%s",
        len(grupos),
        total_descartados,
        grupos,
    )

    if not grupos:
        logger.warning(
            "[MANUAL_C170_FIX] SAIDA_VAZIA | motivo=sem_grupos_elegiveis"
        )
        return {
            "status": "vazio",
            "msg": "Nenhum grupo elegível de C100/C170 encontrado.",
            "total_alterado": 0,
            "total_grupos": 0,
            "total_skips": 0,
            "detalhes": [],
        }

    detalhes: list[dict[str, Any]] = []
    total_alterado = 0
    total_c100_recalculado = 0
    total_erros = 0
    total_skips = 0

    for chave, grupo in grupos.items():
        logger.warning(
            "[MANUAL_C170_FIX] EXECUTANDO_GRUPO | chave=%s | grupo=%s",
            chave,
            grupo,
        )

        res = aplicar_correcao_c170_insert_contribuicao_manual(
            db,
            versao_origem_id=int(versao_origem_id),
            apontamento_id=int(apontamento_id) if apontamento_id else None,
            nf_icms_item_ids=grupo["nf_icms_item_ids"],
            linha_c100=int(grupo["linha_c100"]),
            registro_id_c100=int(grupo["registro_id_c100"]),
            linha_ancora=grupo["linha_ancora"],
            registro_id_ancora=grupo["registro_id_ancora"],
            motivo_codigo="CONTRIB_SEM_C170_MANUAL_V1",
            contexto="COMBUSTIVEL",
            fator_base_credito=0.75,
            aliq_pis="1,6500",
            aliq_cofins="7,6000",
        )

        logger.warning(
            "[MANUAL_C170_FIX] RESULTADO_GRUPO | chave=%s | status=%s | res=%s",
            chave,
            (res or {}).get("status"),
            res,
        )

        detalhes.append(res)

        status_res = str((res or {}).get("status") or "").lower()

        if status_res == "ok":
            total_alterado += int((res or {}).get("insert_criado") or 0)
            total_c100_recalculado += int((res or {}).get("c100_recalculado") or 0)
        elif status_res == "erro":
            total_erros += 1
        else:
            total_skips += 1

    status_final = "ok" if total_alterado > 0 else "vazio"

    logger.warning(
        "[MANUAL_C170_FIX] FIM | status_final=%s | total_alterado=%s | total_grupos=%s | total_c100_recalculado=%s | total_erros=%s | total_skips=%s",
        status_final,
        total_alterado,
        len(grupos),
        total_c100_recalculado,
        total_erros,
        total_skips,
    )

    return {
        "status": status_final,
        "msg": f"{total_alterado} C170 inserido(s) manualmente em {len(grupos)} grupo(s).",
        "total_alterado": total_alterado,
        "total_grupos": len(grupos),
        "total_c100_recalculado": total_c100_recalculado,
        "total_erros": total_erros,
        "total_skips": total_skips,
        "detalhes": detalhes,
    }
