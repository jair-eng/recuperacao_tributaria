from __future__ import annotations

from decimal import Decimal
from typing import Any
from app.utils.numbers import to_decimal

OPORTUNIDADES_TRANSP = [
    {
        "oportunidade": "Combustíveis",
        "fontes": "ECD + EFD C170",
        "slugs": [
            "TRANSP_DESC_COMBUSTIVEL",
            "NCM_DIESEL",
        ],
        "categorias_ecd": [
        "CombustiveisLubrificantes",
    ],
        "indicadores": "CST sem crédito, base zerada, ausência de NAT 02 ou crédito não aproveitado.",
        "restricoes": "Validar se vinculado à atividade de transporte.",
        "acao": "Cruzar C170 por produto/NCM/CFOP e contas contábeis.",
    },
    {
        "oportunidade": "Lubrificantes",
        "fontes": "ECD + EFD C170",
        "slugs": [
            "TRANSP_DESC_LUBRIFICANTES",
            "NCM_LUBRIFICANTES",
        ],
        "categorias_ecd": [
        "CombustiveisLubrificantes",
    ],
        "indicadores": "Compra sem crédito ou sem base PIS/COFINS.",
        "restricoes": "Validar vínculo com frota/operação.",
        "acao": "Mapear NCM/descrição do item e CFOP de entrada.",
    },
    {
        "oportunidade": "ARLA32",
        "fontes": "ECD + EFD C170",
        "slugs": [
            "NCM_ARLA32",
        ],
        "categorias_ecd": [
        "CombustiveisLubrificantes",
    ],
        "indicadores": "Compra sem crédito ou sem base PIS/COFINS.",
        "restricoes": "Validar vínculo com frota diesel/operação.",
        "acao": "Mapear NCM/descrição do item e CFOP de entrada.",
    },
    {
        "oportunidade": "Pneus",
        "fontes": "ECD + EFD C170",
        "slugs": [
            "TRANSP_DESC_PNEUS",
            "NCM_PNEUS",
        ],
        "categorias_ecd": [
        "PecasManutencaoFrota",
        ],
        "indicadores": "Despesa ECD sem base EFD correspondente.",
        "restricoes": "Separar frota operacional de uso administrativo.",
        "acao": "Validar contas ECD e itens fiscais relacionados.",
    },
    {
        "oportunidade": "Manutenção de frota",
        "fontes": "ECD + EFD C170",
        "slugs": [
            "TRANSP_DESC_MANUTENCAO",
            "NCM_MANUTENCAO_VEICULAR",
            "NCM_AUTOPECAS",
            "NCM_FILTROS",
            "NCM_ADITIVOS_FLUIDOS",
        ],
        "categorias_ecd": [
        "PecasManutencaoFrota",
        ],
        "indicadores": "Despesa ECD sem base EFD correspondente.",
        "restricoes": "Separar manutenção operacional de uso administrativo.",
        "acao": "Validar contas ECD e itens fiscais relacionados.",
    },
    {
        "oportunidade": "Subcontratação de frete PJ & PF",
        "fontes": "ECD + D100/D101/D105 + M105/M505",
        "slugs": [
            "CFOP_SERVICO",
            "CFOP_ENTRADA_INSUMO",
        ],
        "categorias_ecd": [
        "SubcontratacaoFreteLucroRealPresumido",
        "SubcontratacaoFreteFisicaSimples",
        ],
        "indicadores": "NAT 03/07/14, crédito presumido 75%, base parcial ou ausente.",
        "restricoes": "Separar PF/Simples/PJ e natureza efetivamente declarada.",
        "acao": "Validar D100/D101/D105 e bases no Bloco M.",
    },
]


def avaliar_oportunidade_transp(
    op: dict[str, Any],
    ctx: dict[str, Any],
) -> dict[str, Any]:
    catalogo = ctx.get("catalogo_fiscal")
    linhas_ecd = ctx.get("linhas_ecd") or []

    slugs = op.get("slugs") or []
    grupos_fiscais = []

    for slug in slugs:
        codigos = catalogo.codigos(slug) if catalogo else []
        grupos_fiscais.append(f"{slug} ({len(codigos)})")

    categorias_ecd = op.get("categorias_ecd") or []
    contas_encontradas = []
    valor_total = Decimal("0.00")

    for item in linhas_ecd:
        categoria = str(item.get("categoria") or "")

        if categoria in categorias_ecd:
            valor = to_decimal(item.get("valor"))
            valor_total += valor
            contas_encontradas.append(
                {
                    "cod_cta": item.get("cod_cta"),
                    "nome_cta": item.get("nome_cta"),
                    "valor": valor,
                    "categoria": categoria,
                }
            )

    if not contas_encontradas:
        situacao = "Não encontrado"
    elif valor_total > 0:
        situacao = "Encontrado"
    else:
        situacao = "Revisar"

    sinais_extra = []

    if op.get("oportunidade") == "Subcontratação de frete PJ & PF":
        ctx_f100 = ctx.get("f100") or {}

        if ctx_f100:
            cst60_nat14 = ctx_f100.get("cst60_nat14") or {}
            pf = cst60_nat14.get("pf") or {}
            pj = cst60_nat14.get("pj") or {}

            sinais_extra.append(
                "F100 - Contratos de Transporte\n"
                f"Registros F100: {ctx_f100.get('qtd_f100', 0)}\n"
                f"PF: {ctx_f100.get('qtd_pf', 0)} | "
                f"PJ: {ctx_f100.get('qtd_pj', 0)}\n"
                f"Base CST 60 / NAT 14: R$ {cst60_nat14.get('vl_oper', 0):,.2f}\n"
                f"PF Base: R$ {pf.get('vl_oper', 0):,.2f} | "
                f"PJ Base: R$ {pj.get('vl_oper', 0):,.2f}\n"
                f"PIS: R$ {cst60_nat14.get('vl_pis', 0):,.2f}\n"
                f"COFINS: R$ {cst60_nat14.get('vl_cofins', 0):,.2f}"
            )

    return {
        **op,
        "cobertura_catalogo": "\n".join(grupos_fiscais),
        "contas_ecd": contas_encontradas,
        "qtd_contas_ecd": len(contas_encontradas),
        "valor_ecd": valor_total,
        "situacao": situacao,
        "sinais_extra": sinais_extra,
    }


def avaliar_oportunidades_transp(
    ctx: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        avaliar_oportunidade_transp(op, ctx)
        for op in OPORTUNIDADES_TRANSP
    ]