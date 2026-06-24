from app.Legacy.fiscal.settings_fiscais import SLUGS_C170_POR_DOMINIO, SLUGS_CST_CREDITAVEIS
from app.domain.fiscal.catalogo.bloqueio_classificacao_por_dominio import item_bloqueado_classificacao
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.catalogo.semantica_produto import _grupos_ncm
from app.domain.fiscal.cenarios.avaliador_cenarios import avaliar_cenarios
from app.domain.fiscal.cenarios.cenario_enriquecimento import enriquecer_cenario_com_enquadramento
from app.domain.fiscal.diagnostico.diag_credito_nao_aproveitado import diagnosticar_credito_nao_aproveitado
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.utils.numbers import to_decimal
from decimal import Decimal


def meta_from_linha_cruzada_c170_local(linha: dict) -> dict:
    icms = linha.get("icms") or {}

    return {
        "periodo": linha.get("periodo"),
        "cod_item": linha.get("cod_item"),
        "descr_item": linha.get("descricao"),
        "ncm": linha.get("ncm"),
        "cfop": linha.get("cfop"),
        "cod_cta": linha.get("cod_cta"),

        "vl_item": icms.get("vl_item") or linha.get("valor_item_icms"),
        "vl_desc": icms.get("vl_desc") or linha.get("valor_desc_icms"),
        "vl_icms": icms.get("vl_icms") or linha.get("valor_icms"),

        "cst_pis": linha.get("cst_pis"),
        "cst_cofins": linha.get("cst_cofins"),
        "vl_bc_pis": linha.get("vl_bc_pis"),
        "vl_bc_cofins": linha.get("vl_bc_cofins"),
        "vl_pis": linha.get("vl_pis"),
        "vl_cofins": linha.get("vl_cofins"),

        "status_cruzamento": linha.get("status_cruzamento"),
        "tipo_match": linha.get("tipo_match"),
        "origem": "RELATORIO_LOCAL_C170_ICMS_CONTRIB",
    }

def resolver_categoria_c170_por_catalogo(
    *,
    meta: dict,
    catalogo,
    dominio: str,
) -> str:
    regras_dominio = SLUGS_C170_POR_DOMINIO.get(dominio) or {}

    grupos = set(_grupos_ncm(meta, catalogo))

    descricao = (
        meta.get("descr_item")
        or meta.get("descricao_item")
        or meta.get("descricao")
        or ""
    )

    if item_bloqueado_classificacao(
        dominio=dominio,
        descricao=descricao,
    ):
        return "NaoClassificado"

    for categoria, slugs in regras_dominio.items():
        for slug in slugs:
            if slug in grupos:
                return categoria

            if descricao and catalogo.desc_match(slug, descricao):
                return categoria

    return "NaoClassificado"

def calcular_base_recuperavel_c170_local(
    *,
    meta: dict,
    linha: dict,
) -> Decimal:
    if linha.get("status_cruzamento") == "NAO_ESCRITURADO":
        icms = linha.get("icms") or {}

        base_pis_icms = to_decimal(icms.get("vl_bc_pis"))
        base_cofins_icms = to_decimal(icms.get("vl_bc_cofins"))

        if base_pis_icms > 0:
            return base_pis_icms

        if base_cofins_icms > 0:
            return base_cofins_icms

    base_pis = to_decimal(meta.get("vl_bc_pis"))
    base_cofins = to_decimal(meta.get("vl_bc_cofins"))

    if base_pis > 0:
        return base_pis

    if base_cofins > 0:
        return base_cofins

    return max(
        Decimal("0.00"),
        to_decimal(meta.get("vl_item"))
        - to_decimal(meta.get("vl_desc"))
        - to_decimal(meta.get("vl_icms")),
    )

