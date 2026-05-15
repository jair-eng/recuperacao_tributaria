from typing import Any, List
from decimal import Decimal
from app.fiscal.settings_fiscais import TRANSP_BUCKETS_DESC, TRANSP_BUCKETS_NCM
from typing import Any


def _norm_str(v: Any) -> str:
    return "" if v is None else str(v).strip()


def _get_dado(dados: Any, idx: int) -> str:
    arr = _get_dados_list(dados)
    if idx < 0 or idx >= len(arr):
        return ""
    return _norm_str(arr[idx])


def _extrair_chaves_c170(dados: Any) -> dict[str, str]:
    return {
        "descricao": _get_dado(dados, 2),
        "cfop": _somente_digitos(_get_dado(dados, 9)),
        "cod_cta": _get_dado(dados, 35),
    }

def _get_dados_list(dados: Any) -> List[Any]:
    if dados is None:
        return []
    if isinstance(dados, list):
        return dados
    if isinstance(dados, dict) and "dados" in dados:
        return list(dados.get("dados") or [])
    return list(dados) if isinstance(dados, (tuple,)) else []


def _somente_digitos(txt: str | None) -> str:
    return "".join(ch for ch in str(txt or "") if ch.isdigit())


def _to_decimal(v: Any) -> Decimal:
    if v is None or v == "":
        return Decimal("0")

    s = str(v).strip()
    if not s:
        return Decimal("0")

    try:
        # formato BR: 1.234,56
        if "," in s:
            s = s.replace(".", "").replace(",", ".")
        # formato padrão: 1234.56 → mantém

        return Decimal(s)
    except Exception:
        return Decimal("0")


def _normalizar_periodo(periodo: str | None) -> str:
    p = _somente_digitos(periodo)
    if len(p) >= 6:
        return p[:6]
    return ""


def _periodo_na_janela_2022(periodo: str | None) -> bool:
    p = _normalizar_periodo(periodo)
    return bool(p) and p.startswith("2022")


def _contains_any(texto: str, termos: list[str]) -> bool:
    txt = _norm_str(texto).lower()
    return any(t in txt for t in termos)


def _descricao_tokens(desc: str) -> set[str]:
    base = _norm_str(desc).lower()
    tokens = {
        t for t in base.replace("-", " ").replace("/", " ").split()
        if len(t) >= 4
    }
    stop = {"para", "com", "de", "da", "das", "dos", "item", "tipo"}
    return {t for t in tokens if t not in stop}


def _score_natureza(
    *,
    alvo_desc: str,
    alvo_cfop: str,
    alvo_ncm: str,
    cand_desc: str,
    cand_cfop: str,
    cand_ncm: str,
) -> int:
    score = 0

    if alvo_cfop and cand_cfop and alvo_cfop == cand_cfop:
        score += 4
    elif alvo_cfop and cand_cfop and alvo_cfop[:3] == cand_cfop[:3]:
        score += 2

    if alvo_ncm and cand_ncm and alvo_ncm == cand_ncm:
        score += 4
    elif alvo_ncm and cand_ncm and alvo_ncm[:4] == cand_ncm[:4]:
        score += 2

    ta = _descricao_tokens(alvo_desc)
    tc = _descricao_tokens(cand_desc)
    inter = ta & tc

    if len(inter) >= 2:
        score += 3
    elif len(inter) == 1:
        score += 1

    desc_a = _norm_str(alvo_desc).lower()
    desc_c = _norm_str(cand_desc).lower()

    grupos = [
        {"diesel", "combustivel", "combustível"},
        {"pneu", "recap"},
        {"filtro", "oleo", "óleo", "lubrificante"},
        {"freio", "lona", "rolamento", "peca", "peça"},
    ]

    for g in grupos:
        if any(x in desc_a for x in g) and any(x in desc_c for x in g):
            score += 2
            break

    return score


