from __future__ import annotations

from typing import Any, Dict


def eh_entrada(meta, catalogo):

    cfop = meta.get("cfop")

    grupos = catalogo.grupos_cfop(cfop)


    return bool({
        "CFOP_ENTRADA",
        "CFOP_ENTRADA_REVENDA",
        "CFOP_ENTRADA_INSUMO",
        "CFOP_USO_CONSUMO",
    } & grupos)


def eh_entrada_cafe(meta: Dict[str, Any], catalogo: Any) -> bool:
    dominio = str(meta.get("dominio") or "").strip()
    if dominio not in {"CAFE", "DOM_CAFE"}:
        return False

    cfop = meta.get("cfop")

    grupos = catalogo.grupos_cfop(cfop)

    return bool({
        "CFOP_CAFE_TORRADO_ENTRADA",
    } & grupos)

def eh_saida(meta: Dict[str, Any], catalogo: Any) -> bool:
    cfop = meta.get("cfop")

    grupos = catalogo.grupos_cfop(cfop)

    return bool({
        "CFOP_SAIDA",
        "CFOP_SAIDA_REVENDA",
    } & grupos)


def eh_revenda(meta: Dict[str, Any], catalogo: Any) -> bool:
    cfop = meta.get("cfop")

    grupos = catalogo.grupos_cfop(cfop)

    return bool({
        "CFOP_ENTRADA_REVENDA",
        "CFOP_SAIDA_REVENDA",
    } & grupos)


def eh_exportacao(meta: Dict[str, Any], catalogo: Any) -> bool:
    cfop = meta.get("cfop")

    grupos = catalogo.grupos_cfop(cfop)

    return "CFOP_EXPORTACAO" in grupos


def eh_transferencia(meta: Dict[str, Any], catalogo: Any) -> bool:
    cfop = meta.get("cfop")

    grupos = catalogo.grupos_cfop(cfop)

    return bool({
        "CFOP_TRANSFERENCIA_ENTRADA",
        "CFOP_TRANSFERENCIA_SAIDA",
    } & grupos)


def eh_imobilizado(meta: Dict[str, Any], catalogo: Any) -> bool:
    cfop = meta.get("cfop")

    grupos = catalogo.grupos_cfop(cfop)

    return "CFOP_ENTRADA_IMOBILIZADO" in grupos


def eh_servico(meta: Dict[str, Any], catalogo: Any) -> bool:
    cfop = meta.get("cfop")

    grupos = catalogo.grupos_cfop(cfop)

    return "CFOP_SERVICO" in grupos


def eh_sem_credito(meta: Dict[str, Any], catalogo: Any) -> bool:
    cst_pis = meta.get("cst_pis")
    cst_cofins = meta.get("cst_cofins")

    grupos_pis = catalogo.grupos_cst_pis(cst_pis)
    grupos_cofins = catalogo.grupos_cst_cofins(cst_cofins)

    grupos = grupos_pis | grupos_cofins

    return bool({
        "CST_PIS_AQUIS_SEM_CRED",
        "CST_COFINS_AQUIS_SEM_CRED",
        "CST_PIS_ZERO_ISENTA_SUSP",
        "CST_COFINS_ZERO_ISENTA_SUSP",
    } & grupos)


def classificar_operacao_fiscal(
    meta: Dict[str, Any],
    catalogo: Any,
) -> Dict[str, bool]:

    return {
        "entrada": eh_entrada(meta, catalogo),
        "saida": eh_saida(meta, catalogo),
        "revenda": eh_revenda(meta, catalogo),
        "exportacao": eh_exportacao(meta, catalogo),
        "sem_credito": eh_sem_credito(meta, catalogo),
        "transferencia": eh_transferencia(meta, catalogo),
        "imobilizado": eh_imobilizado(meta, catalogo),
        "servico": eh_servico(meta, catalogo),
        "entrada_cafe": eh_entrada_cafe(meta, catalogo),
    }