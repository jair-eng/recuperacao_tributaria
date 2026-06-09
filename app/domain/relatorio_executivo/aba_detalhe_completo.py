from __future__ import annotations

from decimal import Decimal
from openpyxl import Workbook
from app.config.settings import ALIQUOTA_PIS, ALIQUOTA_COFINS
from app.utils.ecd_observacao_utils import montar_observacao_detalhe
from app.utils.excel import criar_aba_generica
from app.utils.numbers import to_decimal


def _fator_base_por_fundamento(fundamento: str | None) -> Decimal:
    fundamento = (fundamento or "").strip()

    if fundamento == "CreditoPresumido75":
        return Decimal("0.75")
    return Decimal("1.00")


def criar_aba_detalhe_completo(
    wb: Workbook,
    ctx: dict,
) -> None:
    rows = []

    aliq_pis = Decimal(str(ALIQUOTA_PIS))
    aliq_cofins = Decimal(str(ALIQUOTA_COFINS))

    por_natureza = ctx.get("por_natureza") or {}

    for item in ctx.get("linhas_ecd", []):
        nat = str(item.get("nat_bc_cred") or "").zfill(2)
        dados_nat = por_natureza.get(nat) or {}

        status = dados_nat.get("status")
        valor_conta = to_decimal(item.get("valor"))

        gera_credito = item.get("entra_base_credito") is True


        fator_base = _fator_base_por_fundamento(item.get("fundamento"))

        if gera_credito:
            fator_base = _fator_base_por_fundamento(item.get("fundamento"))

            base_atribuida = (valor_conta * fator_base).quantize(Decimal("0.01"))

            if status in {"SEM_EFD", "PARCIAL"}:
                gap = base_atribuida
            else:
                gap = Decimal("0.00")

            credito_pis = (gap * aliq_pis).quantize(Decimal("0.01"))
            credito_cofins = (gap * aliq_cofins).quantize(Decimal("0.01"))
        else:
            base_atribuida = Decimal("0.00")
            gap = Decimal("0.00")
            credito_pis = Decimal("0.00")
            credito_cofins = Decimal("0.00")

        rows.append(
            {
                "Ano-Mês": item.get("periodo"),
                "Código Conta": item.get("cod_cta"),
                "Descrição": item.get("nome_cta"),
                "NAT_BC_CRED": nat,
                "Categoria": item.get("categoria"),
                "Grupo": item.get("grupo"),
                "Fundamento": item.get("fundamento"),
                "Naturezas Esperadas": item.get("naturezas_esperadas"),
                "Despesa Contábil": valor_conta,
                "Base Atribuída": base_atribuida if gera_credito else "",
                "Gap Atribuído": gap if gera_credito else "",
                "Crédito PIS": credito_pis if gera_credito else "",
                "Crédito COFINS": credito_cofins if gera_credito else "",
                "Fonte": item.get("origem_classificacao"),
                "Origem Valor": item.get("origem_valor"),
                "Confiança": item.get("confianca"),
                "Status": status,
                "Observação": montar_observacao_detalhe(item=item, status=status),
            }
        )

    criar_aba_generica(
        wb,
        nome_aba="Detalhe Completo",
        headers=[
            "Ano-Mês",
            "Código Conta",
            "Descrição",
            "NAT_BC_CRED",
            "Categoria",
            "Grupo",
            "Fundamento",
            "Naturezas Esperadas",
            "Despesa Contábil",
            "Base Atribuída",
            "Gap Atribuído",
            "Crédito PIS",
            "Crédito COFINS",
            "Fonte",
            "Origem Valor",
            "Confiança",
            "Status",
            "Observação",
        ],
        rows=rows,
        money_cols=[
            "Despesa Contábil",
            "Base Atribuída",
            "Gap Atribuído",
            "Crédito PIS",
            "Crédito COFINS",
        ],
    )