def desc_match(cat: dict, grupo_slug: str, texto: str) -> bool:
    if not texto:
        return False

    grupo = cat.get(grupo_slug) or []
    texto_norm = str(texto).lower()

    for item in grupo:
        item_norm = str(item).lower()

        if item_norm in texto_norm:
            return True

        partes = item_norm.split()
        if all(p in texto_norm for p in partes):
            return True

    return False


def _bucket_transp_por_ncm(
    cat,
    *,
    ncm: str,
) -> tuple[str | None, int, list[str], str | None]:
    ncm = str(ncm or "").strip()
    if not ncm:
        return None, 0, [], None

    for slug, bucket, pontos in TRANSP_BUCKETS_NCM:
        if not cat.match_codigo(slug, ncm):
            continue

        bucket_final = bucket
        if slug == "TRANSP_NCM_COMBUSTIVEL" and ncm == "31021010":
            bucket_final = "ARLA32"

        return (
            bucket_final,
            pontos,
            [f"catalogo_ncm:{slug}:{ncm}"],
            slug,
        )

    return None, 0, [], None


def _bucket_transp_por_desc(
    cat,
    *,
    desc_item: str,
) -> tuple[str | None, int, list[str], str | None]:
    desc_norm = str(desc_item or "").strip().lower()
    if not desc_norm:
        return None, 0, [], None

    for slug, bucket, pontos in TRANSP_BUCKETS_DESC:
        if not desc_match(cat, slug, desc_norm):
            continue

        bucket_final = bucket
        if slug == "TRANSP_DESC_COMBUSTIVEL" and "arla" in desc_norm:
            bucket_final = "ARLA32"

        return (
            bucket_final,
            pontos,
            [f"catalogo_desc:{slug}:{desc_norm[:80]}"],
            slug,
        )

    return None, 0, [], None


def _bucket_transp_fallback_desc(
    *,
    desc_item: str,
) -> tuple[str | None, int, list[str]]:
    desc_norm = str(desc_item or "").strip().lower()
    if not desc_norm:
        return None, 0, []

    if any(x in desc_norm for x in ["diesel", "disel", "oleo diesel", "oleo disel", "arla"]):
        bucket = "ARLA32" if "arla" in desc_norm else "COMBUSTIVEL"
        return bucket, 2, [f"descricao_fallback:{desc_norm[:80]}"]

    if any(x in desc_norm for x in ["pneu", "recap"]):
        return "PNEUS", 2, [f"descricao_fallback:{desc_norm[:80]}"]

    if any(x in desc_norm for x in ["oleo lubrificante", "lubrificante", "oleo cambio", "oleo eixo", "oleo hidraul"]):
        return "LUBRIFICANTES", 2, [f"descricao_fallback:{desc_norm[:80]}"]

    if any(x in desc_norm for x in [
        "filtro", "elemento", "sensor", "interruptor", "correia",
        "embreagem", "freio", "rolamento", "parafuso", "porca",
        "rebite", "bateria", "lampada", "guarnicao", "coifa",
        "abrac", "abraç", "valvula", "tubulacao", "mola",
    ]):
        return "MANUTENCAO", 1, [f"descricao_fallback:{desc_norm[:80]}"]

    if any(x in desc_norm for x in [
        "limpeza interna motor",
        "limpeza corretiva sist",
        "limpeza preventiva sist",
        "limpeza injecao",
        "limpeza injeção",
    ]):
        return "SERVICO", 1, [f"descricao_fallback:{desc_norm[:80]}"]

    return None, 0, []


def _subtipo_combustivel_por_desc(desc_item: str) -> str | None:
    desc = _norm_str(desc_item).lower()

    if _contains_any(desc, ["diesel s10", "diesel s-10", "óleo diesel", "oleo diesel", "diesel", "s10", "s500"]):
        return "DIESEL"

    if _contains_any(desc, ["gasolina aditivada", "gasolina comum", "gasolina"]):
        return "GASOLINA"

    if _contains_any(desc, ["etanol", "alcool", "álcool"]):
        return "ETANOL"

    if _contains_any(desc, ["arla", "arla 32", "arla32"]):
        return "ARLA32"

    return None


