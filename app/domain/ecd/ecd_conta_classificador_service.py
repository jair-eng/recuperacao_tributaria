from app.utils.strings import norm_str


def classificar_conta_ecd(
    *,
    nome_cta: str,
    cod_nat: str = "",
    ind_cta: str = "",
    nivel: str = "",
) -> dict:
    n = norm_str(nome_cta or "").upper()
    cod_nat = str(cod_nat or "").strip()
    ind_cta = str(ind_cta or "").strip().upper()
    nivel = str(nivel or "").strip()

    resultado = {
        "categoria_sugerida": "NaoClassificado",
        "grupo_conta_sugerido": "NAO_CLASSIFICADO",
        "elegivel_credito_sugerido": False,
        "naturezas_esperadas_sugeridas": [],
        "fundamento_sugerido": None,
    }

    # REDUTORAS / RECEITAS
    if cod_nat == "04" and ("DEDUÇÕES DA RECEITA" in n or "IMPOSTOS SOBRE VENDAS" in n):
        resultado.update(
            categoria_sugerida="RedutoraReceita",
            grupo_conta_sugerido="REDUTORA_RECEITA",
        )
        return resultado

    if cod_nat == "04" and (
        "RECEITA" in n
        or n.startswith("VENDA ")
        or "VENDA DE" in n
    ):
        resultado.update(
            categoria_sugerida="ReceitaVendaMercadorias",
            grupo_conta_sugerido="RECEITA",
        )
        return resultado

    # ESTOQUE / ATIVO
    if cod_nat == "01" and ("MERCADORIAS PARA REVENDA" in n or "REVENDA" in n):
        resultado.update(
            categoria_sugerida="EstoqueRevenda",
            grupo_conta_sugerido="ESTOQUE_REVENDA",
        )
        return resultado

    if cod_nat == "01" and ("MATÉRIA-PRIMA" in n or "MATERIA-PRIMA" in n):
        resultado.update(
            categoria_sugerida="MateriaPrima",
            grupo_conta_sugerido="MATERIA_PRIMA",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["02"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "01" and ("MERCADOR" in n or "INSUMO" in n or "PRODUTO" in n):
        resultado.update(
            categoria_sugerida="MercadoriasInsumoConsumo",
            grupo_conta_sugerido="INSUMO_OPERACIONAL",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["02"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    # RESULTADO / DESPESA / CUSTO
    if cod_nat == "04" and ("CUSTOS DAS MERCADORIAS VENDIDAS" in n or "CMV" in n):
        resultado.update(
            categoria_sugerida="CustoMercadoriaVendida",
            grupo_conta_sugerido="CMV",
        )
        return resultado

    if cod_nat == "04" and ("CUSTOS DOS PRODUTOS E SERVIÇOS VENDIDOS" in n):
        resultado.update(
            categoria_sugerida="CustoProdutoServicoVendido",
            grupo_conta_sugerido="CUSTO_PRODUTO_SERVICO_VENDIDO",
        )
        return resultado

    if cod_nat == "04" and "ENERGIA" in n:
        resultado.update(
            categoria_sugerida="EnergiaEletricaOperacional",
            grupo_conta_sugerido="ENERGIA_OPERACIONAL",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["04"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "04" and ("COMBUST" in n or "LUBRIFIC" in n):
        resultado.update(
            categoria_sugerida="CombustiveisLubrificantes",
            grupo_conta_sugerido="COMBUSTIVEL_LUBRIFICANTE",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["02"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "04" and "MATERIAL DE USO E CONSUMO" in n:
        resultado.update(
            categoria_sugerida="MaterialUsoConsumo",
            grupo_conta_sugerido="MATERIAL_USO_CONSUMO",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["02"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "04" and "SERVIÇOS PRESTADOS POR TERCEIROS" in n:
        resultado.update(
            categoria_sugerida="ServicosTerceirosOperacionais",
            grupo_conta_sugerido="SERVICOS_TERCEIROS",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["03"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "04" and ("DEPREC" in n or "AMORT" in n):
        resultado.update(
            categoria_sugerida="DepreciacaoFrota",
            grupo_conta_sugerido="DEPRECIACAO_FROTA",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["09", "10"],
            fundamento_sugerido="BemDeCapital",
        )
        return resultado

    if cod_nat == "04" and ("MANUT" in n or "PECA" in n or "PNEU" in n):
        resultado.update(
            categoria_sugerida="PecasManutencaoFrota",
            grupo_conta_sugerido="MANUTENCAO_OPERACIONAL",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["02", "03"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "04" and "SEGURO" in n:
        resultado.update(
            categoria_sugerida="SegurosOperacionais",
            grupo_conta_sugerido="SEGURO_OPERACIONAL",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["03", "13"],
            fundamento_sugerido="RelevanciaImposicaoLegal",
        )
        return resultado

    if cod_nat == "04" and ("FRETE" in n or "CARRETO" in n):
        resultado.update(
            categoria_sugerida="SubcontratacaoFrete",
            grupo_conta_sugerido="FRETE_SUBCONTRATACAO",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["14", "03"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "04" and ("RASTREAMENTO" in n or "TELEMETRIA" in n or "MONITORAMENTO" in n):
        resultado.update(
            categoria_sugerida="RastreamentoTelemetria",
            grupo_conta_sugerido="RASTREAMENTO_TELEMETRIA",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["03"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "04" and ("VALE TRANSPORTE" in n or "VALE-TRANSPORTE" in n or "FRETAMENTO" in n):
        resultado.update(
            categoria_sugerida="ValeTransporteFretamento",
            grupo_conta_sugerido="VALE_TRANSPORTE_FRETAMENTO",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["17"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    if cod_nat == "04" and ("CURSO" in n or "TREINAMENTO" in n or "MOPP" in n or "NR-20" in n):
        resultado.update(
            categoria_sugerida="TreinamentoMOPP",
            grupo_conta_sugerido="TREINAMENTO_OPERACIONAL",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["13"],
            fundamento_sugerido="RelevanciaImposicaoLegal",
        )
        return resultado

    if cod_nat == "04" and ("PEDAG" in n or "ESTACION" in n):
        resultado.update(
            categoria_sugerida="Pedagios",
            grupo_conta_sugerido="PEDAGIO_ESTACIONAMENTO",
            elegivel_credito_sugerido=True,
            naturezas_esperadas_sugeridas=["03", "13"],
            fundamento_sugerido="Essencialidade",
        )
        return resultado

    return resultado