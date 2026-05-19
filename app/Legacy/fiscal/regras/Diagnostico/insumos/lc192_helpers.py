from __future__ import annotations

from typing import Any


from app.sped.utils_geral import _somente_digitos
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_helpers import  _to_decimal



NCM_ARLA32 = "31021010"

LC192_DATA_INI = "20220311"
LC192_DATA_FIM = "20220815"  # janela conservadora da noventena

def norm_codigo(c):
    return str(c or "").strip().upper()
def _normalizar_periodo_aaaamm(valor: Any) -> str:
    """
    Aceita:
    - 202203
    - 2022-03
    - 20220311
    - 11/03/2022

    Retorna AAAAMM ou vazio.
    """
    s = str(valor or "").strip()

    if not s:
        return ""

    dig = _somente_digitos(s)

    if len(dig) >= 8:
        # Pode vir AAAAMMDD ou DDMMAAAA
        if dig[:4].startswith("20"):
            return dig[:6]
        if dig[-4:].startswith("20"):
            return dig[-4:] + dig[2:4]

    if len(dig) >= 6:
        return dig[:6]

    return ""


def _periodo_aaaamm_para_data_min(periodo: str) -> str:
    periodo = _normalizar_periodo_aaaamm(periodo)
    if len(periodo) != 6:
        return ""
    return f"{periodo}01"


def eh_periodo_lc192(valor_periodo: Any) -> bool:
    """
    Valida se o período está dentro da janela LC 192/2022.

    Por enquanto usamos a janela conservadora:
    202203 até 202208.

    A checagem é mensal porque o SPED trabalha por período.
    """
    periodo = _normalizar_periodo_aaaamm(valor_periodo)
    if len(periodo) != 6:
        return False

    return "202203" <= periodo <= "202208"


def eh_ncm_lc192_combustivel(ncm: Any) -> bool:
    """
    Filtro mínimo de segurança.

    A confirmação principal deve vir do catálogo fiscal
    COMB_LC192_NCM.

    Este helper só bloqueia falsos positivos óbvios.
    """
    ncm_norm = _somente_digitos(ncm)

    if not ncm_norm:
        return False

    if ncm_norm == NCM_ARLA32:
        return False

    return True


def eh_regime_nao_cumulativo(meta: dict[str, Any] | None = None, regime: Any = None) -> bool:
    """
    Retorna True quando houver indício de regime não cumulativo.

    Aceita regime vindo direto ou dentro do meta:
    - regime_apuracao
    - cod_inc_trib
    """
    meta = meta or {}

    valor = str(
        regime
        or meta.get("regime_apuracao")
        or meta.get("cod_inc_trib")
        or ""
    ).strip().upper()

    if not valor:
        return False

    # SPED: COD_INC_TRIB = 1 geralmente indica não cumulativo
    if valor in {"1", "NAO_CUMULATIVO", "NÃO_CUMULATIVO", "NAO CUMULATIVO", "NÃO CUMULATIVO"}:
        return True

    return False


def elegivel_lc192_combustivel(
    *,
    meta: dict[str, Any] | None,
    periodo: Any = None,
    regime: Any = None,
    ncm: Any = None,
    no_catalogo_lc192: bool = False,
) -> bool:
    """
    Helper central para a exceção da LC 192/2022.

    Uso esperado:
    - regra COMB_LC192_V1
    - bypass da TRANSP_COMBUSTIVEL_V1

    Importante:
    - no_catalogo_lc192 deve vir da consulta ao grupo COMB_LC192_NCM
    - aqui NÃO consultamos banco para manter o helper puro/testável
    """
    meta = meta or {}

    periodo_ref = (
        periodo
        or meta.get("periodo")
        or meta.get("dt_doc")
        or meta.get("data_doc")
    )

    ncm_ref = (
        ncm
        or meta.get("ncm")
        or meta.get("cod_ncm")
        or meta.get("ncm_item")
    )
    ok_periodo = eh_periodo_lc192(periodo_ref)
    ok_regime = eh_regime_nao_cumulativo(meta=meta, regime=regime)
    ok_ncm = eh_ncm_lc192_combustivel(ncm_ref)
    ok_catalogo = bool(no_catalogo_lc192)

    return ok_periodo and ok_regime and ok_ncm and ok_catalogo


