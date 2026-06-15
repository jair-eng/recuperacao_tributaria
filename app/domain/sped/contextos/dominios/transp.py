from __future__ import annotations


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