def _subtipo_lubrificante_por_desc(desc_item: str) -> str | None:
    desc = _norm_str(desc_item).lower()

    if _contains_any(desc, ["óleo motor", "oleo motor", "15w40", "10w30", "5w30", "ck4", "cj4", "sn", "sl"]):
        return "OLEO_MOTOR"

    if _contains_any(desc, ["óleo câmbio", "oleo cambio", "óleo cambio", "oleo câmbio", "transmissao", "transmissão"]):
        return "OLEO_CAMBIO"

    if _contains_any(desc, ["óleo eixo", "oleo eixo", "diferencial"]):
        return "OLEO_EIXO"

    if _contains_any(desc, ["óleo hidraul", "oleo hidraul", "hidráulico", "hidraulico"]):
        return "OLEO_HIDRAULICO"

    if _contains_any(desc, ["graxa"]):
        return "GRAXA"

    if _contains_any(desc, ["lubrificante", "óleo lubrificante", "oleo lubrificante", "óleo", "oleo"]):
        return "LUBRIFICANTE_GENERICO"

    return None


def _grau_confianca_por_score(score: int) -> str:
    if score >= 8:
        return "ALTA"
    if score >= 5:
        return "MEDIA"
    return "BAIXA"


def _classificar_item_transp_base(
    cat,
    *,
    ncm: str,
    desc_item: str,
    nome_part: str = "",
    cod_cta: str = "",
    origem_cod_cta: str = "",
) -> dict[str, Any]:
    """
    Classificação base TRANSP:
    bucket + score + evidências + origem do match.
    """
    score = 0
    bucket = None
    evidencias: list[str] = []
    match_source = None
    match_slug = None

    nome_part_norm = str(nome_part or "").strip().lower()

    if cod_cta:
        evidencias.append(f"cod_cta:{cod_cta}")
        if origem_cod_cta == "C170_MESMO_DOC":
            score += 1
            evidencias.append("origem_cod_cta:C170_MESMO_DOC")
        elif origem_cod_cta == "FALLBACK_0500":
            evidencias.append("origem_cod_cta:FALLBACK_0500")

    bucket_ncm, pontos_ncm, ev_ncm, slug_ncm = _bucket_transp_por_ncm(cat, ncm=ncm)
    if bucket_ncm:
        bucket = bucket_ncm
        score += pontos_ncm
        evidencias.extend(ev_ncm)
        match_source = "CATALOGO_NCM"
        match_slug = slug_ncm

    bucket_desc, pontos_desc, ev_desc, slug_desc = _bucket_transp_por_desc(cat, desc_item=desc_item)
    if bucket_desc:
        if bucket is None:
            bucket = bucket_desc
        score += pontos_desc
        evidencias.extend(ev_desc)
        if match_source is None:
            match_source = "CATALOGO_DESC"
            match_slug = slug_desc

    if bucket is None:
        bucket_fb, pontos_fb, ev_fb = _bucket_transp_fallback_desc(desc_item=desc_item)
        if bucket_fb:
            bucket = bucket_fb
            score += pontos_fb
            evidencias.extend(ev_fb)
            match_source = "FALLBACK_DESC"

    if "posto" in nome_part_norm:
        score += 2
        evidencias.append(f"fornecedor:{nome_part.strip()}")

    return {
        "bucket": bucket,
        "score": score,
        "evidencias": evidencias,
        "match_source": match_source,
        "match_slug": match_slug,
    }


