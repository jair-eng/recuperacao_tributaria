from __future__ import annotations

from pathlib import Path
from decimal import Decimal
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.domain.fiscal.catalogo.loader_catalogo_fiscal import carregar_catalogo_fiscal
from app.domain.relatorio_executivo.contrib_loader_local import carregar_contrib_local, montar_efd_por_natureza_local
from app.domain.relatorio_executivo.ecd_loader_local import carregar_ecd_local
from app.utils.numbers import to_decimal
from app.utils.sped import listar_txt, periodo_por_i355
from app.utils.strings import normalizar_texto


def montar_contexto_gap_ecd_efd_local(
    db: Session,
    *,
    empresa_id: int | None = None,
    dominio: str = "GERAL",
    pasta_ecd: Path,
    pasta_contrib: Path,
    periodo: str | None = None,
) -> dict:
    arquivos_ecd = listar_txt(Path(pasta_ecd))
    arquivos_contrib = listar_txt(Path(pasta_contrib))

    ecd_ctx = carregar_ecd_local(arquivos_ecd)


    contrib_ctx = carregar_contrib_local(arquivos_contrib)
    efd_por_natureza = montar_efd_por_natureza_local(contrib_ctx)

    linhas_ecd = montar_linhas_ecd_local(
        db=db,
        empresa_id=empresa_id,
        ecd_ctx=ecd_ctx,
        periodo=periodo,
    )

    # Por enquanto vazio até plugarmos o loader da EFD Contrib
    por_natureza = montar_por_natureza_vazio(linhas_ecd)

    for nat, dados_efd in efd_por_natureza.items():
        nat = str(nat or "00").zfill(2)

        if nat not in por_natureza:
            por_natureza[nat] = {
                "periodo": dados_efd.get("periodo") or periodo,
                "nat_bc_cred": nat,
                "valor_ecd": Decimal("0.00"),
                "ecd_elegivel": Decimal("0.00"),
                "valor_efd": Decimal("0.00"),
                "efd_declarada": Decimal("0.00"),
                "gap": Decimal("0.00"),
                "cobertura_pct": Decimal("0.00"),
                "contas_ecd": [],
                "origens": [],
                "categorias": [],
                "grupos": [],
                "fundamentos": [],
                "naturezas_esperadas": [],
                "categoria": "",
                "grupo": "",
                "fundamento": "",
                "tem_gap": False,
                "valor_gap": Decimal("0.00"),
                "status": "SEM_ECD",
            }

        d = por_natureza[nat]
        if dados_efd.get("periodo"):
            d["periodo"] = dados_efd.get("periodo")

        d["valor_efd"] = to_decimal(dados_efd.get("efd_declarada"))
        d["efd_declarada"] = to_decimal(dados_efd.get("efd_declarada"))

        ecd = to_decimal(d.get("valor_ecd"))
        efd = to_decimal(d.get("efd_declarada"))

        if ecd > 0 and efd <= 0:
            d["status"] = "SEM_EFD"
        elif ecd <= 0 and efd > 0:
            d["status"] = "SEM_ECD"
        elif efd < ecd:
            d["status"] = "PARCIAL"
        elif efd > ecd:
            d["status"] = "EXCEDENTE_EFD"
        else:
            d["status"] = "COBERTO"

        d["gap"] = max(Decimal("0.00"), ecd - efd)
        d["valor_gap"] = d["gap"]
        d["tem_gap"] = d["gap"] > 0

    total_ecd = sum(
        to_decimal(i.get("valor"))
        for i in linhas_ecd
    )

    total_efd = sum(
        to_decimal(i.get("efd_declarada"))
        for i in por_natureza.values()
    )
    print("[DOMINIO]", dominio)
    catalogo_fiscal = carregar_catalogo_fiscal(db)
    return {
        "periodo": periodo,
        "catalogo_fiscal": catalogo_fiscal,
        "dominio": dominio,
        "origem": "LOCAL",
        "resumo": {
            "periodo": periodo,
            "total_ecd_elegivel": total_ecd,
            "total_efd_declarada": total_efd,
        },
        "por_natureza": por_natureza,
        "linhas_ecd": linhas_ecd,
        "comparativo": {},
        "ecd_por_mes_nat": {},
        "efd_por_mes_nat": {},
    }


