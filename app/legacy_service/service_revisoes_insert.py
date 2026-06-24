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

    resultado: List[LinhaLogica] = [l for l in linhas_base]

    inserts_after: List[Dict] = []
    inserts_before: List[Dict] = []

    for r in revisoes:
        acao = str(r.get("acao") or "").upper()
        if acao == "INSERT_AFTER":
            inserts_after.append(r)
        elif acao == "INSERT_BEFORE":
            inserts_before.append(r)

    def _preparar(rv: Dict) -> Optional[Dict]:
        rj = rv.get("revisao_json") or rv  # 🔥 fallback seguro
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

        linha_ref = rv.get("linha_num") or rj.get("linha_num") or rj.get("linha_referencia") or 0

        rr = dict(rv)
        rr["linha_final"] = str(linha_txt)
        rr["linha_ref"] = int(linha_ref or 0)
        rr["_rev_id"] = int(rv.get("id") or 0)

        parsed = _parse_linha_sped_to_reg_dados_preservando_finais_vazios(linha_txt)
        rr["_reg_preparado"] = str((parsed[0] if parsed else rv.get("reg") or "")).upper()

        return rr

    def _rev_key(rv: Dict) -> int:
        try:
            return int(rv.get("id") or 0)
        except Exception:
            return 0

    def _alvo_key(rv: Dict):
        reg = str(rv.get("_reg_preparado") or rv.get("reg") or "").upper()

        if reg == "0150":
            return ("0150", int(rv.get("_rev_id") or 0))

        # 🔥 bloco expandido: diferencia por linha_ref + ordem
        if rv.get("_ordem_bloco") is not None:
            rid = int(rv.get("registro_id") or 0)
            lr = int(rv.get("linha_ref") or 0)
            ordem = int(rv.get("_ordem_bloco") or 0)
            return ("BLOCO", rid, lr, ordem)

        rid = int(rv.get("registro_id") or 0)
        if rid > 0:
            return ("RID", rid)

        lr = int(rv.get("linha_ref") or 0)
        return ("LINHA", -lr if lr > 0 else 0)

    def _renumerar_resultado() -> None:
        for i, l in enumerate(resultado, start=1):
            l.linha = i

    def _escolher_vencedoras(lista: List[Dict]) -> List[Dict]:
        def _expandir_preparadas(rv: Dict) -> List[Dict]:
            rj = rv.get("revisao_json") or {}
            linhas_novas = rj.get("linhas_novas") or []

            # 🔥 novo fluxo: bloco com várias linhas
            if linhas_novas:
                linha_ref_base = int(
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
                    rr["_rev_id"] = int(rv.get("id") or 0)
                    rr["_ordem_bloco"] = i

                    parsed = _parse_linha_sped_to_reg_dados_preservando_finais_vazios(linha_txt)
                    rr["_reg_preparado"] = str((parsed[0] if parsed else rv.get("reg") or "")).upper()

                    expandidas.append(rr)

                return expandidas

            # fluxo antigo: uma linha só
            p = _preparar(rv)
            return [p] if p else []

        preparadas: List[Dict] = []
        for rv in lista:
            preparadas.extend(_expandir_preparadas(rv))

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
                if _rev_key(rv) >= _rev_key(atual):
                    vencedora_por_alvo[k] = rv
            else:
                if _rev_key(rv) <= _rev_key(atual):
                    vencedora_por_alvo[k] = rv

        return list(vencedora_por_alvo.values())
    inserts_before_final = _escolher_vencedoras(inserts_before)
    inserts_after_final = _escolher_vencedoras(inserts_after)

    def _achar_indice_alvo(rv: Dict) -> int:
        rid = int(rv.get("registro_id") or 0)
        linha_ref = int(rv.get("linha_ref") or 0)

        for idx, l in enumerate(resultado):
            if rid and int(getattr(l, "registro_id", 0) or 0) == rid:
                return idx
            if linha_ref and int(getattr(l, "linha", 0) or 0) == linha_ref:
                return idx
        return -1

    # Trazendo a conta
    cod_cta_padrao_0500 = resolver_cod_cta_padrao_0500(linhas_base)

    def _criar_linha_inserida(
        rv: Dict,
        alvo: "LinhaLogica",
        linhas_base: list["LinhaLogica"],
        cod_cta_padrao_0500: str,
    ) -> Optional["LinhaLogica"]:
        try:
            reg, dados = _parse_linha_sped_to_reg_dados_preservando_finais_vazios(str(rv["linha_final"]))
            if not reg:
                return None

            if str(reg).upper() == "C170":
                cod_cta = str(dados[35] or "").strip() if len(dados) >= 36 else ""

                if not cod_cta:
                    # 1) tenta resolver com base no contexto da linha/alvo
                    cod_cta = resolver_cod_cta_para_insert_c170(
                        alvo=alvo,
                        linhas_base=linhas_base,
                        cod_cta_padrao_0500=cod_cta_padrao_0500,
                        dados_c170_novo=dados,
                    )

                    # 2) fallback final: verificar conta válida para inserir
                    if not cod_cta:
                        logger.warning(
                            "COD_CTA não resolvido para C170 inserido | reg_alvo=%s linha_alvo=%s",
                            getattr(alvo, "reg", None),
                            getattr(alvo, "linha", None),
                        )

                    while len(dados) < 36:
                        dados.append("")

                    dados[35] = cod_cta


            pai_id = getattr(alvo, "pai_id", None)

            if str(reg).upper() == "C170":
                if str(getattr(alvo, "reg", "")).upper() == "C100":
                    pai_id = getattr(alvo, "registro_id", None)
                else:
                    pai_id = getattr(alvo, "pai_id", None)

            nova = LinhaLogica(
                linha=0,
                reg=str(reg).upper(),
                dados=list(dados or []),
                origem="INSERIDO",
                registro_id=None,
                pai_id=int(pai_id or 0) or None,
                revisao_id=int(rv.get("id") or 0) or None,
            )

            return nova

        except Exception:
            logger.exception(
                "Erro ao criar linha inserida | revisao_id=%s alvo_reg=%s alvo_linha=%s",
                rv.get("id"),
                getattr(alvo, "reg", None),
                getattr(alvo, "linha", None),
            )
            return None

    # INSERT_BEFORE primeiro
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

    # INSERT_AFTER depois
    for rv in inserts_after_final:
        idx = _achar_indice_alvo(rv)
        if idx < 0:
            continue

        alvo = resultado[idx]
        nova = _criar_linha_inserida(rv, alvo, linhas_base, cod_cta_padrao_0500)
        if nova:
            resultado.insert(idx + 1, nova)
            _renumerar_resultado()

    # renumera
    _renumerar_resultado()

    logger.info(
        "OVERLAY_INSERT finalizado | final_lines=%s inserts_before=%s inserts_after=%s",
        len(resultado),
        len(inserts_before_final),
        len(inserts_after_final),
    )

    return resultado