def _classificar_regime_combustivel(
    *,
    ncm: str,
    desc_item: str,
    periodo: str,
    valor_icms: Any = None,
) -> dict[str, Any]:
    evidencias: list[str] = []
    teses_aplicaveis: list[str] = []

    flags = {
        "is_combustivel": True,
        "is_lubrificante": False,
        "is_arla32": False,
        "tem_indicio_monofasico": False,
        "tem_indicio_credito_presumido": False,
        "tem_indicio_janela_2022": False,
        "tem_indicio_icms_st": False,
        "tem_tese": False,
    }

    subtipo = _subtipo_combustivel_por_desc(desc_item) or "COMBUSTIVEL_NAO_IDENTIFICADO"
    regime_fiscal = "SENSIVEL"
    tratamento_motor = "ANALISE_MANUAL"
    permite_autofix = False
    exige_revisao_manual = True

    ncm_digits = _somente_digitos(ncm)
    vl_icms_dec = _to_decimal(valor_icms)

    if ncm_digits.startswith("2710") or ncm_digits.startswith("2711") or subtipo in {"DIESEL", "GASOLINA", "ETANOL"}:
        flags["tem_indicio_monofasico"] = True
        evidencias.append(f"regime_combustivel:possivel_monofasico:{ncm_digits or subtipo}")

    flags["tem_indicio_credito_presumido"] = True
    flags["tem_tese"] = True
    teses_aplicaveis.append("CREDITO_PRESUMIDO")
    evidencias.append("tese:credito_presumido:possivel")

    if _periodo_na_janela_2022(periodo):
        flags["tem_indicio_janela_2022"] = True
        flags["tem_tese"] = True
        teses_aplicaveis.append("JANELA_2022")
        evidencias.append(f"periodo:{_normalizar_periodo(periodo)}")
        evidencias.append("tese:janela_2022:possivel")

    if vl_icms_dec > 0:
        flags["tem_indicio_icms_st"] = True
        flags["tem_tese"] = True
        teses_aplicaveis.append("ICMS_ST_FORA_BASE")
        evidencias.append(f"vl_icms:{vl_icms_dec}")
        evidencias.append("tese:icms_st_fora_base:possivel")

    return {
        "bucket": "COMBUSTIVEL",
        "subbucket": subtipo,
        "regime_fiscal": regime_fiscal,
        "tratamento_motor": tratamento_motor,
        "permite_autofix": permite_autofix,
        "exige_revisao_manual": exige_revisao_manual,
        "teses_aplicaveis": list(dict.fromkeys(teses_aplicaveis)),
        "flags": flags,
        "evidencias_fiscais": evidencias,
    }


def _classificar_regime_arla32(
    *,
    periodo: str,
) -> dict[str, Any]:
    evidencias: list[str] = []

    flags = {
        "is_combustivel": False,
        "is_lubrificante": False,
        "is_arla32": True,
        "tem_indicio_monofasico": False,
        "tem_indicio_credito_presumido": False,
        "tem_indicio_janela_2022": False,
        "tem_indicio_icms_st": False,
        "tem_tese": False,
    }

    if _periodo_na_janela_2022(periodo):
        flags["tem_indicio_janela_2022"] = True
        evidencias.append(f"periodo:{_normalizar_periodo(periodo)}")

    return {
        "bucket": "ARLA32",
        "subbucket": "ARLA32",
        "regime_fiscal": "SENSIVEL",
        "tratamento_motor": "ANALISE_MANUAL",
        "permite_autofix": False,
        "exige_revisao_manual": True,
        "teses_aplicaveis": [],
        "flags": flags,
        "evidencias_fiscais": evidencias,
    }


