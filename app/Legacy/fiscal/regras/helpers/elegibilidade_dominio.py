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
def resolver_dominio_meta(meta: dict) -> str:
    dom = _norm_str(meta.get("dominio") or meta.get("dominio_aplicado") or meta.get("dominio_versao")).upper()
    return dom or DOM_GERAL

def item_cfop_elegivel(meta: dict) -> bool:
    cfop = _only_digits(meta.get("cfop"))
    dominio = resolver_dominio_meta(meta)

    if not cfop:
        return False

    if dominio in {DOM_CAFE, DOM_AGRO}:
        return cfop in CFOPS_ELEGIVEIS_CREDITO

    if dominio == DOM_TRANSP:
        if cfop in CFOPS_TRANSP_SUBCONTRATACAO:
            return False
        if cfop in CFOPS_TRANSP_IMOBILIZADO:
            return False
        return True

    if dominio == DOM_POSTO:
        return cfop in CFOPS_POSTO_COMBUSTIVEL

    if dominio == DOM_REVENDA_GAS:
        return cfop in CFOPS_REVENDA_GAS

    return cfop in CFOPS_ELEGIVEIS_CREDITO

def _texto_item(meta: dict) -> str:
    desc = _norm_str(meta.get("descricao") or meta.get("descricao_item")).upper()
    cod_item = _norm_str(meta.get("cod_item")).upper()
    return f"{desc} {cod_item}".strip()

def _tem_palavra(texto: str, palavras: list[str]) -> bool:
    return any(p in texto for p in palavras)

# -------------------------
# Elegibilidade geral
# -------------------------
def item_elegivel_geral(meta: dict) -> bool:
    return item_cfop_elegivel(meta)

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


def item_elegivel_transp(meta: dict, cat: CatalogoFiscal | None = None) -> bool:
    cfop = _only_digits(meta.get("cfop"))
    ncm = _only_digits(meta.get("ncm"))
    texto = _texto_item(meta)


    # -------------------------
    # bloqueios estruturais
    # -------------------------
    if cfop in CFOPS_TRANSP_SUBCONTRATACAO:
        print("[TRANSP_ELEG] bloqueio=subcontratacao", flush=True)
        return False

    if cfop in CFOPS_TRANSP_IMOBILIZADO:
        print("[TRANSP_ELEG] bloqueio=imobilizado", flush=True)
        return False

    if item_transp_bloqueado(meta):
        print("[TRANSP_ELEG] bloqueio=item_transp_bloqueado", flush=True)
        return False

    # CFOP precisa estar dentro da régua atual
    if cfop not in CFOPS_TRANSP_BLOCO_C:
        print("[TRANSP_ELEG] bloqueio=cfop_fora_regua", flush=True)
        return False

    if not cat:
        print("[TRANSP_ELEG] bloqueio=sem_catalogo", flush=True)
        return False

    classificacao = classificar_item_transp(
        cat,
        ncm=ncm,
        desc_item=str(meta.get("descricao") or meta.get("descricao_item") or "").strip().lower(),
        nome_part=str(meta.get("nome_participante") or ""),
        cod_cta=str(meta.get("cod_cta") or ""),
        origem_cod_cta=str(meta.get("origem_cod_cta") or ""),
        cst_pis=str(meta.get("cst_pis") or ""),
        cst_cofins=str(meta.get("cst_cofins") or ""),
        cfop=cfop,
        periodo=str(meta.get("periodo") or ""),
        valor_icms=meta.get("vl_icms"),
        valor_ipi=meta.get("vl_ipi"),
        origem_dados="META",
    )

    bucket = classificacao.get("bucket")
    tratamento_motor = str(classificacao.get("tratamento_motor") or "")
    permite_autofix = bool(classificacao.get("permite_autofix"))
    flags = classificacao.get("flags") or {}
    tem_tese = bool(flags.get("tem_tese"))
    subbucket = classificacao.get("subbucket")



    # ------------------------------------------------
    # Itens com tese ou análise manual não entram
    # no fluxo automático de elegibilidade/autofix
    # ------------------------------------------------
    if tem_tese:
        print("[TRANSP_ELEG] bloqueio=tese_manual", flush=True)
        return False

    if tratamento_motor in {"ANALISE_MANUAL", "SENSIVEL", "REVISAO_MANUAL"}:
        print(f"[TRANSP_ELEG] bloqueio=tratamento:{tratamento_motor}", flush=True)
        return False

    if permite_autofix:
        print("[TRANSP_ELEG] ok=permite_autofix", flush=True)
        return True

    print("[TRANSP_ELEG] bloqueio=sem_elegibilidade_final", flush=True)
    return False


# -------------------------
# Elegibilidade CAFÉ / AGRO
# -------------------------
def item_elegivel_cafe(meta: dict) -> bool:
    cfop = _only_digits(meta.get("cfop"))

    if not cfop:
        return False

    # CFOPs típicos de entrada (mesmos que você já usa no projeto)
    CFOPS_CAFE_BLOCO_C = CFOPS_ELEGIVEIS

    if cfop not in CFOPS_CAFE_BLOCO_C:
        return False

    # dados do item
    ncm = _only_digits(meta.get("ncm"))
    texto = _texto_item(meta)

    # -------------------------------------------------
    # NCM catálogo simplificado (família 0901)
    # -------------------------------------------------
    if ncm and ncm.startswith("0901"):
        return True

    # -------------------------------------------------
    # fallback por descrição
    # -------------------------------------------------
    palavras_cafe = [
        "CAFE", "CAFÉ",
        "GRAO", "GRÃO",
        "TORRADO",
        "MOIDO", "MOÍDO",
    ]

    if _tem_palavra(texto, palavras_cafe):
        return True

    return False


