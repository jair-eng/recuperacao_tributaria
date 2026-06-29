from __future__ import annotations

from typing import Any, Dict, Optional

from app.Legacy.fiscal.settings_fiscais import CSTS_CREDITAVEIS
from app.utils.numbers import dec_any


def diagnosticar_credito_nao_aproveitado(
    meta: Dict[str, Any],
    classificacao: Dict[str, Any],
    cenario: Dict[str, Any],
) -> Optional[Dict[str, Any]]:

    if not cenario or not cenario.get("ativo"):
        return None

    enquadramento = cenario.get("enquadramento") or {}

    if not enquadramento:
        return {
            "ativo": True,
            "codigo": "ENQUADRAMENTO_NAO_ENCONTRADO",
            "tipo": "ERRO_CONFIGURACAO",
            "descricao": "Cenário ativo sem enquadramento fiscal cadastrado.",
            "meta": {
                "codigo_cenario": cenario.get("codigo_cenario"),
                "fundamento_legal": cenario.get("fundamento_legal"),
            },
        }

    csts_creditaveis = {str(cst or "").strip().zfill(2) for cst in (CSTS_CREDITAVEIS  or set())}

    cst_pis_atual = str(meta.get("cst_pis") or "").zfill(2)
    cst_cofins_atual = str(meta.get("cst_cofins") or "").zfill(2)

    cst_pis_destino = str(enquadramento.get("cst_pis_destino") or "").zfill(2)
    cst_cofins_destino = str(enquadramento.get("cst_cofins_destino") or "").zfill(2)

    vl_bc_pis = dec_any(meta.get("vl_bc_pis") or meta.get("base_pis"))
    vl_bc_cofins = dec_any(meta.get("vl_bc_cofins") or meta.get("base_cofins"))
    vl_pis = dec_any(meta.get("vl_pis"))
    vl_cofins = dec_any(meta.get("vl_cofins"))

    if (
        cst_pis_atual in csts_creditaveis
        and cst_cofins_atual in csts_creditaveis
        and vl_bc_pis > 0
        and vl_bc_cofins > 0
        and vl_pis > 0
        and vl_cofins > 0
    ):
        return None

    problemas = []

    if cst_pis_destino and cst_pis_atual != cst_pis_destino:
        problemas.append("CST_PIS_DIVERGENTE")

    if cst_cofins_destino and cst_cofins_atual != cst_cofins_destino:
        problemas.append("CST_COFINS_DIVERGENTE")

    if vl_bc_pis <= 0:
        problemas.append("BASE_PIS_ZERADA")

    if vl_bc_cofins <= 0:
        problemas.append("BASE_COFINS_ZERADA")

    if vl_pis <= 0:
        problemas.append("CREDITO_PIS_NAO_APROVEITADO")

    if vl_cofins <= 0:
        problemas.append("CREDITO_COFINS_NAO_APROVEITADO")

    if not problemas:
        return None

    codigo_cenario = cenario.get("codigo_cenario")

    return {
        "ativo": True,
        "codigo": "CREDITO_NAO_APROVEITADO_V2",
        "tipo": "OPORTUNIDADE",
        "prioridade": "ALTA",
        "descricao": (
            f"Entrada elegível no cenário {codigo_cenario}, "
            f"mas com inconsistência de CST/base/crédito."
        ),
        "problemas": problemas,
        "impacto_financeiro": None,
        "meta": {
            **meta,
            "codigo_cenario": codigo_cenario,
            "fundamento_legal": cenario.get("fundamento_legal"),
            "enquadramento": enquadramento,
            "cod_cred": enquadramento.get("cod_cred"),
            "nat_bc_cred": enquadramento.get("nat_bc_cred"),
            "classificacao": classificacao,
            "cst_pis_atual": cst_pis_atual,
            "cst_cofins_atual": cst_cofins_atual,
            "cst_pis_destino": cst_pis_destino,
            "cst_cofins_destino": cst_cofins_destino,
            "vl_bc_pis": str(vl_bc_pis),
            "vl_bc_cofins": str(vl_bc_cofins),
            "vl_pis": str(vl_pis),
            "vl_cofins": str(vl_cofins),
        },
    }