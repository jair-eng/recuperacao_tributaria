from app.Legacy.fiscal.cat_fiscal import CatalogoFiscal
from app.Legacy.fiscal.constants import DOM_GERAL, DOM_CAFE, DOM_AGRO, DOM_TRANSP, DOM_POSTO, DOM_REVENDA_GAS
from app.Legacy.fiscal.regras.Diagnostico.insumos.insumos_helpers import classificar_item_transp
from app.Legacy.fiscal.settings_fiscais import CFOPS_ELEGIVEIS, CFOPS_TRANSP_SUBCONTRATACAO, CFOPS_TRANSP_IMOBILIZADO, \
    CFOPS_TRANSP_BLOCO_C, CFOPS_POSTO_COMBUSTIVEL, \
    CFOPS_REVENDA_GAS
from app.icms_ipi.icms_helpers import _only_digits, _norm_str

CFOPS_ELEGIVEIS_CREDITO = CFOPS_ELEGIVEIS

# -------------------------
# Helpers base
# -------------------------

def _texto_item(meta: dict) -> str:
    desc = _norm_str(meta.get("descricao") or meta.get("descricao_item")).upper()
    cod_item = _norm_str(meta.get("cod_item")).upper()
    return f"{desc} {cod_item}".strip()

def _tem_palavra(texto: str, palavras: list[str]) -> bool:
    return any(p in texto for p in palavras)
# -------------------------
# Elegibilidade TRANSP
# -------------------------
def item_transp_bloqueado(meta: dict) -> bool:
    texto = _texto_item(meta)

    palavras_bloqueio = [
        "RETIFICA", "RETÍFICA",
        "REFORMA",
        "MOTOR COMPLETO",
        "IMPLEMENTO",
        "MELHORIA ESTRUTURAL",
        "ADAPTACAO", "ADAPTAÇÃO",
        "CARROCERIA",
        "SEMI REBOQUE", "SEMI-REBOQUE",
        "CAVALO MECANICO", "CAVALO MECÂNICO",
        "VEICULO", "VEÍCULO",
        "CAMINHAO", "CAMINHÃO",
    ]

    # exceções para não bloquear itens operacionais típicos
    excecoes_operacionais = [
        "PNEU CAMINHAO", "PNEU CAMINHÃO",
        "LONA CAMINHAO", "LONA CAMINHÃO",
        "FILTRO CAMINHAO", "FILTRO CAMINHÃO",
        "OLEO CAMINHAO", "ÓLEO CAMINHÃO",
        "LUBRIFICANTE CAMINHAO", "LUBRIFICANTE CAMINHÃO",
        "BATERIA CAMINHAO", "BATERIA CAMINHÃO",
        "PECA CAMINHAO", "PEÇA CAMINHÃO",
        "ROLAMENTO CAMINHAO", "ROLAMENTO CAMINHÃO",
        "FREIO CAMINHAO", "FREIO CAMINHÃO",
    ]

    if _tem_palavra(texto, excecoes_operacionais):
        return False

    return _tem_palavra(texto, palavras_bloqueio)


def resolver_cst_credito_por_dominio(
    *,
    dominio: str,
    contexto: str | None = None,
) -> tuple[str, str]:
    dom = str(dominio or "").strip().upper()
    ctx = str(contexto or "").strip().upper()

    # 1) casos especiais primeiro (manual)
    if ctx == "LC192":
        return "61", "61"

    if ctx == "COMBUSTIVEL":
        return "50", "50"

    if ctx in {"EXPORTACAO", "EXPORTACAO_RESSARCIMENTO", "EXP_RESSARC"}:
        return "51", "51"

    # 2) domínio padrão
    if dom == DOM_TRANSP:
        return "50", "50"

    if dom in {DOM_CAFE, DOM_AGRO}:
        return "51", "51"

    # fallback = crédito normal padrão
    return "50", "50"