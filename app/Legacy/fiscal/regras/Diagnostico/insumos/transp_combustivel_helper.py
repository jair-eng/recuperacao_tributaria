from __future__ import annotations

from typing import Any, Dict, List, Optional
from app.Legacy.fiscal.ent_cat_fiscal import CatalogoFiscal
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_helpers import classificar_item_transp
from app.Legacy.fiscal.regras.Diagnostico.insumos.lc192_helpers import elegivel_lc192_combustivel

BUCKETS_COMBUSTIVEL_MANUAL = {"COMBUSTIVEL", "ARLA32"}


def _s(v: Any) -> str:
    return str(v or "").strip()


def _to_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    txt = _s(v).lower()
    return txt in {"1", "true", "sim", "yes"}


def item_candidato_fluxo_manual_combustivel_transp(
    catalogo: CatalogoFiscal,
    *,
    item: Dict[str, Any],
    nome_participante: str = "",
    cod_cta: str = "",
    origem_cod_cta: str = "",
    cst_pis: str = "",
    cst_cofins: str = "",
    periodo: str = "",
    origem_dados: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Classifica um item para o fluxo manual de combustível da transportadora.

    Retorna um dict enriquecido quando o item for candidato (COMBUSTIVEL/ARLA32),
    ou None quando não for.
    """
    ncm = _s(item.get("ncm"))
    descricao = _s(
        item.get("descricao")
        or item.get("descricao_item")
        or item.get("descr_item")
    )
    cfop = _s(item.get("cfop"))
    cod_item = _s(item.get("cod_item"))
    num_item = _s(item.get("num_item"))

    cls = classificar_item_transp(
        catalogo,
        ncm=ncm,
        desc_item=descricao,
        nome_part=nome_participante,
        cod_cta=cod_cta,
        origem_cod_cta=origem_cod_cta,
        cst_pis=cst_pis,
        cst_cofins=cst_cofins,
        cfop=cfop,
        periodo=periodo,
        valor_icms=item.get("valor_icms_icms") or item.get("vl_icms") or item.get("valor_icms"),
        valor_ipi=item.get("valor_ipi_icms") or item.get("vl_ipi") or item.get("valor_ipi"),
        origem_dados=origem_dados,
    )

    bucket = _s(cls.get("bucket"))
    if bucket not in BUCKETS_COMBUSTIVEL_MANUAL:
        return None

    return {
        # --- identidade/origem do item ---
        "origem": "ICMS_IPI_CRUZAMENTO",
        "origem_dados_classificacao": origem_dados,

        "chave_nfe": item.get("chave_nfe"),
        "num_item": num_item or item.get("item") or "",
        "cod_item": cod_item,
        "cod_item_norm": item.get("cod_item_norm") or cod_item,
        "descricao": descricao,
        "ncm": ncm,
        "cfop": cfop,

        # --- valores de origem ---
        "valor_item_icms": (
                item.get("valor_item_icms")
                or item.get("vl_item")
                or item.get("valor_item")
        ),
        "valor_icms_icms": (
                item.get("valor_icms_icms")
                or item.get("vl_icms")
                or item.get("valor_icms")
        ),
        "valor_ipi_icms": (
                item.get("valor_ipi_icms")
                or item.get("vl_ipi")
                or item.get("valor_ipi")
        ),
        "valor_item_efd": item.get("valor_item_efd") or "0",

        # --- vínculo / execução ---
        "nf_icms_item_id": item.get("nf_icms_item_id") or item.get("id"),
        "registro_id_ancora": item.get("registro_id_ancora"),
        "linha_ancora": item.get("linha_ancora"),
        "reg_ancora": item.get("reg_ancora"),
        "contrib_tem_c100": item.get("contrib_tem_c100"),

        "c170_registro_id_existente": item.get("c170_registro_id"),
        "c170_linha_existente": item.get("c170_linha"),

        "status": item.get("status"),
        "tipo_match": item.get("tipo_match"),
        "match_encontrado": bool(item.get("match_encontrado")),
        "observacao": item.get("observacao"),

        # --- classificação transporte / combustível ---
        "bucket": bucket,
        "subbucket": cls.get("subbucket"),
        "match_source": cls.get("match_source"),
        "match_slug": cls.get("match_slug"),
        "tratamento_motor": cls.get("tratamento_motor"),
        "teses_aplicaveis": list(cls.get("teses_aplicaveis") or []),
        "flags": dict(cls.get("flags") or {}),
        "score_classificacao": int(cls.get("score") or 0),
        "grau_confianca": cls.get("grau_confianca"),

        # --- controle do fluxo manual ---
        "permite_autocorrecao": False,
        "permite_acao_manual": True,
        "exige_revisao_manual": True,
        "modo_correcao": "MANUAL_ONLY",
        "risco_fiscal": "ALTO",
    }


def filtrar_itens_fluxo_manual_combustivel_transp(
    catalogo: CatalogoFiscal,
    *,
    itens: List[Dict[str, Any]],
    nome_participante: str = "",
    cod_cta: str = "",
    origem_cod_cta: str = "",
    cst_pis: str = "",
    cst_cofins: str = "",
    periodo: str = "",
    origem_dados: str = "",
) -> List[Dict[str, Any]]:
    """
    Filtra uma lista de itens, mantendo só os candidatos ao fluxo manual
    de combustível da transportadora.
    """
    out: List[Dict[str, Any]] = []

    for item in itens or []:
        if not isinstance(item, dict):
            continue

        cand = item_candidato_fluxo_manual_combustivel_transp(
            catalogo,
            item=item,
            nome_participante=nome_participante,
            cod_cta=cod_cta,
            origem_cod_cta=origem_cod_cta,
            cst_pis=cst_pis,
            cst_cofins=cst_cofins,
            periodo=periodo,
            origem_dados=origem_dados,
        )
        if cand:
            out.append(cand)

    return out


def nota_tem_candidato_fluxo_manual_combustivel_transp(
    catalogo: CatalogoFiscal,
    *,
    itens_contexto: List[Dict[str, Any]],
    nome_participante: str = "",
    periodo: str = "",
    origem_dados: str = "ICMS_IPI",
) -> bool:
    """
    Atalho booleano para saber se a nota possui pelo menos um item candidato
    ao fluxo manual de combustível.
    """
    itens = filtrar_itens_fluxo_manual_combustivel_transp(
        catalogo,
        itens=itens_contexto,
        nome_participante=nome_participante,
        periodo=periodo,
        origem_dados=origem_dados,
    )
    return len(itens) > 0


def resumir_itens_fluxo_manual_combustivel_transp(
    itens: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Gera um resumo útil para meta de apontamento.
    """
    qtd_combustivel = 0
    qtd_arla32 = 0
    score_total = 0
    teses: set[str] = set()

    for it in itens or []:
        bucket = _s(it.get("bucket"))
        if bucket == "COMBUSTIVEL":
            qtd_combustivel += 1
        elif bucket == "ARLA32":
            qtd_arla32 += 1

        score_total += int(it.get("score_classificacao") or 0)

        for tese in list(it.get("teses_aplicaveis") or []):
            tese_txt = _s(tese)
            if tese_txt:
                teses.add(tese_txt)

    return {
        "qtd_itens": len(itens or []),
        "qtd_combustivel": qtd_combustivel,
        "qtd_arla32": qtd_arla32,
        "score_total": score_total,
        "teses_aplicaveis": sorted(teses),
    }


def modo_execucao_combustivel_transp_por_meta(
    meta: Dict[str, Any],
) -> str:
    """
    Define o modo de execução esperado para o fluxo manual.
    """
    contrib_tem_c100 = _to_bool(meta.get("contrib_tem_c100"))
    registro_id_ancora = meta.get("registro_id_ancora")
    linha_ancora = meta.get("linha_ancora")

    if contrib_tem_c100 and (registro_id_ancora or linha_ancora):
        return "C170_FALTANTE"

    return "C100_FALTANTE"


def bypassar_combustivel_manual_por_lc192(
    *,
    meta: dict,
    item: dict,
    catalogo,
    periodo=None,
    regime=None,
) -> bool:
    ncm = item.get("ncm") or meta.get("ncm")
    bucket = item.get("bucket") or meta.get("bucket")

    if bucket != "COMBUSTIVEL":
        return False

    no_catalogo_lc192 = catalogo.ncm_match("COMB_LC192_NCM", ncm)

    return elegivel_lc192_combustivel(
        meta={**meta, **item},
        periodo=periodo or meta.get("periodo"),
        regime=regime or meta.get("regime_apuracao") or meta.get("cod_inc_trib"),
        ncm=ncm,
        no_catalogo_lc192=no_catalogo_lc192,
    )