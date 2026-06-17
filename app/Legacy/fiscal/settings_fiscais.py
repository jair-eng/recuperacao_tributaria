from __future__ import annotations

from typing import Optional

COD_SIT_SKIP_CONS = {"06", "07"}

CFOPS_ELEGIVEIS = {"1101", "1102", "2101", "2102", "3101", "3102"}
# CSTs que obrigam M400/M800 (receita CST 04/06/07/08/09)
CSTS_RECEITA_M = {"04", "06", "07", "08", "09"}

# Receita tributada não cumulativa (RECEITA, não crédito!)
CSTS_RECEITA_NCUM = {"01", "02", "03"}

# CSTs que o 0900 considera "excluídas" de receita bruta (alíquota zero/isenta/suspensa)
CSTS_EXCL_AZ_ISENT_SUSP = {"06", "07", "08", "09"}

# CSTs tributados nao cumulativos (crédito)
CSTS_TRIB_NCUM = {"50", "51", "52", "53", "54", "55", "56"}

CSTS_NAO_CREDITAVEIS = frozenset({
    # monofásico / substituição / alíquota zero
    "04", "05", "06", "07", "08", "09",

    # OUTRAS OPERAÇÕES SEM CRÉDITO
    "49",  # outras operações de saída
    "98", "99",

    #
    "70", "71", "72", "73", "74", "75",
    # Erros
    "00"
})

# =========================
# TRANSPORTADORA - CFOPs
# =========================

CFOPS_TRANSP_COMBUSTIVEL = {"1407", "2407", "3407","1652", "2652", "3652"}

CFOPS_TRANSP_PECAS_OPERACAO = {"1403", "2403", "3403","1101", "1102", "2101", "2102", "3101", "3102"}

CFOPS_TRANSP_SUBCONTRATACAO = {"1350", "2350", "3350", "1931", "1932", "1933"}

CFOPS_TRANSP_IMOBILIZADO = {"1551", "2551", "2556", "3551"}

# bloco C (o que interessa agora)
CFOPS_TRANSP_BLOCO_C = (
    CFOPS_TRANSP_COMBUSTIVEL
    | CFOPS_TRANSP_PECAS_OPERACAO
)

CFOPS_REVENDA_GAS = {"1102", "2102", "3102","1403", "2403", "3403","1652","1653", "2652", "3652","1407", "1403", "2407", "3407",}
CFOPS_POSTO_COMBUSTIVEL = {"1652", "2652", "3652","1102", "2102", "3102","1403", "2403", "3403","1407", "2407", "3407",}

SLUGS_C170_POR_DOMINIO = {
    "TRANSP": {
        "CombustiveisLubrificantes": {
            "NCM_DIESEL",
            "NCM_LUBRIFICANTES",
            "NCM_ARLA32",
            "TRANSP_DESC_COMBUSTIVEL",
            "TRANSP_DESC_LUBRIFICANTES",
            "NCM_ADITIVOS_FLUIDOS",
            "NCM_GASOLINA",
        },
        "PecasManutencaoFrota": {
            "NCM_MANUTENCAO_VEICULAR",
            "NCM_PNEUS",
            "NCM_FILTROS",
            "NCM_AUTOPECAS",
            "TRANSP_DESC_MANUTENCAO",
            "TRANSP_DESC_PNEUS",
        },
    }
}

SLUGS_CST_CREDITAVEIS = {
    "CST_PIS_CREDITO_NCUM",
    "CST_PIS_CREDITO_PRESUMIDO",
}

TRANSP_NCM_SLUGS = (
    "TRANSP_NCM_COMBUSTIVEL",
    "TRANSP_NCM_LUBRIFICANTES",
    "TRANSP_NCM_MANUTENCAO",
    "TRANSP_NCM_PNEUS",
)

TRANSP_DESC_SLUGS = (
    "TRANSP_DESC_COMBUSTIVEL",
    "TRANSP_DESC_LUBRIFICANTES",
    "TRANSP_DESC_MANUTENCAO",
    "TRANSP_DESC_PNEUS",
)

TRANSP_BUCKETS_NCM = (
    ("TRANSP_NCM_COMBUSTIVEL", "COMBUSTIVEL", 5),
    ("TRANSP_NCM_PNEUS", "PNEUS", 4),
    ("TRANSP_NCM_LUBRIFICANTES", "LUBRIFICANTES", 4),
    ("TRANSP_NCM_MANUTENCAO", "MANUTENCAO", 3),
)

TRANSP_BUCKETS_DESC = (
    ("TRANSP_DESC_COMBUSTIVEL", "COMBUSTIVEL", 3),
    ("TRANSP_DESC_PNEUS", "PNEUS", 2),
    ("TRANSP_DESC_LUBRIFICANTES", "LUBRIFICANTES", 2),
    ("TRANSP_DESC_MANUTENCAO", "MANUTENCAO", 1),
)


# crédito normal posto/autopeças/lubrificantes
grupos_posto_credito_normal = (
    "TRANSP_NCM_LUBRIFICANTES",
    "AUTO_NCM_ADITIVOS_FLUIDOS",
    "AUTO_NCM_ARLA32",
    "AUTO_NCM_FILTROS",
    "AUTO_NCM_GERAIS",
    "AUTO_NCM_LIMPEZA_MANUTENCAO",
)

def _cst_sem_credito(cst: Optional[str]) -> bool:
    return str(cst or "").strip() in CSTS_NAO_CREDITAVEIS