def montar_por_natureza_vazio(linhas_ecd: list[dict]) -> dict:
    por_nat = defaultdict(lambda: {
        "periodo": None,
        "nat_bc_cred": None,
        "valor_ecd": Decimal("0.00"),
        "ecd_elegivel": Decimal("0.00"),
        "valor_efd": Decimal("0.00"),
        "efd_declarada": Decimal("0.00"),
        "gap": Decimal("0.00"),
        "cobertura_pct": Decimal("0.00"),
        "contas_ecd": [],
        "origens": [],
        "categorias": set(),
        "grupos": set(),
        "fundamentos": set(),
        "naturezas_esperadas": set(),
        "status": "SEM_EFD",
    })


    for item in linhas_ecd:
        nat = str(item.get("nat_bc_cred") or "00").zfill(2)
        periodo = item.get("periodo")
        valor = to_decimal(item.get("valor"))

        d = por_nat[nat]
        d["periodo"] = periodo
        d["nat_bc_cred"] = nat
        d["valor_ecd"] += valor

        if item.get("entra_base_credito", True):
            d["ecd_elegivel"] += valor
            d["gap"] += valor

        if item.get("cod_cta"):
            d["contas_ecd"].append(item.get("cod_cta"))

        if item.get("origem"):
            d["origens"].append(item.get("origem"))

        if item.get("categoria"):
            d["categorias"].add(item.get("categoria"))

        if item.get("grupo"):
            d["grupos"].add(item.get("grupo"))

        if item.get("fundamento"):
            d["fundamentos"].add(item.get("fundamento"))

        for n in item.get("naturezas_esperadas") or []:
            d["naturezas_esperadas"].add(str(n).zfill(2))

    resultado = {}

    for nat, d in por_nat.items():
        categorias = sorted(d["categorias"])
        grupos = sorted(d["grupos"])
        fundamentos = sorted(d["fundamentos"])
        naturezas = sorted(d["naturezas_esperadas"])

        resultado[nat] = {
            **d,
            "categorias": categorias,
            "grupos": grupos,
            "fundamentos": fundamentos,
            "naturezas_esperadas": naturezas,
            "categoria": ", ".join(categorias),
            "grupo": ", ".join(grupos),
            "fundamento": ", ".join(fundamentos),
            "tem_gap": d["gap"] > 0,
            "valor_gap": d["gap"],
        }

    return resultado

