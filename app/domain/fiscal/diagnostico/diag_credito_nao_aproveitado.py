from __future__ import annotations

from typing import Any, Dict, Optional
from app.Legacy.fiscal.settings_fiscais import CSTS_CREDITAVEIS
from app.utils.numbers import dec_any, q2
from decimal import Decimal
import logging
logger = logging.getLogger(__name__)


def diagnosticar_credito_nao_aproveitado(
    meta: Dict[str, Any],
    classificacao: Dict[str, Any],
    cenario: Dict[str, Any],
) -> Optional[Dict[str, Any]]:

    if not cenario or not cenario.get("ativo"):
        return None

    codigo_cenario = (
            cenario.get("cenario")
            or cenario.get("codigo_cenario")
            or ""
    )

    if codigo_cenario.startswith("TRANSP_USO_CONSUMO_"):
        return {
            "ativo": True,
            "codigo": "CFOP_USO_CONSUMO",
            "tipo": "SEM_ACAO",
            "prioridade": "MEDIA",
            "descricao": (
                "Item relacionado à atividade da transportadora, mas escriturado "
                "com CFOP de uso ou consumo. A apropriação do crédito depende de "
                "análise fiscal e possível correção prévia da EFD ICMS/IPI."
            ),
            "meta": {
                **meta,
                "codigo_cenario": codigo_cenario,
                "fundamento_legal": cenario.get("fundamento_legal") or [],
                "justificativa_cenario": cenario.get("justificativa") or [],
                "classificacao": classificacao,
                "motivo_bloqueio": "CFOP_USO_CONSUMO",
                "acao_automatica_permitida": False,
            },
        }

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

    if (
            cst_pis_atual in csts_creditaveis
            and cst_cofins_atual in csts_creditaveis
    ):
        return None

    cst_pis_destino = str(enquadramento.get("cst_pis_destino") or "").zfill(2)
    cst_cofins_destino = str(enquadramento.get("cst_cofins_destino") or "").zfill(2)

    vl_bc_pis = dec_any(meta.get("vl_bc_pis") or meta.get("base_pis"))
    vl_bc_cofins = dec_any(meta.get("vl_bc_cofins") or meta.get("base_cofins"))
    vl_pis = dec_any(meta.get("vl_pis"))
    vl_cofins = dec_any(meta.get("vl_cofins"))

    aliq_pis_destino = dec_any(enquadramento.get("aliq_pis"))
    aliq_cofins_destino = dec_any(enquadramento.get("aliq_cofins"))

    vl_pis_esperado = q2(
        vl_bc_pis * aliq_pis_destino / Decimal("100")
    )

    vl_cofins_esperado = q2(
        vl_bc_cofins * aliq_cofins_destino / Decimal("100")
    )

    vl_item = dec_any(meta.get("vl_item"))
    vl_desc = dec_any(meta.get("vl_desc"))

    base_economica = q2(vl_item - vl_desc)

    problemas = []

    if cst_pis_destino and cst_pis_atual != cst_pis_destino:
        problemas.append("CST_PIS_DIVERGENTE")

    if cst_cofins_destino and cst_cofins_atual != cst_cofins_destino:
        problemas.append("CST_COFINS_DIVERGENTE")

    if vl_bc_pis <= 0:
        problemas.append("BASE_PIS_ZERADA")

    if vl_bc_cofins <= 0:
        problemas.append("BASE_COFINS_ZERADA")

    if vl_pis != vl_pis_esperado:
        problemas.append("CREDITO_PIS_DIVERGENTE")

    if vl_cofins != vl_cofins_esperado:
        problemas.append("CREDITO_COFINS_DIVERGENTE")

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