from __future__ import annotations

from typing import Any, Dict


def _grupos_ncm(meta: Dict[str, Any], catalogo: Any) -> set[str]:
    if catalogo is None:
        return set()

    ncm = meta.get("ncm") or meta.get("cod_ncm")

    if not ncm:
        return set()
    
    return catalogo.grupos_ncm(ncm)


def eh_cafe(meta, catalogo):

    if "NCM_CAFE" in _grupos_ncm(meta, catalogo):
        return True

    descricao = _texto_item(meta)

    if descricao and catalogo.desc_match("DESC_CAFE", descricao):
        return True

    return False

def eh_embalagem(meta, catalogo):

    if "NCM_EMBALAGENS" in _grupos_ncm(meta, catalogo):
        return True

    descricao = _texto_item(meta)

    if descricao and catalogo.desc_match("DESC_EMBALAGENS", descricao):
        return True

    return False


def eh_combustivel(meta: Dict[str, Any], catalogo: Any) -> bool:

    grupos = _grupos_ncm(meta, catalogo)


    return "NCM_COMBUSTIVEIS" in grupos


def eh_diesel(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_DIESEL" in _grupos_ncm(meta, catalogo)


def eh_gasolina(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_GASOLINA" in _grupos_ncm(meta, catalogo)


def eh_etanol(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_ETANOL" in _grupos_ncm(meta, catalogo)


def eh_glp(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_GLP" in _grupos_ncm(meta, catalogo)


def eh_lubrificante(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_LUBRIFICANTES" in _grupos_ncm(meta, catalogo)


def eh_manutencao_veicular(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_MANUTENCAO_VEICULAR" in _grupos_ncm(meta, catalogo)


def eh_pneu(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_PNEUS" in _grupos_ncm(meta, catalogo)


def eh_autopeca(meta: Dict[str, Any], catalogo: Any) -> bool:
    grupos = _grupos_ncm(meta, catalogo)

    return bool({
        "NCM_AUTOPECAS",
        "NCM_MANUTENCAO_VEICULAR",
        "NCM_FILTROS",
        "NCM_ADITIVOS_FLUIDOS",
        "NCM_PNEUS",
        "NCM_PECAS_MOTOS",
    } & grupos)

def eh_posto_geral(meta: Dict[str, Any], catalogo: Any) -> bool:
    grupos = _grupos_ncm(meta, catalogo)

    return bool({"AUTO_NCM_LIMPEZA_MANUTENCAO","AUTO_NCM_GERAIS",
    } & grupos)

def eh_filtro(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_FILTROS" in _grupos_ncm(meta, catalogo)


def eh_aditivo_fluido(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_ADITIVOS_FLUIDOS" in _grupos_ncm(meta, catalogo)


def eh_arla32(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_ARLA32" in _grupos_ncm(meta, catalogo)

def eh_peca_moto(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_PECAS_MOTOS" in _grupos_ncm(meta, catalogo)


def eh_agua_mineral(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_AGUA_MINERAL" in _grupos_ncm(meta, catalogo)


def eh_vasilhame_gas(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_VASILHAME_GAS" in _grupos_ncm(meta, catalogo)

def eh_maquininha_cartao(meta: Dict[str, Any], catalogo: Any) -> bool:
    return "NCM_MAQUININAS_CARTAO" in _grupos_ncm(meta, catalogo)

def _texto_item(meta: Dict[str, Any]) -> str:
    return (
        meta.get("descr_item")
        or meta.get("descricao_item")
        or meta.get("descricao")
        or meta.get("xprod")
        or ""
    )


def eh_fertilizante(meta: Dict[str, Any], catalogo: Any) -> bool:

    descricao = _texto_item(meta)
    # Bloqueio ARLA

    if descricao and catalogo.desc_match("DESC_ARLA32", descricao):
        return False

    if "NCM_FERTILIZANTES" in _grupos_ncm(meta, catalogo):

        # exige reforço textual
        if descricao and catalogo.desc_match("DESC_FERTILIZANTES", descricao):
            return True

    # Fallback descrição

    if descricao and catalogo.desc_match("DESC_FERTILIZANTES", descricao):
        return True

    return False

def classificar_produto_fiscal(
    meta: Dict[str, Any],
    catalogo: Any,
) -> Dict[str, bool]:

    return {
        "combustivel": eh_combustivel(meta, catalogo),
        "diesel": eh_diesel(meta, catalogo),
        "gasolina": eh_gasolina(meta, catalogo),
        "etanol": eh_etanol(meta, catalogo),
        "glp": eh_glp(meta, catalogo),
        "lubrificante": eh_lubrificante(meta, catalogo),
        "manutencao_veicular": eh_manutencao_veicular(meta, catalogo),
        "pneu": eh_pneu(meta, catalogo),
        "autopeca": eh_autopeca(meta, catalogo),
        "filtro": eh_filtro(meta, catalogo),
        "aditivo_fluido": eh_aditivo_fluido(meta, catalogo),
        "arla32": eh_arla32(meta, catalogo),
        "peca_moto": eh_peca_moto(meta, catalogo),
        "agua_mineral": eh_agua_mineral(meta, catalogo),
        "vasilhame_gas": eh_vasilhame_gas(meta, catalogo),
        "maquininha_cartao": eh_maquininha_cartao(meta, catalogo),
        "fertilizante": eh_fertilizante(meta, catalogo),
        "cafe": eh_cafe(meta, catalogo),
        "embalagem": eh_embalagem(meta, catalogo),
        "posto_geral": eh_posto_geral(meta, catalogo),
    }