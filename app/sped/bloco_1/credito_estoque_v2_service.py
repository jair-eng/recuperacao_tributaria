from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.credito_estoque_v2 import CreditoEstoqueV2
from app.sped.bloco_1.builder import extrair_creditos_mes_bloco_m_por_cod_cred
from app.sped.blocoM.m_utils import extrair_cods_cred_bloco_m
from app.sped.bloco_1.utils_1500 import yyyymm_to_mmyyyy
from app.utils.numbers import dec_any, q2


def proximo_periodo_yyyymm(periodo: str) -> str:
    periodo = str(periodo or "").strip()
    ano = int(periodo[:4])
    mes = int(periodo[4:6])

    if mes == 12:
        return f"{ano + 1}01"

    return f"{ano}{mes + 1:02d}"


def atualizar_credito_estoque_v2(
    *,
    db: Session,
    empresa_id: int,
    versao_exportada_id: int,
    periodo_origem: str,  # YYYYMM
    base_delta_por_cod_cred_nat_cst: dict[str, dict[str, dict[str, Decimal]]],
) -> None:
    """
    Grava na credito_estoque_v2 somente o DELTA recuperado pela V2.

    Estrutura esperada:
      {
        "101": {
            "02": {
                "50": Decimal("base")
            }
        },
        "201": {
            ...
        }
      }

    Uma linha por:
      empresa_id + periodo_origem + cod_cred

    PIS e COFINS ficam na mesma linha.
    """

    periodo_origem = str(periodo_origem or "").strip()
    if not periodo_origem or len(periodo_origem) != 6:
        raise ValueError(f"periodo_origem inválido: {periodo_origem!r}")

    periodo_escrituracao = proximo_periodo_yyyymm(periodo_origem)

    for cod_cred, base_por_nat_cst in sorted(
        (base_delta_por_cod_cred_nat_cst or {}).items()
    ):
        cod_cred = str(cod_cred or "").strip()
        if not cod_cred:
            continue

        base_total_delta = Decimal("0.00")

        for mapa_cst in (base_por_nat_cst or {}).values():
            for base in (mapa_cst or {}).values():
                base_total_delta += dec_any(base)

        base_total_delta = q2(base_total_delta)

        if base_total_delta <= 0:
            continue

        valor_pis = q2(base_total_delta * Decimal("0.0165"))
        valor_cofins = q2(base_total_delta * Decimal("0.0760"))

        if valor_pis <= 0 and valor_cofins <= 0:
            continue

        row = (
            db.query(CreditoEstoqueV2)
            .filter(CreditoEstoqueV2.empresa_id == int(empresa_id))
            .filter(CreditoEstoqueV2.periodo_origem == periodo_origem)
            .filter(CreditoEstoqueV2.cod_cred == cod_cred)
            .one_or_none()
        )

        if row is None:
            row = CreditoEstoqueV2(
                empresa_id=int(empresa_id),
                periodo_origem=periodo_origem,
                cod_cred=cod_cred,
            )

        row.versao_exportada_id = int(versao_exportada_id)
        row.periodo_escrituracao = periodo_escrituracao
        row.ultimo_periodo_processado = None
        row.orig_cred = "01"

        row.valor_original_pis = valor_pis
        row.valor_original_cofins = valor_cofins

        row.valor_utilizado_pis = Decimal("0.00")
        row.valor_utilizado_cofins = Decimal("0.00")

        row.saldo_pis = valor_pis
        row.saldo_cofins = valor_cofins

        row.status = "ABERTO"

        db.add(row)

    db.flush()

def buscar_creditos_estoque_v2(
    *,
    db: Session,
    empresa_id: int,
    periodo_atual: str,  # YYYYMM
) -> list[Any]:
    """
    Busca estoques V2 abertos que já devem aparecer no Bloco 1 do período atual.
    """

    periodo_atual = str(periodo_atual or "").strip()

    return (
        db.query(CreditoEstoqueV2)
        .filter(CreditoEstoqueV2.empresa_id == int(empresa_id))
        .filter(CreditoEstoqueV2.periodo_escrituracao <= periodo_atual)
        .filter(CreditoEstoqueV2.periodo_origem < periodo_atual)
        .filter(CreditoEstoqueV2.status == "ABERTO")
        .filter(
            or_(
                CreditoEstoqueV2.saldo_pis > 0,
                CreditoEstoqueV2.saldo_cofins > 0,
            )
        )
        .order_by(
            CreditoEstoqueV2.periodo_origem.asc(),
            CreditoEstoqueV2.cod_cred.asc(),
        )
        .all()
    )