def _classificar_regime_lubrificante(
    *,
    ncm: str,
    desc_item: str,
    periodo: str = "",
    valor_icms: Any = None,
) -> dict[str, Any]:
    evidencias: list[str] = []
    teses_aplicaveis: list[str] = []

    flags = {
        "is_combustivel": False,
        "is_lubrificante": True,
        "is_arla32": False,
        "tem_indicio_monofasico": False,
        "tem_indicio_credito_presumido": False,
        "tem_indicio_janela_2022": False,
        "tem_indicio_icms_st": False,
        "tem_tese": False,
    }

    subtipo = _subtipo_lubrificante_por_desc(desc_item) or "LUBRIFICANTE_NAO_IDENTIFICADO"
    ncm_digits = _somente_digitos(ncm)
    vl_icms_dec = _to_decimal(valor_icms)

    # Regra alinhada com o que decidimos:
    # - lubrificante sensível -> análise manual
    # - lubrificante não sensível -> autocorreção
    if ncm_digits.startswith("2710"):
        regime_fiscal = "MONOFASICO"
        tratamento_motor = "ANALISE_MANUAL"
        permite_autofix = False
        exige_revisao_manual = True
        flags["tem_indicio_monofasico"] = True
        flags["tem_tese"] = True
        evidencias.append(f"regime_lubrificante:possivel_monofasico:{ncm_digits}")

        if _periodo_na_janela_2022(periodo):
            flags["tem_indicio_janela_2022"] = True
            teses_aplicaveis.append("JANELA_2022")
            evidencias.append(f"periodo:{_normalizar_periodo(periodo)}")
            evidencias.append("tese:janela_2022:possivel")

        if vl_icms_dec > 0:
            flags["tem_indicio_icms_st"] = True
            teses_aplicaveis.append("ICMS_ST_FORA_BASE")
            evidencias.append(f"vl_icms:{vl_icms_dec}")
            evidencias.append("tese:icms_st_fora_base:possivel")
    else:
        regime_fiscal = "CREDITO_NORMAL"
        tratamento_motor = "AUTOFIX_SEGURO"
        permite_autofix = True
        exige_revisao_manual = False
        evidencias.append("situacao:lubrificante_nao_sensivel_insumo_essencial")

    return {
        "bucket": "LUBRIFICANTES",
        "subbucket": subtipo,
        "regime_fiscal": regime_fiscal,
        "tratamento_motor": tratamento_motor,
        "permite_autofix": permite_autofix,
        "exige_revisao_manual": exige_revisao_manual,
        "teses_aplicaveis": list(dict.fromkeys(teses_aplicaveis)),
        "flags": flags,
        "evidencias_fiscais": evidencias,
    }


def _classificar_combustivel_lubrificante_transp(
    *,
    base: dict[str, Any],
    ncm: str,
    desc_item: str,
    cst_pis: str = "",
    cst_cofins: str = "",
    cfop: str = "",
    periodo: str = "",
    valor_icms: Any = None,
    valor_ipi: Any = None,
    origem_dados: str = "",
) -> dict[str, Any]:
    """
    Refinador especializado para COMBUSTIVEL / LUBRIFICANTES / ARLA32.
    Recebe a classificação base pronta para evitar circularidade/recursão.
    """
    bucket = base.get("bucket")
    evidencias = list(base.get("evidencias") or [])
    match_source = base.get("match_source")
    match_slug = base.get("match_slug")
    score = int(base.get("score") or 0)

    periodo_norm = _normalizar_periodo(periodo)
    if periodo_norm:
        evidencias.append(f"periodo_input:{periodo_norm}")

    cfop_norm = _somente_digitos(cfop)
    if cfop_norm:
        evidencias.append(f"cfop:{cfop_norm}")

    if origem_dados:
        evidencias.append(f"origem_dados:{origem_dados}")

    if cst_pis:
        evidencias.append(f"cst_pis:{cst_pis}")
    if cst_cofins:
        evidencias.append(f"cst_cofins:{cst_cofins}")

    if valor_ipi not in (None, ""):
        evidencias.append(f"vl_ipi:{_to_decimal(valor_ipi)}")

    if bucket == "COMBUSTIVEL":
        fiscal = _classificar_regime_combustivel(
            ncm=ncm,
            desc_item=desc_item,
            periodo=periodo_norm,
            valor_icms=valor_icms,
        )
    elif bucket == "ARLA32":
        fiscal = _classificar_regime_arla32(
            periodo=periodo_norm,
        )
    elif bucket == "LUBRIFICANTES":
        fiscal = _classificar_regime_lubrificante(
            ncm=ncm,
            desc_item=desc_item,
            periodo=periodo_norm,
            valor_icms=valor_icms,
        )
    else:
        fiscal = {
            "bucket": bucket,
            "subbucket": None,
            "regime_fiscal": "INDETERMINADO",
            "tratamento_motor": "REVISAO_MANUAL",
            "permite_autofix": False,
            "exige_revisao_manual": True,
            "teses_aplicaveis": [],
            "flags": {
                "is_combustivel": False,
                "is_lubrificante": False,
                "is_arla32": False,
                "tem_indicio_monofasico": False,
                "tem_indicio_credito_presumido": False,
                "tem_indicio_janela_2022": False,
                "tem_indicio_icms_st": False,
                "tem_tese": False,
            },
            "evidencias_fiscais": [],
        }

    evidencias.extend(fiscal.get("evidencias_fiscais") or [])

    score_final = score
    if fiscal["tratamento_motor"] == "AUTOFIX_SEGURO":
        score_final += 2
    elif fiscal["tratamento_motor"] in {"SENSIVEL", "ANALISE_MANUAL"}:
        score_final += 1

    return {
        "bucket": fiscal.get("bucket") or bucket,
        "subbucket": fiscal.get("subbucket"),
        "regime_fiscal": fiscal.get("regime_fiscal"),
        "tratamento_motor": fiscal.get("tratamento_motor"),
        "permite_autofix": bool(fiscal.get("permite_autofix")),
        "exige_revisao_manual": bool(fiscal.get("exige_revisao_manual")),
        "teses_aplicaveis": list(fiscal.get("teses_aplicaveis") or []),
        "flags": dict(fiscal.get("flags") or {}),
        "score": score_final,
        "grau_confianca": _grau_confianca_por_score(score_final),
        "evidencias": evidencias,
        "match_source": match_source,
        "match_slug": match_slug,
    }


