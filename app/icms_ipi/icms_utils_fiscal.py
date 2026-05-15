from __future__ import annotations

from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from app.db.models import EfdVersao, EfdArquivo
from app.db.models.nf_icms_base import NfIcmsBase
from app.db.models.nf_icms_item import NfIcmsItem
from app.fiscal.cat_fiscal import CatalogoFiscal
from app.fiscal.constants import DOM_GERAL, DOM_CAFE, DOM_AGRO, DOM_SUP, DOM_POSTO, DOM_TRANSP, DOM_REVENDA_GAS
from app.fiscal.ent_cat_fiscal import carregar_catalogo_fiscal
from app.fiscal.regras.Diagnostico.insumos.lc192_helpers import elegivel_lc192_combustivel
from app.fiscal.settings_fiscais import CFOPS_ELEGIVEIS, CFOPS_TRANSP_SUBCONTRATACAO, CFOPS_TRANSP_IMOBILIZADO, \
    CFOPS_POSTO_COMBUSTIVEL, CFOPS_REVENDA_GAS
from app.icms_ipi.icms_helpers import _only_digits, _norm_str, _match_dominio_transp_catalogo
from app.services.dominio_service import resolver_dominio_por_versao


CFOPS_ENTRADA_CREDITO = CFOPS_ELEGIVEIS


def _descricao_item_icms(item: NfIcmsItem) -> str:
    for attr in ("descr_item", "descricao", "descricao_item", "desc_item"):
        if hasattr(item, attr):
            v = getattr(item, attr)
            if v:
                return str(v).strip()
    return ""


def _ncm_item_icms(item: NfIcmsItem) -> str:
    for attr in ("ncm", "cod_ncm"):
        if hasattr(item, attr):
            v = getattr(item, attr)
            if v:
                return _only_digits(v)
    return ""


def _cfop_item_icms(item: NfIcmsItem) -> str:
    for attr in ("cfop", "cod_cfop"):
        if hasattr(item, attr):
            v = getattr(item, attr)
            if v:
                return _only_digits(v)
    return ""


def _cfop_elegivel_por_dominio(item: NfIcmsItem | str, *, dominio: str) -> bool:
    if isinstance(item, str):
        cfop = item.strip()
    else:
        cfop = _cfop_item_icms(item)
    dom = _norm_str(dominio).upper()

    if not cfop:
        return False

    if dom == DOM_TRANSP:
        if cfop in CFOPS_TRANSP_SUBCONTRATACAO:
            return False
        if cfop in CFOPS_TRANSP_IMOBILIZADO:
            return False
        return True
    if dom == DOM_POSTO:
        return cfop in CFOPS_POSTO_COMBUSTIVEL
    if dom == DOM_REVENDA_GAS:
        return cfop in CFOPS_REVENDA_GAS

    if dom in {DOM_CAFE, DOM_AGRO}:
        return cfop in CFOPS_ELEGIVEIS

    return cfop in CFOPS_ELEGIVEIS


def _item_aderente_dominio_cafe(item: NfIcmsItem) -> bool:
    ncm = _ncm_item_icms(item)
    desc = _norm_str(_descricao_item_icms(item)).upper()

    if ncm.startswith("0901"):
        return True

    palavras_cafe = [
        "CAFE",
        "CAFÉ",
        "GRAO DE CAFE",
        "GRÃO DE CAFÉ",
        "GRAOS DE CAFE",
        "GRÃOS DE CAFÉ",
        "CAFE TORRADO",
        "CAFE VERDE",
        "CAFE EM GRAO",
        "CAFÉ EM GRÃO",
    ]

    return any(p in desc for p in palavras_cafe)


def _item_aderente_dominio_agro(item: NfIcmsItem) -> bool:
    ncm = _ncm_item_icms(item)
    desc = _norm_str(_descricao_item_icms(item)).upper()

    prefixos_agro = ("1001", "1005", "1201")  # trigo, milho, soja
    if any(ncm.startswith(p) for p in prefixos_agro):
        return True

    palavras_agro = [
        "SOJA",
        "MILHO",
        "TRIGO",
        "GRAO",
        "GRÃO",
        "COMMODITY AGRICOLA",
        "COMMODITY AGRÍCOLA",
    ]

    return any(p in desc for p in palavras_agro)

