from app.Legacy.fiscal.settings_fiscais import SLUGS_C170_POR_DOMINIO
from app.domain.ecd.ecd_conta_classificador_service import classificar_texto_por_natureza_esperada
from collections import defaultdict
from typing import Any
from app.domain.fiscal.bloco_F.f100_contexto import classificar_registro_f100_por_natureza
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.utils.ecd_calculos_utils import nat_list
from app.utils.numbers import to_decimal, somar_credito_base
from decimal import Decimal
from sqlalchemy import text

from app.utils.strings import norm_str


def enriquecer_documento_com_categoria(
    *,
    db,
    item: dict,
    texto: str,
    nat: str | None,
) -> dict:
    classificacao = classificar_texto_por_natureza_esperada(
        db=db,
        texto=texto,
        nat_bc_cred=nat,
    )

    novo = dict(item)
    novo.update({
        "categoria": classificacao.get("categoria"),
        "grupo": classificacao.get("grupo"),
        "fundamento": classificacao.get("fundamento"),
        "naturezas_esperadas": classificacao.get("naturezas_esperadas"),
        "confianca_classificacao": classificacao.get("confianca"),
        "origem_classificacao": classificacao.get("origem_classificacao"),
    })

    return novo


def chave_nat_categoria(nat: str | None, categoria: str | None) -> tuple[str, str]:
    return (
        str(nat or "00").zfill(2),
        categoria or "NaoClassificado",
    )

def escolher_natureza_recuperacao(
    *,
    categoria: str,
    naturezas_esperadas: list[str],
    chaves_com_documento: set[tuple[str, str]],
) -> str | None:
    nats = [
        str(nat or "").zfill(2)
        for nat in naturezas_esperadas
        if nat not in (None, "")
    ]

    if not nats:
        return None

    for nat in nats:
        chave = chave_nat_categoria(nat, categoria)
        if chave in chaves_com_documento:
            return nat

    return nats[0]

def montar_ecd_por_chave(
    linhas_ecd: list[dict[str, Any]],
    *,
    por_periodo: bool = False,
) -> dict[tuple, dict[str, Any]]:
    resultado = defaultdict(lambda: {
        "valor_ecd": Decimal("0.00"),
        "qtd_contas": 0,
    })

    for linha in linhas_ecd:
        if linha.get("entra_base_credito") is not True:
            continue

        categoria = linha.get("categoria") or "NaoClassificado"
        if categoria == "NaoClassificado":
            continue

        valor = to_decimal(linha.get("valor"))
        if valor <= 0:
            continue

        nat = escolher_nat_ecd(linha)
        if not nat:
            continue

        periodo = linha.get("periodo")

        chave_base = chave_nat_categoria(nat, categoria)

        if por_periodo:
            chave = (
                periodo,
                chave_base[0],
                chave_base[1],
            )
        else:
            chave = chave_base

        resultado[chave]["valor_ecd"] += valor
        resultado[chave]["qtd_contas"] += 1


    return dict(resultado)

