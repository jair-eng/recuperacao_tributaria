from app.Legacy.fiscal.settings_fiscais import SLUGS_C170_POR_DOMINIO, SLUGS_CST_CREDITAVEIS
from app.domain.fiscal.catalogo.bloqueio_classificacao_por_dominio import item_bloqueado_classificacao
from app.domain.fiscal.catalogo.classificacao_fiscal import classificar_item_fiscal
from app.domain.fiscal.catalogo.semantica_produto import _grupos_ncm
from app.domain.fiscal.cenarios.avaliador_cenarios import avaliar_cenarios
from app.domain.fiscal.cenarios.cenario_enriquecimento import enriquecer_cenario_com_enquadramento
from app.domain.fiscal.diagnostico.diag_credito_nao_aproveitado import diagnosticar_credito_nao_aproveitado
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.utils.numbers import to_decimal
from collections import defaultdict
from typing import Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


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
    classificacao: dict | None = None,
) -> str:
    dominio = str(dominio or "").strip().upper()
    classificacao = classificacao or {}

    operacao = classificacao.get("operacao") or {}
    produto = classificacao.get("produto") or {}

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

    # ------------------------------------------------------------
    # Prioriza a classificação semântica já calculada
    # ------------------------------------------------------------
    if dominio == "CAFE":
        if operacao.get("entrada_cafe") or produto.get("cafe"):
            return "MateriaPrima"

        if produto.get("diesel"):
            return "CombustiveisLubrificantes"

        if produto.get("combustivel"):
            return "CombustiveisLubrificantes"

        if produto.get("fertilizante"):
            return "MercadoriasInsumoConsumo"

        if produto.get("embalagem"):
            return "MercadoriasInsumoConsumo"

    # ------------------------------------------------------------
    # Fallback legado por catálogo
    # ------------------------------------------------------------
    regras_dominio = SLUGS_C170_POR_DOMINIO.get(dominio) or {}
    grupos = set(_grupos_ncm(meta, catalogo))

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
    oportunidades_c170: list[dict] = []

    dominio = str(dominio or "GERAL").strip().upper()

    stats = {
        "sem_classificacao": 0,
        "nao_classificado": 0,
        "sem_cenario": 0,
        "cenario_inativo": 0,
        "sem_codigo_cenario": 0,
        "sem_enquadramento": 0,
        "sem_diagnostico": 0,
        "ja_creditado": 0,
        "base_zerada": 0,
        "incluidos": 0,
    }

    # Mantém somente pequenas amostras para facilitar novos domínios,
    # sem inundar o terminal com um log para cada item.
    LIMITE_AMOSTRAS = 5

    amostras: dict[str, list[dict]] = {
        "sem_classificacao": [],
        "nao_classificado": [],
        "sem_cenario": [],
        "cenario_inativo": [],
        "sem_codigo_cenario": [],
        "sem_enquadramento": [],
        "sem_diagnostico": [],
        "base_zerada": [],
    }

    contagem_periodos = defaultdict(int)
    contagem_status_cruzamento = defaultdict(int)
    contagem_categorias = defaultdict(int)
    contagem_cenarios = defaultdict(int)
    contagem_sem_cenario_por_categoria_cfop = defaultdict(int)
    contagem_oportunidades_por_tipo = defaultdict(int)
    contagem_oportunidades_por_categoria = defaultdict(int)

    csts_creditaveis = {
        str(cst or "").strip().zfill(2)
        for slug in SLUGS_CST_CREDITAVEIS
        for cst in catalogo.codigos(slug)
    }

    cache_classificacao: dict[tuple, dict | None] = {}
    cache_categoria: dict[tuple, str] = {}
    cache_enquadramento_por_codigo: dict[str, dict] = {}

    def adicionar_amostra(
        grupo: str,
        *,
        meta: dict,
        linha: dict,
        categoria: str | None = None,
        codigo_cenario: str | None = None,
        classificacao: dict | None = None,
        detalhe: Any = None,
    ) -> None:
        destino = amostras.get(grupo)

        if destino is None or len(destino) >= LIMITE_AMOSTRAS:
            return

        destino.append({
            "periodo": meta.get("periodo"),
            "cod_item": meta.get("cod_item"),
            "descricao": meta.get("descr_item"),
            "ncm": meta.get("ncm"),
            "cfop": meta.get("cfop"),
            "categoria": categoria,
            "cenario": codigo_cenario,
            "status_cruzamento": meta.get("status_cruzamento"),
            "tipo_match": linha.get("tipo_match"),
            "chv_nfe": linha.get("chv_nfe"),
            "num_doc": linha.get("num_doc"),
            "num_item": linha.get("num_item"),
            "operacao": (
                (classificacao or {}).get("operacao")
                if classificacao
                else None
            ),
            "produto": (
                (classificacao or {}).get("produto")
                if classificacao
                else None
            ),
            "detalhe": detalhe,
        })

    for linha in linhas_cruzadas:
        meta = meta_from_linha_cruzada_c170_local(linha)
        meta["dominio"] = dominio

        status_cruzamento = str(
            linha.get("status_cruzamento")
            or meta.get("status_cruzamento")
            or ""
        ).strip().upper()

        meta["status_cruzamento"] = status_cruzamento

        descricao = str(
            meta.get("descr_item")
            or meta.get("descricao_item")
            or meta.get("descricao")
            or ""
        ).strip()

        # Mantém uma descrição canônica dentro do meta.
        meta["descr_item"] = descricao

        periodo = str(meta.get("periodo") or "").strip()
        cfop = str(meta.get("cfop") or "").strip()
        cod_item = str(meta.get("cod_item") or "").strip()
        ncm = str(meta.get("ncm") or "").strip()

        contagem_periodos[periodo or "SEM_PERIODO"] += 1
        contagem_status_cruzamento[
            status_cruzamento or "SEM_STATUS"
        ] += 1

        chave_classificacao = (
            dominio,
            cod_item,
            ncm,
            descricao.upper(),
            cfop,
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
            stats["sem_classificacao"] += 1

            adicionar_amostra(
                "sem_classificacao",
                meta=meta,
                linha=linha,
            )
            continue

        chave_categoria = (
            dominio,
            cod_item,
            ncm,
            descricao.upper(),
            cfop,
        )

        if chave_categoria in cache_categoria:
            categoria = cache_categoria[chave_categoria]
        else:
            categoria = resolver_categoria_c170_por_catalogo(
                meta=meta,
                catalogo=catalogo,
                dominio=dominio,
                classificacao=classificacao,
            )
            cache_categoria[chave_categoria] = categoria

        if categoria == "NaoClassificado":
            stats["nao_classificado"] += 1

            adicionar_amostra(
                "nao_classificado",
                meta=meta,
                linha=linha,
                classificacao=classificacao,
            )
            continue

        contagem_categorias[categoria] += 1

        meta["categoria"] = categoria
        meta["categoria_catalogo"] = categoria

        cenario = avaliar_cenarios(
            meta,
            classificacao,
        )

        if not cenario:
            stats["sem_cenario"] += 1
            contagem_sem_cenario_por_categoria_cfop[
                (categoria, cfop or "SEM_CFOP")
            ] += 1

            adicionar_amostra(
                "sem_cenario",
                meta=meta,
                linha=linha,
                categoria=categoria,
                classificacao=classificacao,
            )
            continue

        if not cenario.get("ativo"):
            stats["cenario_inativo"] += 1

            adicionar_amostra(
                "cenario_inativo",
                meta=meta,
                linha=linha,
                categoria=categoria,
                classificacao=classificacao,
                detalhe={
                    "cenario": cenario,
                },
            )
            continue

        codigo_cenario = str(
            cenario.get("codigo_cenario")
            or cenario.get("cenario")
            or ""
        ).strip()

        if not codigo_cenario:
            fundamentos_raw = cenario.get("fundamento_legal") or []

            if isinstance(fundamentos_raw, str):
                codigo_cenario = fundamentos_raw.strip()

            elif isinstance(fundamentos_raw, (list, tuple, set)):
                codigo_cenario = next(
                    (
                        str(fundamento).strip()
                        for fundamento in fundamentos_raw
                        if str(fundamento or "").strip()
                    ),
                    "",
                )

        if not codigo_cenario:
            stats["sem_codigo_cenario"] += 1

            adicionar_amostra(
                "sem_codigo_cenario",
                meta=meta,
                linha=linha,
                categoria=categoria,
                classificacao=classificacao,
                detalhe={
                    "cenario": cenario,
                },
            )
            continue

        contagem_cenarios[codigo_cenario] += 1

        if codigo_cenario in cache_enquadramento_por_codigo:
            cenario = {
                **cenario,
                "codigo_cenario": codigo_cenario,
                "enquadramento": (
                    cache_enquadramento_por_codigo[codigo_cenario]
                ),
            }
        else:
            cenario = {
                **cenario,
                "codigo_cenario": codigo_cenario,
            }

            cenario = enriquecer_cenario_com_enquadramento(
                db,
                cenario,
            )

            enquadramento_carregado = (
                cenario.get("enquadramento") or {}
            )

            if not enquadramento_carregado:
                stats["sem_enquadramento"] += 1

                adicionar_amostra(
                    "sem_enquadramento",
                    meta=meta,
                    linha=linha,
                    categoria=categoria,
                    codigo_cenario=codigo_cenario,
                    classificacao=classificacao,
                )
                continue

            cache_enquadramento_por_codigo[codigo_cenario] = (
                enquadramento_carregado
            )

        enquadramento = cenario.get("enquadramento") or {}

        if not enquadramento:
            stats["sem_enquadramento"] += 1

            adicionar_amostra(
                "sem_enquadramento",
                meta=meta,
                linha=linha,
                categoria=categoria,
                codigo_cenario=codigo_cenario,
                classificacao=classificacao,
            )
            continue

        if status_cruzamento == "NAO_ESCRITURADO":
            diag = {
                "codigo": "SEM_EFD",
                "tipo": "OPORTUNIDADE",
                "problemas": ["NAO_ESCRITURADO"],
                "meta": {
                    **meta,
                    "enquadramento": enquadramento,
                    "cst_pis_atual": "",
                    "cst_cofins_atual": "",
                    "cst_pis_destino": enquadramento.get(
                        "cst_pis_destino"
                    ),
                    "cst_cofins_destino": enquadramento.get(
                        "cst_cofins_destino"
                    ),
                },
            }
        else:
            diag = diagnosticar_credito_nao_aproveitado(
                meta=meta,
                classificacao=classificacao,
                cenario=cenario,
            )

        if not diag:
            stats["sem_diagnostico"] += 1

            adicionar_amostra(
                "sem_diagnostico",
                meta=meta,
                linha=linha,
                categoria=categoria,
                codigo_cenario=codigo_cenario,
                classificacao=classificacao,
                detalhe={
                    "enquadramento": enquadramento,
                },
            )
            continue

        meta_diag = diag.get("meta") or {}

        cst_pis_atual = str(
            meta_diag.get("cst_pis_atual") or ""
        ).strip().zfill(2)

        cst_cofins_atual = str(
            meta_diag.get("cst_cofins_atual") or ""
        ).strip().zfill(2)

        if (
            status_cruzamento != "NAO_ESCRITURADO"
            and cst_pis_atual in csts_creditaveis
            and cst_cofins_atual in csts_creditaveis
        ):
            stats["ja_creditado"] += 1
            continue

        base_recuperavel = calcular_base_recuperavel_c170_local(
            meta=meta,
            linha=linha,
        )

        if base_recuperavel <= 0:
            stats["base_zerada"] += 1

            adicionar_amostra(
                "base_zerada",
                meta=meta,
                linha=linha,
                categoria=categoria,
                codigo_cenario=codigo_cenario,
                classificacao=classificacao,
                detalhe={
                    "vl_item": meta.get("vl_item"),
                    "vl_desc": meta.get("vl_desc"),
                    "vl_icms": meta.get("vl_icms"),
                    "vl_bc_pis": meta.get("vl_bc_pis"),
                    "vl_bc_cofins": meta.get("vl_bc_cofins"),
                    "icms_vl_bc_pis": (
                        (linha.get("icms") or {}).get("vl_bc_pis")
                    ),
                    "icms_vl_bc_cofins": (
                        (linha.get("icms") or {}).get(
                            "vl_bc_cofins"
                        )
                    ),
                },
            )

        aliq_pis = to_decimal(
            enquadramento.get("aliq_pis")
        )
        aliq_cofins = to_decimal(
            enquadramento.get("aliq_cofins")
        )

        pis_recuperavel = (
            base_recuperavel
            * aliq_pis
            / Decimal("100")
        ).quantize(Decimal("0.01"))

        cofins_recuperavel = (
            base_recuperavel
            * aliq_cofins
            / Decimal("100")
        ).quantize(Decimal("0.01"))

        problemas = diag.get("problemas") or []

        codigo_diagnostico = (
            "SEM_EFD"
            if status_cruzamento == "NAO_ESCRITURADO"
            else diag.get("codigo")
        )

        if status_cruzamento == "NAO_ESCRITURADO":
            status_oportunidade = "NAO_ESCRITURADO"

        elif any(
            "CST" in str(problema).upper()
            for problema in problemas
        ):
            status_oportunidade = "CST_DIVERGENTE"

        elif any(
            "BASE" in str(problema).upper()
            for problema in problemas
        ):
            status_oportunidade = "BASE_ZERADA"

        elif any(
            "CREDITO" in str(problema).upper()
            for problema in problemas
        ):
            status_oportunidade = "CREDITO_NAO_APROVEITADO"

        else:
            status_oportunidade = "OUTRA_INCONSISTENCIA"

        oportunidade = {
            "periodo": meta.get("periodo"),
            "status_oportunidade": status_oportunidade,
            "codigo_diagnostico": codigo_diagnostico,
            "tipo": diag.get("tipo"),

            "categoria": categoria,
            "cenario": codigo_cenario,
            "nat_bc_cred": enquadramento.get("nat_bc_cred"),
            "cod_cred": enquadramento.get("cod_cred"),

            "descricao": descricao,
            "cod_item": meta.get("cod_item"),
            "ncm": meta.get("ncm"),
            "cfop": meta.get("cfop"),
            "cod_cta": meta.get("cod_cta"),

            "cst_pis_atual": cst_pis_atual,
            "cst_cofins_atual": cst_cofins_atual,
            "cst_pis_destino": (
                meta_diag.get("cst_pis_destino")
                or enquadramento.get("cst_pis_destino")
            ),
            "cst_cofins_destino": (
                meta_diag.get("cst_cofins_destino")
                or enquadramento.get("cst_cofins_destino")
            ),

            "base_recuperavel": base_recuperavel,
            "pis_recuperavel": pis_recuperavel,
            "cofins_recuperavel": cofins_recuperavel,
            "credito_recuperavel": (
                pis_recuperavel + cofins_recuperavel
            ),

            "problemas": problemas,
            "motivo": ", ".join(
                str(problema)
                for problema in problemas
            ),

            "status_cruzamento": status_cruzamento,
            "tipo_match": linha.get("tipo_match"),
            "chv_nfe": linha.get("chv_nfe"),
            "num_doc": linha.get("num_doc"),
            "num_item": linha.get("num_item"),
        }

        oportunidades_c170.append(oportunidade)

        stats["incluidos"] += 1
        contagem_oportunidades_por_tipo[
            status_oportunidade
        ] += 1
        contagem_oportunidades_por_categoria[
            categoria
        ] += 1

    resumo = {
        "dominio": dominio,
        "linhas_cruzadas": len(linhas_cruzadas),
        "cache_classificacao": len(cache_classificacao),
        "cache_categoria": len(cache_categoria),
        "cache_enquadramento": len(
            cache_enquadramento_por_codigo
        ),
        "oportunidades": len(oportunidades_c170),
        **stats,
    }

    logger.info(
        "[REL_C170_RESUMO] %s",
        resumo,
    )

    logger.info(
        "[REL_C170_DISTRIBUICAO] "
        "periodos=%s status_cruzamento=%s "
        "categorias=%s cenarios=%s "
        "oportunidades_tipo=%s "
        "oportunidades_categoria=%s",
        dict(sorted(contagem_periodos.items())),
        dict(contagem_status_cruzamento),
        dict(
            sorted(
                contagem_categorias.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ),
        dict(
            sorted(
                contagem_cenarios.items(),
                key=lambda item: item[1],
                reverse=True,
            )
        ),
        dict(contagem_oportunidades_por_tipo),
        dict(contagem_oportunidades_por_categoria),
    )

    if contagem_sem_cenario_por_categoria_cfop:
        logger.info(
            "[REL_C170_SEM_CENARIO_RESUMO] top=%s",
            sorted(
                contagem_sem_cenario_por_categoria_cfop.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:20],
        )

    # Apenas situações excepcionais geram warning.
    for grupo in (
        "sem_classificacao",
        "nao_classificado",
        "sem_cenario",
        "cenario_inativo",
        "sem_codigo_cenario",
        "sem_enquadramento",
        "sem_diagnostico",
        "base_zerada",
    ):
        quantidade = stats.get(grupo, 0)

        if quantidade <= 0:
            continue

        logger.warning(
            "[REL_C170_AMOSTRAS] tipo=%s quantidade=%s amostras=%s",
            grupo,
            quantidade,
            amostras.get(grupo) or [],
        )

    return oportunidades_c170