# Item aderente Transportadora


def _item_aderente_dominio_transp(
    item: NfIcmsItem,
    catalogo: CatalogoFiscal | None = None,
) -> bool:
    ncm = _ncm_item_icms(item)
    desc = _norm_str(_descricao_item_icms(item)).upper()
    return _match_dominio_transp_catalogo(
        ncm=ncm,
        desc=desc,
        catalogo=catalogo,
    )

def _item_aderente_dominio(
    item: NfIcmsItem,
    dominio: str,
    catalogo: CatalogoFiscal | None = None,
) -> bool:
    dom = _norm_str(dominio).upper()

    if dom == DOM_CAFE:
        return _item_aderente_dominio_cafe(item)

    if dom == DOM_AGRO:
        return _item_aderente_dominio_agro(item)

    if dom == DOM_TRANSP:
        if not catalogo:
            return False
        return _item_aderente_dominio_transp(item, catalogo=catalogo)

    if dom == DOM_GERAL:
        return True

    # enquanto não houver regra específica, comportamento conservador
    if dom in {DOM_SUP, DOM_POSTO}:
        return True

    return False


def _item_icms_elegivel_para_insercao(
    item: NfIcmsItem,
    *,
    dominio: str,
    catalogo: CatalogoFiscal | None = None,
) -> bool:
    if not _cfop_elegivel_por_dominio(item, dominio=dominio):
        return False

    if not _item_aderente_dominio(item, dominio, catalogo=catalogo):
        return False

    return True


def _filtrar_notas_elegiveis_por_dominio(
    db: Session,
    *,
    versao_origem_id: int,
    notas: List[Tuple[NfIcmsBase, List[NfIcmsItem]]],
    contexto: str | None = None,
    periodo_lc192: str | None = None,
    regime_lc192: str | None = None,
) -> List[Tuple[NfIcmsBase, List[NfIcmsItem], str]]:
    dominio = resolver_dominio_por_versao(db, versao_origem_id) or DOM_GERAL

    versao = db.get(EfdVersao, int(versao_origem_id))
    empresa_id = None
    if versao:
        empresa_id = getattr(versao, "empresa_id", None)
        if empresa_id is None and getattr(versao, "arquivo_id", None):
            arquivo = db.get(EfdArquivo, int(versao.arquivo_id))
            empresa_id = getattr(arquivo, "empresa_id", None)

    catalogo = carregar_catalogo_fiscal(db, empresa_id=empresa_id)
    saida: List[Tuple[NfIcmsBase, List[NfIcmsItem], str]] = []

    for nf, itens in notas:
        itens_elegiveis: List[NfIcmsItem] = []

        for item in itens:
            ok = _item_icms_elegivel_para_insercao(
                item,
                dominio=dominio,
                catalogo=catalogo,
            )

            print(
                "[DBG FILTRO DOMINIO ITEM]",
                "nf_id=", getattr(nf, "id", None),
                "dominio=", dominio,
                "item_id=", getattr(item, "id", None),
                "cod_item=", getattr(item, "cod_item", None),
                "cfop=", getattr(item, "cfop", None),
                "ncm=", getattr(item, "ncm", None),
                "descr=", getattr(item, "descr_item", None) or getattr(item, "descricao_item", None),
                "ok=", ok,
                flush=True,
            )

            if ok:
                itens_elegiveis.append(item)
            if contexto == "LC192":
                ncm = str(getattr(item, "ncm", "") or "").strip()
                no_catalogo_lc192 = catalogo.ncm_match("COMB_LC192_NCM", ncm)

                if elegivel_lc192_combustivel(
                        meta={
                            "cfop": str(getattr(item, "cfop", "") or "").strip(),
                            "ncm": ncm,
                        },
                        periodo=periodo_lc192,
                        regime=regime_lc192,
                        ncm=ncm,
                        no_catalogo_lc192=no_catalogo_lc192,
                ):
                    itens_elegiveis.append(item)

                continue

            if _item_icms_elegivel_para_insercao(
                    item,
                    dominio=dominio,
                    catalogo=catalogo,
            ):
                itens_elegiveis.append(item)

        if itens_elegiveis:
            saida.append((nf, itens_elegiveis, dominio))

    return saida