def montar_c170_por_chave(
    *,
    db,
    c170_contrib: list[dict[str, Any]],
    dominio: str = "GERAL",
    por_periodo: bool = False,
) -> dict[tuple, dict[str, Any]]:
    catalogo = carregar_catalogo_fiscal(db)

    resultado = defaultdict(lambda: {
        "valor_creditado_c170": Decimal("0.00"),
        "valor_oportunidade_c170": Decimal("0.00"),
        "qtd_c170": 0,
        "qtd_c170_creditado": 0,
        "qtd_c170_sem_credito": 0,
        "qtd_c170_oportunidade": 0,
        "exemplo_descricao": "",
        "exemplo_participante": "",
        "exemplo_cod_cta": "",
        "exemplo_cod_item": "",
        "exemplo_ncm": "",
        "exemplo_cfop": "",
    })

    for item in c170_contrib:
        if item.get("ind_oper") != "0":
            continue

        cls = classificar_c170_por_catalogo(
            item=item,
            catalogo=catalogo,
            dominio=dominio,
        )

        categoria = cls["categoria"]

        nat = buscar_nat_principal_categoria(
            db=db,
            categoria=categoria,
        )

        periodo = item.get("periodo")

        chave_base = chave_nat_categoria(nat, categoria)

        if por_periodo:
            chave = (
                periodo,
                chave_base[0],
                chave_base[1],
            )
        else:
            chave = chave_base

        if not resultado[chave].get("exemplo_descricao"):
            resultado[chave]["exemplo_descricao"] = (
                    item.get("descr_item")
                    or item.get("desc_doc_oper")
                    or ""
            )

        if not resultado[chave].get("exemplo_participante"):
            resultado[chave]["exemplo_participante"] = (
                item.get("participante_nome")
            )

        base_item = somar_credito_base([item])
        tem_credito = bool(item.get("tem_credito"))

        agg = resultado[chave]

        if not agg.get("exemplo_descricao"):
            agg["exemplo_descricao"] = (
                    item.get("descr_item_0200")
                    or item.get("descr_compl")
                    or item.get("cod_item")
                    or ""
            )

        if not agg.get("exemplo_participante"):
            agg["exemplo_participante"] = item.get("participante_nome") or ""

        if not agg.get("exemplo_cod_cta"):
            agg["exemplo_cod_cta"] = item.get("cod_cta") or ""

        if not agg.get("exemplo_cod_item"):
            agg["exemplo_cod_item"] = item.get("cod_item") or ""

        if not agg.get("exemplo_ncm"):
            agg["exemplo_ncm"] = item.get("ncm") or ""

        if not agg.get("exemplo_cfop"):
            agg["exemplo_cfop"] = item.get("cfop") or ""

        agg["qtd_c170"] += 1

        if tem_credito:
            agg["valor_creditado_c170"] += base_item
            agg["qtd_c170_creditado"] += 1
        else:
            agg["qtd_c170_sem_credito"] += 1

            if cls["elegivel_dominio"]:
                agg["valor_oportunidade_c170"] += base_item
                agg["qtd_c170_oportunidade"] += 1

    return dict(resultado)

def montar_f100_por_chave(
    *,
    db,
    f100_contrib: list[dict[str, Any]],
    por_periodo: bool = False,
) -> dict[tuple, dict[str, Any]]:

    resultado = defaultdict(lambda: {
        "valor_creditado_f100": Decimal("0.00"),
        "qtd_f100": 0,
        "exemplo_descricao": "",
        "exemplo_participante": "",
        "exemplo_participante_tipo": "",
        "exemplo_cod_cta": "",
    })

    for item in f100_contrib:
        nat = str(item.get("nat_bc_cred") or "00").zfill(2)

        # Preferir classificação já enriquecida no montar_contexto_f100
        categoria = item.get("categoria")

        if not categoria:
            classificacao = item.get("classificacao_natureza") or {}

            if classificacao:
                categoria = classificacao.get("categoria")

        # Fallback: classificar com contexto completo
        if not categoria and db:
            classificacao = classificar_registro_f100_por_natureza(
                db=db,
                item=item,
            )
            categoria = classificacao.get("categoria")

        categoria = categoria or "NaoClassificado"

        periodo = item.get("periodo")



        chave = chave_nat_categoria(nat, categoria)

        if por_periodo:
            chave = (
                periodo,
                chave[0],
                chave[1],
            )

        agg = resultado[chave]

        if not agg.get("exemplo_descricao"):
            agg["exemplo_descricao"] = item.get("desc_doc_oper") or ""

        if not agg.get("exemplo_participante"):
            agg["exemplo_participante"] = item.get("participante_nome") or ""

        if not agg.get("exemplo_participante_tipo"):
            agg["exemplo_participante_tipo"] = item.get("participante_tipo") or ""

        if not agg.get("exemplo_cod_cta"):
            agg["exemplo_cod_cta"] = item.get("cod_cta") or ""

        agg["valor_creditado_f100"] += somar_credito_base([item])
        agg["qtd_f100"] += 1

    return dict(resultado)

def montar_a170_por_chave(
    *,
    db,
    a170_contrib: list[dict[str, Any]],
    dominio: str = "GERAL",
    por_periodo: bool = False,
) -> dict[tuple, dict[str, Any]]:
    resultado = defaultdict(lambda: {
        "valor_creditado_a170": Decimal("0.00"),
        "valor_sem_credito_a170": Decimal("0.00"),
        "qtd_a170": 0,
        "qtd_a170_creditado": 0,
        "qtd_a170_sem_credito": 0,
        "exemplo_descricao": "",
        "exemplo_cod_cta": "",
    })

    for item in a170_contrib:
        if item.get("ind_oper") != "0":
            continue

        cls = classificar_a170_por_catalogo(
            db=db,
            item=item,
            dominio=dominio,
        )

        categoria = cls.get("categoria") or "NaoClassificado"

        nat = str(cls.get("nat_bc_cred") or "00").zfill(2)

        periodo = item.get("periodo")

        chave = chave_nat_categoria(nat, categoria)

        if por_periodo:
            chave = (
                periodo,
                chave[0],
                chave[1],
            )
        else:
            chave = chave

        base_item = somar_credito_base([item])
        tem_credito = bool(item.get("tem_credito"))

        agg = resultado[chave]
        agg["qtd_a170"] += 1

        if not agg.get("exemplo_descricao"):
            agg["exemplo_descricao"] = (
                    item.get("descr_item")
                    or item.get("descricao")
                    or ""
            )

        if not agg.get("exemplo_cod_cta"):
            agg["exemplo_cod_cta"] = item.get("cod_cta") or ""

        if tem_credito:
            agg["valor_creditado_a170"] += base_item
            agg["qtd_a170_creditado"] += 1
        else:
            agg["valor_sem_credito_a170"] += to_decimal(
                item.get("vl_item")
                or item.get("vl_bc_pis")
                or item.get("vl_bc_cofins")
            )
            agg["qtd_a170_sem_credito"] += 1


    return dict(resultado)