def diagnosticar_oportunidades_c170_local(
    *,
    db,
    linhas_cruzadas: list[dict],
    dominio: str = "GERAL",
) -> list[dict]:
    catalogo = carregar_catalogo_fiscal(db)
    oportunidades_c170 = []

    csts_creditaveis = {
        str(cst or "").strip().zfill(2)
        for slug in SLUGS_CST_CREDITAVEIS
        for cst in catalogo.codigos(slug)
    }

    cache_classificacao = {}
    cache_categoria = {}
    cache_enquadramento_por_codigo = {}

    for linha in linhas_cruzadas:

        meta = meta_from_linha_cruzada_c170_local(linha)
        meta["dominio"] = dominio

        descricao = (
            meta.get("descr_item")
            or meta.get("descricao_item")
            or meta.get("descricao")
            or ""
        )

        chave_classificacao = (
            dominio,
            str(meta.get("cod_item") or "").strip(),
            str(meta.get("ncm") or "").strip(),
            descricao.upper().strip(),
            str(meta.get("cfop") or "").strip(),
        )

        if chave_classificacao in cache_classificacao:
            classificacao = cache_classificacao[chave_classificacao]
        else:
            classificacao = classificar_item_fiscal(
                meta=meta,
                catalogo=catalogo,
            )
            cache_classificacao[chave_classificacao] = classificacao

        if not classificacao:
            continue

        chave_categoria = (
            dominio,
            str(meta.get("ncm") or "").strip(),
            descricao.upper().strip(),
        )

        if chave_categoria in cache_categoria:
            categoria = cache_categoria[chave_categoria]
        else:
            categoria = resolver_categoria_c170_por_catalogo(
                meta=meta,
                catalogo=catalogo,
                dominio=dominio,
            )
            cache_categoria[chave_categoria] = categoria

        if categoria == "NaoClassificado":
            continue

        cenario = avaliar_cenarios(
            meta,
            classificacao,
        )

        if not cenario:
            continue

        if not cenario.get("ativo"):
            continue

        fundamentos = cenario.get("fundamento_legal") or []
        codigo_cenario = str(fundamentos[0]).strip() if fundamentos else ""

        if not codigo_cenario:
            continue

        if codigo_cenario in cache_enquadramento_por_codigo:
            cenario = {
                **cenario,
                "codigo_cenario": codigo_cenario,
                "enquadramento": cache_enquadramento_por_codigo[codigo_cenario],
            }
        else:
            cenario = enriquecer_cenario_com_enquadramento(db, cenario)

            if not cenario.get("enquadramento"):
                continue

            cache_enquadramento_por_codigo[codigo_cenario] = cenario.get("enquadramento")

        diag = diagnosticar_credito_nao_aproveitado(
            meta=meta,
            classificacao=classificacao,
            cenario=cenario,
        )
        if not diag:
            continue

        meta_diag = diag.get("meta") or {}
        enquadramento = meta_diag.get("enquadramento") or {}

        cst_pis_atual = str(meta_diag.get("cst_pis_atual") or "").strip().zfill(2)
        cst_cofins_atual = str(meta_diag.get("cst_cofins_atual") or "").strip().zfill(2)

        if (
            linha.get("status_cruzamento") != "NAO_ESCRITURADO"
            and cst_pis_atual in csts_creditaveis
            and cst_cofins_atual in csts_creditaveis
        ):
            continue

        base_recuperavel = calcular_base_recuperavel_c170_local(
            meta=meta,
            linha=linha,
        )

        aliq_pis = to_decimal(enquadramento.get("aliq_pis"))
        aliq_cofins = to_decimal(enquadramento.get("aliq_cofins"))

        pis_recuperavel = (
            base_recuperavel * aliq_pis / Decimal("100")
        ).quantize(Decimal("0.01"))

        cofins_recuperavel = (
            base_recuperavel * aliq_cofins / Decimal("100")
        ).quantize(Decimal("0.01"))

        problemas = diag.get("problemas") or []

        codigo_diagnostico = (
            "SEM_EFD"
            if linha.get("status_cruzamento") == "NAO_ESCRITURADO"
            else diag.get("codigo")
        )

        if linha.get("status_cruzamento") == "NAO_ESCRITURADO":
            status_oportunidade = "NAO_ESCRITURADO"
        elif any("CST" in p for p in problemas):
            status_oportunidade = "CST_DIVERGENTE"
        elif any("BASE" in p for p in problemas):
            status_oportunidade = "BASE_ZERADA"
        elif any("CREDITO" in p for p in problemas):
            status_oportunidade = "CREDITO_NAO_APROVEITADO"
        else:
            status_oportunidade = "OUTRA_INCONSISTENCIA"

        oportunidades_c170.append({
            "periodo": meta.get("periodo"),
            "status_oportunidade": status_oportunidade,
            "codigo_diagnostico": codigo_diagnostico,
            "tipo": diag.get("tipo"),

            "categoria": categoria,
            "nat_bc_cred": enquadramento.get("nat_bc_cred"),
            "cod_cred": enquadramento.get("cod_cred"),

            "descricao": meta.get("descr_item"),
            "cod_item": meta.get("cod_item"),
            "ncm": meta.get("ncm"),
            "cfop": meta.get("cfop"),
            "cod_cta": meta.get("cod_cta"),

            "cst_pis_atual": cst_pis_atual,
            "cst_cofins_atual": cst_cofins_atual,
            "cst_pis_destino": meta_diag.get("cst_pis_destino"),
            "cst_cofins_destino": meta_diag.get("cst_cofins_destino"),

            "base_recuperavel": base_recuperavel,
            "pis_recuperavel": pis_recuperavel,
            "cofins_recuperavel": cofins_recuperavel,
            "credito_recuperavel": pis_recuperavel + cofins_recuperavel,

            "problemas": problemas,
            "motivo": ", ".join(problemas),

            "status_cruzamento": linha.get("status_cruzamento"),
            "tipo_match": linha.get("tipo_match"),
            "chv_nfe": linha.get("chv_nfe"),
            "num_doc": linha.get("num_doc"),
            "num_item": linha.get("num_item"),
        })

    print("[PERF C170 OPORTUNIDADES]", {
        "linhas_cruzadas": len(linhas_cruzadas),
        "cache_classificacao": len(cache_classificacao),
        "cache_categoria": len(cache_categoria),
        "cache_enquadramento": len(cache_enquadramento_por_codigo),
        "oportunidades": len(oportunidades_c170),
    })

    return oportunidades_c170