def classificar_item_transp(
    cat,
    *,
    ncm: str,
    desc_item: str,
    nome_part: str = "",
    cod_cta: str = "",
    origem_cod_cta: str = "",
    cst_pis: str = "",
    cst_cofins: str = "",
    cfop: str = "",
    periodo: str = "",
    valor_icms: Any = None,
    valor_ipi: Any = None,
    origem_dados: str = "",
) -> dict[str, Any]:
    """
    Fonte única de verdade para classificar item TRANSP.

    Mantém compatibilidade com chamadas antigas e, quando aplicável,
    refina automaticamente COMBUSTIVEL / LUBRIFICANTES / ARLA32.
    """
    base = _classificar_item_transp_base(
        cat,
        ncm=ncm,
        desc_item=desc_item,
        nome_part=nome_part,
        cod_cta=cod_cta,
        origem_cod_cta=origem_cod_cta,
    )

    bucket = base.get("bucket")

    if bucket in {"COMBUSTIVEL", "LUBRIFICANTES", "ARLA32"}:
        return _classificar_combustivel_lubrificante_transp(
            base=base,
            ncm=ncm,
            desc_item=desc_item,
            cst_pis=cst_pis,
            cst_cofins=cst_cofins,
            cfop=cfop,
            periodo=periodo,
            valor_icms=valor_icms,
            valor_ipi=valor_ipi,
            origem_dados=origem_dados,
        )

    score = int(base.get("score") or 0)

    # Defaults compatíveis para buckets não especializados
    permite_autofix = bucket in {"PNEUS", "MANUTENCAO"}
    tratamento_motor = "AUTOFIX_SEGURO" if permite_autofix else "REVISAO_MANUAL"

    return {
        "bucket": bucket,
        "subbucket": None,
        "regime_fiscal": "INDETERMINADO",
        "tratamento_motor": tratamento_motor,
        "permite_autofix": permite_autofix,
        "exige_revisao_manual": not permite_autofix,
        "teses_aplicaveis": [],
        "flags": {
            "is_combustivel": False,
            "is_lubrificante": False,
            "is_arla32": False,
            "tem_indicio_monofasico": False,
            "tem_indicio_credito_presumido": False,
            "tem_indicio_janela_2022": False,
            "tem_indicio_icms_st": False,
            "tem_tese": False,
        },
        "score": score,
        "grau_confianca": _grau_confianca_por_score(score),
        "evidencias": list(base.get("evidencias") or []),
        "match_source": base.get("match_source"),
        "match_slug": base.get("match_slug"),
    }