def item_elegivel_agro(meta: dict) -> bool:
    cfop = _only_digits(meta.get("cfop"))

    if not cfop:
        return False

    if cfop not in CFOPS_ELEGIVEIS:
        return False

    # mantém sua lógica atual (NCM agro, descrição etc)
    return True

# -------------------------
# Elegibilidade POSTO
# -------------------------
def item_elegivel_posto(meta: dict, catalogo=None) -> bool:
    cfop = _only_digits(meta.get("cfop"))
    ncm = _only_digits(meta.get("ncm"))
    texto = _texto_item(meta)

    if not cfop:
        return False

    # Posto: compra/revenda de combustíveis e lubrificantes

    if cfop not in CFOPS_POSTO_COMBUSTIVEL:
        return False

    # Catálogo fiscal, se disponível
    if catalogo and ncm:

        if catalogo.ncm_match("COMB_LC192_NCM", ncm):
            return True
        if catalogo.ncm_match("MONO_COMBUSTIVEIS", ncm):
            return True
        if catalogo.ncm_match("TRANSP_NCM_COMBUSTIVEL", ncm):
            return True

    # NCMs combustíveis clássicos
    if ncm.startswith("271012"):  # gasolina
        return True

    if ncm.startswith("27101921"):  # diesel
        return True

    if ncm.startswith("220710") or ncm.startswith("220720"):  # etanol
        return True

    if ncm.startswith("27111910"):  # GLP
        return True

    palavras_combustivel = [
        "GASOLINA",
        "DIESEL",
        "OLEO DIESEL",
        "ÓLEO DIESEL",
        "ETANOL",
        "ALCOOL",
        "ÁLCOOL",
        "GLP",
        "GAS LIQUEFEITO",
        "GÁS LIQUEFEITO",
        "BOTIJAO",
        "BOTIJÃO",
    ]

    return _tem_palavra(texto, palavras_combustivel)

def item_elegivel_posto_credito_normal(meta: dict, catalogo=None) -> bool:
    cfop = _only_digits(meta.get("cfop"))
    ncm = _only_digits(meta.get("ncm"))

    if not cfop:
        return False

    if cfop not in CFOPS_POSTO_COMBUSTIVEL:
        return False

    if not catalogo or not ncm:
        return False

    # 1) primeiro crédito normal
    if (
        catalogo.ncm_match("TRANSP_NCM_LUBRIFICANTES", ncm)
        or catalogo.ncm_match("AUTO_NCM_FILTROS", ncm)
        or catalogo.ncm_match("AUTO_NCM_ARLA32", ncm)
        or catalogo.ncm_match("AUTO_NCM_ADITIVOS_FLUIDOS", ncm)
        or catalogo.ncm_match("AUTO_NCM_LIMPEZA_MANUTENCAO", ncm)
        or catalogo.ncm_match("AUTO_NCM_GERAIS", ncm)
    ):
        return True

    # 2) depois bloqueia combustível puro
    if catalogo.ncm_match("COMB_LC192_NCM", ncm):
        return False

    if catalogo.ncm_match("MONO_COMBUSTIVEIS", ncm):
        return False

    if catalogo.ncm_match("TRANSP_NCM_COMBUSTIVEL", ncm):
        return False

    return False

# -------------------------
# Elegibilidade REVENDA GÁS
# -------------------------
def item_elegivel_revenda_gas(meta: dict, catalogo=None) -> bool:
    cfop = _only_digits(meta.get("cfop"))
    ncm = _only_digits(meta.get("ncm"))
    texto = _texto_item(meta)

    if not cfop:
        return False

    if cfop not in CFOPS_REVENDA_GAS:
        return False

    # Revenda de gás: não usar COMB_LC192_NCM/MONO_COMBUSTIVEIS amplo,
    # porque isso deixa passar diesel/gasolina/etanol.
    if catalogo and ncm:
        if catalogo.ncm_match("REVENDA_GAS_LC192_NCM", ncm):
            return True

    # fallback seguro: GLP / gases liquefeitos
    if ncm == "27111910" or ncm.startswith("27111910"):
        return True

    palavras_gas = [
        "GLP",
        "GAS GLP",
        "GÁS GLP",
        "GAS LIQUEFEITO",
        "GÁS LIQUEFEITO",
        "BOTIJAO",
        "BOTIJÃO",
        "P13",
        "P20",
        "P45",
        "RECARGA GAS",
        "RECARGA GÁS",
    ]

    return _tem_palavra(texto, palavras_gas)

# -------------------------
# Dispatcher por domínio
# -------------------------
def item_cruzamento_elegivel_por_dominio(
    meta: dict,
    catalogo: CatalogoFiscal | None = None,
) -> bool:
    dominio = resolver_dominio_meta(meta)

    if dominio == DOM_TRANSP:
        return item_elegivel_transp(meta, cat=catalogo)
    if dominio == DOM_CAFE:
        return item_elegivel_cafe(meta)
    if dominio == DOM_AGRO:
        return item_elegivel_agro(meta)
    if dominio == DOM_POSTO:
        return (
            item_elegivel_posto(meta, catalogo=catalogo)
            or item_elegivel_posto_credito_normal(meta, catalogo=catalogo)
        )
    if dominio == DOM_REVENDA_GAS:
        return item_elegivel_revenda_gas(meta, catalogo=catalogo)
    return item_elegivel_geral(meta)


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
        return "51", "51"

    if dom in {DOM_CAFE, DOM_AGRO}:
        return "51", "51"

    # fallback = crédito normal padrão
    return "50", "50"