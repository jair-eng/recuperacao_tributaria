from __future__ import annotations

from typing import Dict, List, Optional
from app.sped.blocoC.c170_utils import _parse_linha_sped_to_reg_dados_preservando_finais_vazios
from app.sped.revisao_overlay import LinhaLogica
from app.sped.utils_cod_cta import resolver_cod_cta_padrao_0500, resolver_cod_cta_para_insert_c170
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


def aplicar_revisoes_insert(
    *,
    linhas_base,
    revisoes,
    preferir_ultima=True,
    db: Session | None = None,
    versao_origem_id: int | None = None,
) -> List["LinhaLogica"]:
    if not linhas_base:
        return []

    if not revisoes:
        return list(linhas_base)

    resultado: List[LinhaLogica] = list(linhas_base)

    REGS_MESTRES_BLOCO0 = {"0150", "0190", "0200", "0500"}

    # ------------------------------------------------------------
    # Helpers básicos
    # ------------------------------------------------------------
    def _as_int(v, default: int = 0) -> int:
        try:
            return int(v or default)
        except Exception:
            return default

    def _rev_json(rv: Dict) -> Dict:
        rj = rv.get("revisao_json") or {}
        return rj if isinstance(rj, dict) else {}

    def _rev_id(rv: Dict) -> int:
        return _as_int(rv.get("_rev_id") or rv.get("id"))

    def _reg(rv: Dict) -> str:
        return str(rv.get("_reg_preparado") or rv.get("reg") or "").upper()

    def _renumerar_resultado() -> None:
        for i, l in enumerate(resultado, start=1):
            l.linha = i

    def _eh_mestre_bloco0(rv: Dict) -> bool:
        return _reg(rv) in REGS_MESTRES_BLOCO0 and rv.get("_ordem_bloco0") is not None

    # ------------------------------------------------------------
    # Separação por ação
    # ------------------------------------------------------------
    inserts_after: List[Dict] = []
    inserts_before: List[Dict] = []

    for r in revisoes:
        acao = str(r.get("acao") or "").upper()
        if acao == "INSERT_AFTER":
            inserts_after.append(r)
        elif acao == "INSERT_BEFORE":
            inserts_before.append(r)

    # ------------------------------------------------------------
    # Preparação / expansão
    # ------------------------------------------------------------
    def _preparar_linha_unica(rv: Dict) -> Optional[Dict]:
        rj = _rev_json(rv)
        linhas_novas = rj.get("linhas_novas") or []

        linha_txt = (
            rj.get("linha_nova")
            or (linhas_novas[0] if linhas_novas else "")
            or rv.get("linha")
            or rj.get("linha")
            or ""
        )

        if not linha_txt:
            return None

        linha_ref = (
            rv.get("linha_num")
            or rj.get("linha_num")
            or rj.get("linha_referencia")
            or 0
        )

        rr = dict(rv)
        rr["linha_final"] = str(linha_txt)
        rr["linha_ref"] = _as_int(linha_ref)
        rr["_rev_id"] = _as_int(rv.get("id"))
        rr["_ordem_bloco0"] = rj.get("_ordem_bloco0")

        parsed = _parse_linha_sped_to_reg_dados_preservando_finais_vazios(linha_txt)
        rr["_reg_preparado"] = str((parsed[0] if parsed else rv.get("reg") or "")).upper()

        return rr

    def _expandir_revisao(rv: Dict) -> List[Dict]:
        rj = _rev_json(rv)
        linhas_novas = rj.get("linhas_novas") or []

        if not linhas_novas:
            p = _preparar_linha_unica(rv)
            return [p] if p else []

        linha_ref_base = _as_int(
            rv.get("linha_num")
            or rj.get("linha_num")
            or rj.get("linha_referencia")
            or 0
        )

        expandidas: List[Dict] = []

        for i, linha_txt in enumerate(linhas_novas):
            if not linha_txt:
                continue

            rr = dict(rv)
            rr["linha_final"] = str(linha_txt)
            rr["linha_ref"] = int(linha_ref_base + i)
            rr["_rev_id"] = _as_int(rv.get("id"))
            rr["_ordem_bloco"] = i
            mapa_itens = rj.get("mapa_linha_nf_icms_item_id") or {}
            rr["nf_icms_item_id"] = int(mapa_itens.get(str(i)) or 0) or None
            rr["_ordem_bloco0"] = rj.get("_ordem_bloco0")

            parsed = _parse_linha_sped_to_reg_dados_preservando_finais_vazios(linha_txt)
            rr["_reg_preparado"] = str((parsed[0] if parsed else rv.get("reg") or "")).upper()

            expandidas.append(rr)

        return expandidas

    # ------------------------------------------------------------
    # Chave de deduplicação/vencedora
    # ------------------------------------------------------------
    def _alvo_key(rv: Dict):
        reg = _reg(rv)

        if reg in REGS_MESTRES_BLOCO0 and rv.get("_ordem_bloco0") is not None:
            return (
                "BLOCO0",
                _as_int(rv.get("registro_id")),
                _as_int(rv.get("linha_ref")),
                _as_int(rv.get("_ordem_bloco0")),
                _rev_id(rv),
            )

        if reg == "0150":
            return ("0150", _rev_id(rv))

        if rv.get("_ordem_bloco") is not None:
            return (
                "BLOCO",
                _rev_id(rv),
                _as_int(rv.get("registro_id")),
                _as_int(rv.get("linha_ref")),
                _as_int(rv.get("_ordem_bloco")),
            )

        rid = _as_int(rv.get("registro_id"))
        if rid > 0:
            return ("RID", rid)

        lr = _as_int(rv.get("linha_ref"))
        return ("LINHA", -lr if lr > 0 else 0)

    def _escolher_vencedoras(lista: List[Dict]) -> List[Dict]:
        preparadas: List[Dict] = []
        for rv in lista:
            preparadas.extend(_expandir_revisao(rv))

        vencedora_por_alvo: Dict[object, Dict] = {}

        for rv in preparadas:
            k = _alvo_key(rv)
            if not k:
                continue

            atual = vencedora_por_alvo.get(k)
            if atual is None:
                vencedora_por_alvo[k] = rv
                continue

            if preferir_ultima:
                if _rev_id(rv) >= _rev_id(atual):
                    vencedora_por_alvo[k] = rv
            else:
                if _rev_id(rv) <= _rev_id(atual):
                    vencedora_por_alvo[k] = rv

        return list(vencedora_por_alvo.values())

    inserts_before_final = _escolher_vencedoras(inserts_before)
    inserts_after_final = _escolher_vencedoras(inserts_after)

    # ------------------------------------------------------------
    # Ordenação especial SOMENTE para mestres do Bloco 0.
    # Importante:
    # - INSERT_AFTER aplica invertido porque cada insert entra logo após a mesma âncora.
    # - C100/C170 e demais registros ficam fora dessa ordenação.
    # ------------------------------------------------------------
    mestres_after = [rv for rv in inserts_after_final if _eh_mestre_bloco0(rv)]
    outros_after = [rv for rv in inserts_after_final if not _eh_mestre_bloco0(rv)]

    mestres_after = sorted(
        mestres_after,
        key=lambda rv: (
            _as_int(rv.get("linha_ref")),
            _as_int(rv.get("_ordem_bloco0"), 9999),
            _rev_id(rv),
        ),
        reverse=True,
    )

    inserts_after_final = mestres_after + outros_after

    logger.debug(
        "[OVERLAY INSERT] vencedoras | before=%s after=%s",
        len(inserts_before_final),
        len(inserts_after_final),
    )

    # ------------------------------------------------------------
    # Busca do alvo
    # ------------------------------------------------------------
    def _achar_indice_alvo(rv: Dict) -> int:
        rid = _as_int(rv.get("registro_id"))
        linha_ref = _as_int(rv.get("linha_ref"))
        reg_insert = _reg(rv)

        mestre_bloco0 = _eh_mestre_bloco0(rv)

        priorizar_linha = (
            reg_insert in {"C100", "C170"}
            and linha_ref > 0
            and not mestre_bloco0
        )

        def _buscar_por_linha() -> int:
            for idx, l in enumerate(resultado):
                if linha_ref and _as_int(getattr(l, "linha", 0)) == linha_ref:
                    return idx
            return -1

        def _buscar_por_rid() -> int:
            for idx, l in enumerate(resultado):
                if rid and _as_int(getattr(l, "registro_id", 0)) == rid:
                    return idx
            return -1

        if priorizar_linha:
            idx = _buscar_por_linha()
            if idx >= 0:
                return idx

            idx = _buscar_por_rid()
            if idx >= 0:
                return idx
        else:
            idx = _buscar_por_rid()
            if idx >= 0:
                return idx

            idx = _buscar_por_linha()
            if idx >= 0:
                return idx

        logger.warning(
            "[OVERLAY INSERT] alvo não encontrado | rev=%s reg=%s rid=%s linha_ref=%s priorizar_linha=%s",
            rv.get("id"),
            reg_insert,
            rid,
            linha_ref,
            priorizar_linha,
        )
        return -1

    # ------------------------------------------------------------
    # Criação da LinhaLogica inserida
    # ------------------------------------------------------------
    cod_cta_padrao_0500 = resolver_cod_cta_padrao_0500(linhas_base)

    def _criar_linha_inserida(
        rv: Dict,
        alvo: "LinhaLogica",
        linhas_base: list["LinhaLogica"],
        cod_cta_padrao_0500: str,
    ) -> Optional["LinhaLogica"]:
        try:
            reg, dados = _parse_linha_sped_to_reg_dados_preservando_finais_vazios(
                str(rv["linha_final"])
            )

            if not reg:
                return None

            reg = str(reg).upper()

            if reg == "C170":
                cod_cta = str(dados[35] or "").strip() if len(dados) >= 36 else ""

                if not cod_cta:
                    cod_cta = resolver_cod_cta_para_insert_c170(
                        alvo=alvo,
                        linhas_base=linhas_base,
                        cod_cta_padrao_0500=cod_cta_padrao_0500,
                        dados_c170_novo=dados,
                    )

                    if not cod_cta:
                        logger.warning(
                            "COD_CTA não resolvido para C170 inserido | reg_alvo=%s linha_alvo=%s",
                            getattr(alvo, "reg", None),
                            getattr(alvo, "linha", None),
                        )

                    while len(dados) < 36:
                        dados.append("")

                    dados[35] = cod_cta

                    logger.debug(
                        "COD_CTA preenchido em C170 inserido | reg_alvo=%s linha_alvo=%s cod_cta_final=%s origem_base_0500=%s",
                        getattr(alvo, "reg", None),
                        getattr(alvo, "linha", None),
                        cod_cta,
                        cod_cta_padrao_0500,
                    )

            pai_id = getattr(alvo, "pai_id", None)

            if reg == "C170":
                if str(getattr(alvo, "reg", "")).upper() == "C100":
                    pai_id = getattr(alvo, "registro_id", None)
                else:
                    pai_id = getattr(alvo, "pai_id", None)

            return LinhaLogica(
                linha=0,
                reg=reg,
                dados=list(dados or []),
                origem="INSERIDO",
                registro_id=None,
                pai_id=int(pai_id or 0) or None,
                revisao_id=_rev_id(rv) or None,
            )

        except Exception:
            logger.exception(
                "Erro ao criar linha inserida | revisao_id=%s alvo_reg=%s alvo_linha=%s",
                rv.get("id"),
                getattr(alvo, "reg", None),
                getattr(alvo, "linha", None),
            )
            return None

    # ------------------------------------------------------------
    # Aplicação dos INSERTs
    # ------------------------------------------------------------
    for rv in inserts_before_final:
        idx = _achar_indice_alvo(rv)
        if idx < 0:
            continue

        alvo = resultado[idx]
        nova = _criar_linha_inserida(
            rv,
            alvo,
            linhas_base,
            cod_cta_padrao_0500,
        )

        if nova:
            resultado.insert(idx, nova)
            _renumerar_resultado()

    for rv in inserts_after_final:
        idx = _achar_indice_alvo(rv)
        if idx < 0:
            continue

        alvo = resultado[idx]
        nova = _criar_linha_inserida(
            rv,
            alvo,
            linhas_base,
            cod_cta_padrao_0500,
        )

        if nova:
            resultado.insert(idx + 1, nova)
            _renumerar_resultado()

    _renumerar_resultado()

    logger.info(
        "OVERLAY_INSERT finalizado | final_lines=%s inserts_before=%s inserts_after=%s",
        len(resultado),
        len(inserts_before_final),
        len(inserts_after_final),
    )

    return resultado