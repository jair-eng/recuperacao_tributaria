from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from app.Legacy.fiscal.regras.Diagnostico.insumos.lc192_helpers import eh_periodo_lc192
from app.Legacy.fiscal.settings_fiscais import CSTS_TRIB_NCUM, CFOPS_ELEGIVEIS, CSTS_NAO_CREDITAVEIS
from relatorio_oportunidades.foto_oportunidade.aux_funcoes_foto import _digits, _s, _q2

# ============================================================
# Constantes de simulação
# ============================================================

ALIQUOTA_PIS = Decimal("0.0165")
ALIQUOTA_COFINS = Decimal("0.0760")

CFOPS_VALIDOS = CFOPS_ELEGIVEIS

CSTS_ORIGEM = CSTS_NAO_CREDITAVEIS

CSTS_CREDITAVEIS = CSTS_TRIB_NCUM

DOMINIOS_LC192 = {"POSTO", "REVENDA_GAS", "TRANSP"}
NCM_LC192 = {
    "22071090",  # Etanol
    "27101259",  # Gasolina
    "27101921",  # Óleo diesel
    "27101932",  # Óleo diesel S10 / óleo combustível
    "27111910",  # GLP
}

NCM_CAFE_PREFIXOS = ("0901",)
TERMOS_CAFE = ("CAFE", "CAFÉ")

PERIODOS_LC192 = {
    "032022", "042022", "052022",
    "062022", "072022", "082022",
}

def _eh_item_cafe_ou_agro(row: Dict[str, Any]) -> bool:
    ncm = _digits(row.get("ncm"))
    desc = _s(row.get("descricao")).upper()
    cod_item = _s(row.get("cod_item")).upper()

    if any(ncm.startswith(p) for p in NCM_CAFE_PREFIXOS):
        return True

    texto = f"{desc} {cod_item}"
    if any(t in texto for t in TERMOS_CAFE):
        return True

    return False

def _dominio_lc192_por_empresa(nome_empresa: str, participante: str = "") -> bool:
    texto = f"{_s(nome_empresa)} {_s(participante)}".upper()

    termos_ok = (
        "POSTO",
        "COMBUSTIVEL",
        "COMBUSTÍVEL",
        "PETROLEO",
        "PETRÓLEO",
        "GAS",
        "GÁS",
        "GLP",
        "TRANSPORT",
        "TRANSPORTE",
        "LOGISTICA",
        "LOGÍSTICA",
    )

    return any(t in texto for t in termos_ok)

# ============================================================
# Simulação
# ============================================================

def _simular_credito(
    *,
    cfop: str,
    cst_pis: str,
    valor_item: Decimal,
    valor_desconto: Decimal,
    valor_icms: Decimal,
    sem_efd: bool = False,
) -> Dict[str, Any]:
    """
    Simula a lógica do Foto Recuperação / motor:
      - guard-rail por CFOP
      - se CST origem -> simula CST 51
      - se CST já creditável -> mantém
      - base = valor_item - desconto - icms
    """
    base_simulada = Decimal("0")
    pis_simulado = Decimal("0")
    cofins_simulado = Decimal("0")
    credito_total = Decimal("0")

    cst_simulado = ""
    regra = ""
    elegivel = False
    motivo = ""

    if cfop not in CFOPS_VALIDOS:
        motivo = "CFOP fora do guard-rail"
        return {
            "elegivel": False,
            "motivo_simulacao": motivo,
            "base_simulada": base_simulada,
            "pis_simulado": pis_simulado,
            "cofins_simulado": cofins_simulado,
            "credito_simulado": credito_total,
            "cst_simulado": cst_simulado,
            "regra_simulada": regra,
        }

    base_simulada = valor_item - valor_desconto - valor_icms
    if base_simulada < 0:
        base_simulada = Decimal("0")

    if sem_efd:
        elegivel = True
        cst_simulado = "51"
        regra = "NAO_ESCRITURADO_CST51"
        motivo = "Item não escriturado na EFD Contribuições"

    elif cst_pis in CSTS_CREDITAVEIS:
        elegivel = True
        cst_simulado = cst_pis
        regra = "JA_CREDITAVEL"
        motivo = "Item já creditável no EFD"

    elif cst_pis in CSTS_ORIGEM:
        elegivel = True
        cst_simulado = "51"
        regra = "IND_AGRO_CST51"
        motivo = "CST origem elegível para simulação"

    else:
        motivo = "CST fora da simulação"

    if elegivel and base_simulada > 0:
        pis_simulado = base_simulada * ALIQUOTA_PIS
        cofins_simulado = base_simulada * ALIQUOTA_COFINS
        credito_total = pis_simulado + cofins_simulado

    return {
        "elegivel": elegivel,
        "motivo_simulacao": motivo,
        "base_simulada": _q2(base_simulada),
        "pis_simulado": _q2(pis_simulado),
        "cofins_simulado": _q2(cofins_simulado),
        "credito_simulado": _q2(credito_total),
        "cst_simulado": cst_simulado,
        "regra_simulada": regra,
    }

def _simular_credito_lc192(
    *,
    valor_item: Decimal,
    valor_desconto: Decimal,
    valor_icms: Decimal,
    cst_pis_atual: str = "",
    cst_cofins_atual: str = "",
) -> Dict[str, Any]:
    cst_pis_atual = (_s(cst_pis_atual) or "00").zfill(2)
    cst_cofins_atual = (_s(cst_cofins_atual) or "00").zfill(2)

    if (
        cst_pis_atual not in CSTS_NAO_CREDITAVEIS
        or cst_cofins_atual not in CSTS_NAO_CREDITAVEIS
    ):
        return {
            "elegivel": False,
            "motivo_simulacao": f"LC192 bloqueado: CST atual {cst_pis_atual}/{cst_cofins_atual} já creditável",
            "base_simulada": Decimal("0"),
            "pis_simulado": Decimal("0"),
            "cofins_simulado": Decimal("0"),
            "credito_simulado": Decimal("0"),
            "cst_simulado": "",
            "regra_simulada": "",
            "cenario_fiscal": "LC192",
            "natureza_credito_m": "206",
        }

    base = valor_item - valor_desconto - valor_icms
    if base < 0:
        base = Decimal("0")

    pis = base * ALIQUOTA_PIS
    cofins = base * ALIQUOTA_COFINS

    return {
        "elegivel": base > 0,
        "motivo_simulacao": "LC192 - combustível elegível",
        "base_simulada": _q2(base),
        "pis_simulado": _q2(pis),
        "cofins_simulado": _q2(cofins),
        "credito_simulado": _q2(pis + cofins),
        "cst_simulado": "61",
        "regra_simulada": "COMB_LC192_V1",
        "cenario_fiscal": "LC192",
        "natureza_credito_m": "206",
    }
def resolver_cenario_especial(row: Dict[str, Any]) -> Dict[str, Any]:
    ncm = _digits(row.get("ncm"))
    periodo = _s(row.get("periodo"))
    empresa = _s(row.get("empresa"))
    participante = _s(row.get("participante"))

    cfop = _s(row.get("cfop"))

    if (
            eh_periodo_lc192(periodo)
            and ncm in NCM_LC192
            and cfop in {"1407", "1403", "2407", "2403", "3407", "3403", "1652", "1653", "2652", "3652"}
    ):
        return {
            "elegivel": True,
            "tipo": "LC192",
            "regra": "COMB_LC192_V1",
        }

    return {"elegivel": False}