def consolidar_achados_comb_lc192_v1(result) -> None:
    aps = list(result.apontamentos or [])
    if not aps:
        return

    manter = []
    grupos = defaultdict(lambda: {
        "aps": [],
        "impacto": Decimal("0"),
        "base": Decimal("0"),
        "pis": Decimal("0"),
        "cofins": Decimal("0"),
        "qtd": 0,
        "repr": None,
        "registro_ids": [],
        "nf_icms_item_ids": [],
        "itens": [],
    })

    for a in aps:
        codigo = norm_codigo(getattr(a, "codigo", None))

        if codigo != "COMB_LC192_V1":
            manter.append(a)
            continue

        meta = getattr(a, "meta_json", None) or getattr(a, "meta", None) or {}

        contexto = str(
            meta.get("contexto_credito")
            or meta.get("contexto")
            or "LC192"
        ).strip().upper()

        chave = ("COMB_LC192_V1", contexto)

        g = grupos[chave]
        g["aps"].append(a)
        g["qtd"] += 1
        g["impacto"] += _to_decimal(getattr(a, "impacto_financeiro", 0))
        g["base"] += _to_decimal(
            meta.get("base_credito")
            or meta.get("base_calculo_estimada")
            or meta.get("vl_bc_pis")
        )

        g["pis"] += _to_decimal(
            meta.get("pis_estimado")
            or meta.get("valor_pis_estimado")
            or meta.get("vl_pis")
        )

        g["cofins"] += _to_decimal(
            meta.get("cofins_estimado")
            or meta.get("valor_cofins_estimado")
            or meta.get("vl_cofins")
        )

        if g["repr"] is None:
            g["repr"] = a

        registro_id = meta.get("registro_id") or getattr(a, "registro_id", None)
        if registro_id:
            g["registro_ids"].append(int(registro_id))

        nf_item_id = meta.get("nf_icms_item_id")
        if nf_item_id:
            g["nf_icms_item_ids"].append(int(nf_item_id))

        if len(g["itens"]) < 20:
            g["itens"].append({
                "cod_item": meta.get("cod_item"),
                "descricao": meta.get("descricao_item") or meta.get("descricao"),
                "ncm": meta.get("ncm"),
                "cfop": meta.get("cfop"),
                "chave_nfe": meta.get("chave_nfe"),
                "num_item": meta.get("num_item"),
                "registro_id": registro_id,
                "nf_icms_item_id": nf_item_id,
                "base_credito": str(
                    meta.get("base_credito")
                    or meta.get("base_calculo_estimada")
                    or 0
                ),
                "pis_estimado": str(
                    meta.get("pis_estimado")
                    or meta.get("valor_pis_estimado")
                    or 0
                ),
                "cofins_estimado": str(
                    meta.get("cofins_estimado")
                    or meta.get("valor_cofins_estimado")
                    or 0
                ),
            })

    for (_, contexto), g in grupos.items():
        if not g["repr"]:
            continue

        base_ap = g["repr"]
        meta_base = deepcopy(
            getattr(base_ap, "meta_json", None)
            or getattr(base_ap, "meta", None)
            or {}
        )

        registro_ids = sorted(set(g["registro_ids"]))
        nf_icms_item_ids = sorted(set(g["nf_icms_item_ids"]))

        meta_base.update({
            "agrupado": True,
            "codigo_origem": "COMB_LC192_V1",
            "contexto_credito": contexto,
            "tipo_credito": "COMB_LC192_V1",
            "cod_base_credito": "206",
            "natureza_credito_m": "206",

            "qtd_itens": g["qtd"],
            "base_total": str(g["base"]),
            "pis_total": str(g["pis"]),
            "cofins_total": str(g["cofins"]),
            "credito_total_estimado": str(g["impacto"]),

            # usados pelo resolver em lote
            "registro_ids": registro_ids,
            "nf_icms_item_ids": nf_icms_item_ids,

            # usado pela UI
            "itens_resumo": g["itens"],

            "permite_autocorrecao": True,
            "executor_fluxo": "COMB_LC192_AGR",
        })

        desc = (
            f"Possível crédito LC192 não aproveitado. "
            f"{g['qtd']} item(ns) | base total {g['base']} | "
            f"crédito estimado total {g['impacto']}"
        )

        novo = deepcopy(base_ap)
        novo.codigo = "COMB_LC192_AGR_V1"
        novo.descricao = desc
        novo.impacto_financeiro = float(g["impacto"])

        if hasattr(novo, "meta_json"):
            novo.meta_json = meta_base
        elif hasattr(novo, "meta"):
            novo.meta = meta_base

        manter.append(novo)

    result.apontamentos = manter