def classificar_c170_por_catalogo(
    *,
    item: dict[str, Any],
    catalogo,
    dominio: str,
) -> dict[str, Any]:
    dominio = norm_str(dominio).upper()
    desc = norm_str(item.get("descr_compl") or item.get("cod_item")).upper()
    ncm = norm_str(item.get("ncm"))

    categorias_dominio = SLUGS_C170_POR_DOMINIO.get(dominio) or {}

    for categoria, slugs in categorias_dominio.items():
        for slug in slugs:
            if bate_em_grupos(
                ncm=ncm,
                texto=desc,
                catalogo=catalogo,
                slugs={slug},
            ):
                return {
                    "categoria": categoria,
                    "elegivel_dominio": True,
                    "origem_classificacao": "CATALOGO_FISCAL",
                    "slug_match": slug,
                }

    return {
        "categoria": "NaoClassificado",
        "elegivel_dominio": False,
        "origem_classificacao": "NAO_CLASSIFICADO",
        "slug_match": None,
    }


def classificar_a170_por_catalogo(
    *,
    db,
    item: dict[str, Any],
    dominio: str = "GERAL",
) -> dict[str, Any]:
    texto = (
        item.get("descr_compl")
        or item.get("cod_item")
        or ""
    )

    classificacao = classificar_texto_por_natureza_esperada(
        db=db,
        texto=texto,
    )

    categoria = classificacao.get("categoria") or "NaoClassificado"
    naturezas = classificacao.get("naturezas_esperadas") or []

    if naturezas:
        nat = str(naturezas[0]).zfill(2)
    else:
        nat = "00"

    return {
        "categoria": categoria,
        "grupo": classificacao.get("grupo"),
        "fundamento": classificacao.get("fundamento"),
        "nat_bc_cred": nat,
        "naturezas_esperadas": naturezas,
        "elegivel_dominio": categoria != "NaoClassificado",
        "origem_classificacao": classificacao.get("origem_classificacao"),
        "confianca": classificacao.get("confianca"),
    }


def buscar_nat_principal_categoria(
    *,
    db,
    categoria: str,
) -> str:
    if categoria == "NaoClassificado":
        return "00"

    row = db.execute(
        text("""
            SELECT natureza_codigo
            FROM ecd_categoria_natureza_esperada
            WHERE ativo = 1
              AND categoria = :categoria
              AND natureza_codigo IS NOT NULL
              AND natureza_codigo <> ''
            ORDER BY prioridade ASC, natureza_codigo ASC
            LIMIT 1
        """),
        {"categoria": categoria},
    ).mappings().first()

    if not row:
        return "00"

    return str(row["natureza_codigo"]).zfill(2)

def bate_em_grupos(
    *,
    texto: str,
    ncm: str | None,
    catalogo,
    slugs: set[str] | list[str],
) -> bool:
    texto = norm_str(texto).upper()
    ncm = norm_str(ncm)

    for slug in slugs:
        itens = catalogo.grupos.get(slug) or set()

        for codigo in itens:
            codigo_norm = norm_str(codigo).upper()

            if not codigo_norm:
                continue

            if ncm and codigo_norm == ncm:
                return True

            if codigo_norm in texto:
                return True

    return False



def escolher_nat_ecd(linha: dict[str, Any]) -> str | None:
    nat_real = linha.get("nat_bc_cred")
    if nat_real:
        return str(nat_real).zfill(2)

    nats = nat_list(linha)
    if not nats:
        return None

    return str(nats[0]).zfill(2)