def montar_linhas_ecd_local(
    db: Session,
    *,
    empresa_id: int | None = None,
    ecd_ctx: dict,
    periodo: str | None = None,
) -> list[dict]:
    i050 = ecd_ctx.get("i050") or ecd_ctx.get("I050") or []
    i355 = ecd_ctx.get("i355") or ecd_ctx.get("I355") or []

    contas_por_codigo = {}

    for conta in i050:
        cod_cta = str(conta.get("cod_cta") or "").strip()
        if cod_cta:
            contas_por_codigo[cod_cta] = conta

    linhas = []

    for mov in i355:
        cod_cta = str(mov.get("cod_cta") or "").strip()
        if not cod_cta:
            continue

        conta = contas_por_codigo.get(cod_cta) or {}

        valor = to_decimal(mov.get("vl_cta") or mov.get("valor"))
        if not valor:
            continue

        periodo_linha = periodo_por_i355(mov, periodo)

        nome_cta = conta.get("cta") or conta.get("nome_cta")

        classificacao = classificar_conta_ecd_por_catalogo_local(
            db,
            nome_cta=nome_cta,
        )

        categoria = classificacao.get("categoria")
        grupo = classificacao.get("grupo")
        fundamento = classificacao.get("fundamento")
        nat_bc_cred = classificacao.get("nat_bc_cred")
        naturezas_esperadas = classificacao.get("naturezas_esperadas") or []
        confianca = classificacao.get("confianca")
        observacao = classificacao.get("observacao")
        origem_classificacao = classificacao.get("origem_classificacao")
        nivel_evidencia = classificacao.get("nivel_evidencia")
        entra_base_credito = classificacao.get("entra_base_credito")



        linhas.append({
            "periodo": periodo_linha,
            "arquivo": mov.get("arquivo") or conta.get("arquivo"),
            "cod_cta": cod_cta,
            "nome_cta": nome_cta,
            "cod_nat": conta.get("cod_nat"),
            "ind_cta": conta.get("ind_cta"),
            "nivel": conta.get("nivel"),

            "valor": valor,

            "categoria": categoria,
            "grupo": grupo,
            "fundamento": fundamento,
            "nat_bc_cred": nat_bc_cred,
            "naturezas_esperadas": naturezas_esperadas,
            "confianca": confianca,
            "observacao": observacao,

            "origem": "I355",
            "origem_valor": "I355",
            "origem_classificacao": origem_classificacao,
            "nivel_evidencia": nivel_evidencia,
            "entra_base_credito": entra_base_credito,
        })

    return linhas

def classificar_conta_ecd_por_catalogo_local(
    db: Session,
    *,
    nome_cta: str | None,
) -> dict:
    nome = normalizar_texto(nome_cta)

    if not nome:
        return {
            "categoria": "NaoClassificado",
            "grupo": None,
            "fundamento": "Investigar",
            "nat_bc_cred": "00",
            "naturezas_esperadas": [],
            "confianca": 50,
            "observacao": "Conta sem descrição para classificação.",
            "origem_classificacao": "NaoClassificado",
        }

    sql = """
    SELECT
        categoria,
        grupo_conta,
        natureza_codigo,
        fundamento,
        confianca,
        observacao_padrao,
        palavras_chave,
        nivel_evidencia,
        entra_base_credito
    FROM ecd_categoria_natureza_esperada
    WHERE ativo = 1
    ORDER BY prioridade DESC
    """

    regras = db.execute(text(sql)).mappings().all()

    for regra in regras:
        palavras_raw = regra.palavras_chave or ""
        palavras = [
            normalizar_texto(p)
            for p in palavras_raw.replace(";", ",").split(",")
            if p.strip()
        ]

        if not palavras:
            continue

        if any(p in nome for p in palavras):
            nat = str(regra["natureza_codigo"] or "00").zfill(2)

            categoria = regra["categoria"]
            grupo = regra["grupo_conta"]

            naturezas_esperadas = sorted({
                str(r["natureza_codigo"] or "00").zfill(2)
                for r in regras
                if r["categoria"] == categoria
                   and r["grupo_conta"] == grupo
                   and r["natureza_codigo"]
            })

            return {
                "categoria": categoria,
                "grupo": grupo,
                "fundamento": regra["fundamento"],
                "nat_bc_cred": nat,
                "naturezas_esperadas": naturezas_esperadas,
                "confianca": regra["confianca"] or 70,
                "observacao": regra["observacao_padrao"],
                "origem_classificacao": "CatalogoLocal",
                "nivel_evidencia": regra["nivel_evidencia"] or "CATALOGO",
                "entra_base_credito": bool(regra["entra_base_credito"]),
            }


    return {
        "categoria": "NaoClassificado",
        "grupo": None,
        "fundamento": "Investigar",
        "nat_bc_cred": "00",
        "naturezas_esperadas": [],
        "confianca": 50,
        "observacao": "Conta ainda não classificada no catálogo local.",
        "origem_classificacao": "NaoClassificado",
    }