def agregar_por_categoria(
    por_chave: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    resultado = defaultdict(lambda: {
        "categoria": "",
        "valor_ecd": Decimal("0.00"),

        "valor_creditado_c170": Decimal("0.00"),
        "valor_oportunidade_c170": Decimal("0.00"),

        "valor_creditado_f100": Decimal("0.00"),

        "valor_creditado_a170": Decimal("0.00"),
        "valor_sem_credito_a170": Decimal("0.00"),

        "valor_creditado_total": Decimal("0.00"),
        "valor_documentado_total": Decimal("0.00"),
        "valor_gap_ecd": Decimal("0.00"),

        "qtd_contas": 0,

        "qtd_c170": 0,
        "qtd_c170_creditado": 0,
        "qtd_c170_sem_credito": 0,
        "qtd_c170_oportunidade": 0,

        "qtd_f100": 0,

        "qtd_a170": 0,
        "qtd_a170_creditado": 0,
        "qtd_a170_sem_credito": 0,

        "naturezas": set(),
    })

    for dados in por_chave.values():
        categoria = dados.get("categoria") or "NaoClassificado"
        nat = str(dados.get("nat_bc_cred") or "").zfill(2)

        agg = resultado[categoria]
        agg["categoria"] = categoria

        valor_ecd = to_decimal(dados.get("valor_ecd"))

        valor_creditado_c170 = to_decimal(dados.get("valor_creditado_c170"))
        valor_oportunidade_c170 = to_decimal(dados.get("valor_oportunidade_c170"))

        valor_creditado_f100 = to_decimal(dados.get("valor_creditado_f100"))

        valor_creditado_a170 = to_decimal(dados.get("valor_creditado_a170"))
        valor_sem_credito_a170 = to_decimal(dados.get("valor_sem_credito_a170"))

        valor_creditado_total = (
            valor_creditado_c170
            + valor_creditado_f100
            + valor_creditado_a170
        )

        valor_documentado_total = (
            valor_creditado_total
            + valor_sem_credito_a170
        )

        valor_gap_ecd = max(
            Decimal("0.00"),
            valor_ecd - valor_documentado_total,
        )

        agg["valor_ecd"] += valor_ecd

        agg["valor_creditado_c170"] += valor_creditado_c170
        agg["valor_oportunidade_c170"] += valor_oportunidade_c170

        agg["valor_creditado_f100"] += valor_creditado_f100

        agg["valor_creditado_a170"] += valor_creditado_a170
        agg["valor_sem_credito_a170"] += valor_sem_credito_a170

        agg["valor_creditado_total"] += valor_creditado_total
        agg["valor_documentado_total"] += valor_documentado_total
        agg["valor_gap_ecd"] += valor_gap_ecd

        agg["qtd_contas"] += int(dados.get("qtd_contas") or 0)

        agg["qtd_c170"] += int(dados.get("qtd_c170") or 0)
        agg["qtd_c170_creditado"] += int(dados.get("qtd_c170_creditado") or 0)
        agg["qtd_c170_sem_credito"] += int(dados.get("qtd_c170_sem_credito") or 0)
        agg["qtd_c170_oportunidade"] += int(dados.get("qtd_c170_oportunidade") or 0)

        agg["qtd_f100"] += int(dados.get("qtd_f100") or 0)

        agg["qtd_a170"] += int(dados.get("qtd_a170") or 0)
        agg["qtd_a170_creditado"] += int(dados.get("qtd_a170_creditado") or 0)
        agg["qtd_a170_sem_credito"] += int(dados.get("qtd_a170_sem_credito") or 0)

        if nat and nat != "00":
            agg["naturezas"].add(nat)

    final = {}

    for categoria, dados in resultado.items():
        valor_ecd = to_decimal(dados.get("valor_ecd"))
        valor_documentado_total = to_decimal(dados.get("valor_documentado_total"))
        valor_creditado_total = to_decimal(dados.get("valor_creditado_total"))

        cobertura_documental_pct = (
            (valor_documentado_total / valor_ecd) * Decimal("100")
            if valor_ecd > 0
            else Decimal("0.00")
        )

        cobertura_credito_pct = (
            (valor_creditado_total / valor_ecd) * Decimal("100")
            if valor_ecd > 0
            else Decimal("0.00")
        )

        final[categoria] = {
            **dados,
            "naturezas": sorted(dados["naturezas"]),
            "naturezas_txt": ", ".join(sorted(dados["naturezas"])),
            "cobertura_documental_pct": cobertura_documental_pct,
            "cobertura_credito_pct": cobertura_credito_pct,
        }

    return final

