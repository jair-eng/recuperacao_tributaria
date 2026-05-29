from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session
from decimal import Decimal
from sqlalchemy import or_
import calendar
from app.db.models import EfdRegistro, ContextoFiscalVersao, EcdSaldoI155Db, EcdResultadoI355Db
from app.db.models.ecd_conta_empresa import EcdContaEmpresa
from app.db.models.ecd_conta_natureza_esperada import EcdContaNaturezaEsperada
from app.domain.ecd.ecd_credito_analytics import (
    somar_despesa_ecd_elegivel_por_mes_natureza,
    montar_efd_declarada_por_mes_natureza,
    comparar_ecd_elegivel_vs_efd_declarada,
)
from app.utils.sped import reg_linha_sped
from app.utils.dates import normalizar_periodo


def gerar_diagnostico_gap_ecd_efd(
    db: Session,
    *,
    versao_id: int,
    periodo: str,
    linhas_ecd_classificadas: list[dict],
    linhas_sped: list[str],
) -> Dict[str, Any]:
    """
    Diagnóstico analítico:
        ECD elegível x EFD declarada.

    NÃO altera SPED.
    NÃO gera revisão.
    NÃO aplica corretiva.

    Apenas:
    - calcula elegibilidade ECD
    - lê bases declaradas no Bloco M
    - compara cobertura/GAP
    """

    periodo_norm = normalizar_periodo(periodo)

    # ============================================================
    # 1) ECD elegível
    # ============================================================

    ecd_por_mes_nat = somar_despesa_ecd_elegivel_por_mes_natureza(
        linhas_ecd_classificadas
    )

    # ============================================================
    # 2) Extrai apenas linhas do Bloco M
    # ============================================================

    linhas_bloco_m = []

    for linha in linhas_sped or []:
        reg = reg_linha_sped(linha)

        if not reg:
            continue

        if reg.startswith("M"):
            linhas_bloco_m.append(linha)

    # ============================================================
    # 3) EFD declarada
    # ============================================================

    efd_por_mes_nat = montar_efd_declarada_por_mes_natureza(
        linhas_bloco_m,
        periodo=periodo_norm,
    )

    # ============================================================
    # 4) GAP
    # ============================================================

    comparativo = comparar_ecd_elegivel_vs_efd_declarada(
        ecd_por_mes_nat=ecd_por_mes_nat,
        efd_por_mes_nat=efd_por_mes_nat,
    )

    # ============================================================
    # 5) Resumo executivo
    # ============================================================

    resumo = {
        "versao_id": versao_id,
        "periodo": periodo_norm,
        "total_ecd_elegivel": Decimal("0.00"),
        "total_efd_declarada": Decimal("0.00"),

        # saldo líquido: ECD - EFD
        "total_gap": Decimal("0.00"),

        # oportunidade: ECD maior que EFD
        "total_gap_positivo": Decimal("0.00"),

        # declarado maior que ECD
        "total_gap_negativo": Decimal("0.00"),

        "total_naturezas": 0,
        "naturezas_com_gap_positivo": 0,
        "naturezas_com_gap_negativo": 0,
    }

    periodo_cmp = comparativo.get(periodo_norm) or {}

    for nat, dados in periodo_cmp.items():
        valor_ecd = dados.get("valor_ecd_elegivel") or 0
        valor_efd = dados.get("base_efd_declarada") or 0
        gap = dados.get("gap_base") or 0

        resumo["total_ecd_elegivel"] += valor_ecd
        resumo["total_efd_declarada"] += valor_efd
        resumo["total_gap"] += gap
        resumo["total_naturezas"] += 1

        if gap > 0:
            resumo["total_gap_positivo"] += gap
            resumo["naturezas_com_gap_positivo"] += 1

        elif gap < 0:
            resumo["total_gap_negativo"] += abs(gap)
            resumo["naturezas_com_gap_negativo"] += 1

    return {
        "resumo": resumo,
        "comparativo": comparativo,
        "ecd_por_mes_nat": ecd_por_mes_nat,
        "efd_por_mes_nat": efd_por_mes_nat,
    }

def carregar_linhas_sped_por_versao(
    db: Session,
    *,
    versao_id: int,
) -> list[str]:

    registros = (
        db.query(EfdRegistro)
        .filter(EfdRegistro.versao_id == versao_id)
        .order_by(EfdRegistro.id.asc())
        .all()
    )

    linhas: list[str] = []

    for reg in registros:

        reg_nome = getattr(reg, "reg", None)

        conteudo_json = getattr(reg, "conteudo_json", None) or {}

        dados = conteudo_json.get("dados") or []

        if not reg_nome:
            continue

        linha = "|" + "|".join(
            [str(reg_nome)] + [str(x or "") for x in dados]
        ) + "|"

        linhas.append(linha)

    return linhas

def gerar_diagnostico_gap_ecd_efd_por_versao(
    db: Session,
    *,
    versao_id: int,
    periodo: str,
    linhas_ecd_classificadas: list[dict],
) -> Dict[str, Any]:
    """
    Diagnóstico real por versão.

    Ainda recebe ECD classificada por parâmetro.
    Mas já busca o SPED real da EfdRegistro.
    """

    linhas_sped = carregar_linhas_sped_por_versao(
        db,
        versao_id=versao_id,
    )

    return gerar_diagnostico_gap_ecd_efd(
        db=db,
        versao_id=versao_id,
        periodo=periodo,
        linhas_ecd_classificadas=linhas_ecd_classificadas,
        linhas_sped=linhas_sped,
    )

def carregar_linhas_ecd_elegiveis_por_versao(
    db: Session,
    *,
    versao_id: int,
) -> list[dict]:
    """
    Carrega linhas ECD já classificadas/enquadradas.
    """

    # ajustar para o modelo real de vocês
    rows = (
        db.query(ContextoFiscalVersao)
        .filter(ContextoFiscalVersao.versao_id == versao_id)
        .all()
    )

    linhas: list[dict] = []

    for row in rows:

        nat_bc_cred = getattr(row, "nat_bc_cred", None)
        valor = getattr(row, "valor_elegivel", None)

        if not nat_bc_cred:
            continue

        if not valor:
            continue

        linhas.append(
            {
                "periodo": getattr(row, "periodo", None),
                "nat_bc_cred": nat_bc_cred,
                "valor": valor,
                "elegivel_credito": True,
                "cod_cta": getattr(row, "cod_cta", None),
                "origem": getattr(row, "origem", None),
            }
        )

    return linhas


def carregar_linhas_ecd_elegiveis_reais(
    db: Session,
    *,
    empresa_id: int,
    periodo: str,
) -> list[dict]:
    periodo_norm = normalizar_periodo(periodo)
    if not periodo_norm:
        raise ValueError(f"Período inválido: {periodo}")

    ano = periodo_norm[:4]
    mes = periodo_norm[4:]

    contas = (
        db.query(EcdContaEmpresa)
        .filter(EcdContaEmpresa.empresa_id == empresa_id)
        .filter(EcdContaEmpresa.periodo.like(f"{ano}%"))
        .filter(
            or_(
                EcdContaEmpresa.elegivel_credito_confirmado == True,
                EcdContaEmpresa.elegivel_credito_sugerido == True,
            )
        )
        .all()
    )

    linhas: list[dict] = []

    for conta in contas:
        elegivel = (
            conta.elegivel_credito_confirmado
            if conta.elegivel_credito_confirmado is not None
            else conta.elegivel_credito_sugerido
        )

        if not elegivel:
            continue

        natureza = (
            db.query(EcdContaNaturezaEsperada)
            .filter(EcdContaNaturezaEsperada.empresa_id == empresa_id)
            .filter(EcdContaNaturezaEsperada.ecd_conta_empresa_id == conta.id)
            .filter(EcdContaNaturezaEsperada.ativo == True)
            .first()
        )

        nat_bc_cred = (
            str(natureza.natureza_codigo).strip().zfill(2)
            if natureza and natureza.natureza_codigo
            else "00"
        )
        tem_natureza = bool(
            natureza and natureza.natureza_codigo
        )
        cod_cta = conta.cod_cta

        valor = Decimal("0.00")
        origem_valor = None

        ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
        dt_res = f"{ultimo_dia:02d}{mes}{ano}"


        i355 = (
            db.query(EcdResultadoI355Db)
            .filter(EcdResultadoI355Db.empresa_id == empresa_id)
            .filter(EcdResultadoI355Db.cod_cta == cod_cta)
            .filter(EcdResultadoI355Db.dt_res == dt_res)
            .first()
        )

        if i355 and i355.vl_cta is not None:
            valor = Decimal(str(i355.vl_cta or 0))
            origem_valor = "I355"

        if valor <= 0:
            i155 = (
                db.query(EcdSaldoI155Db)
                .filter(EcdSaldoI155Db.empresa_id == empresa_id)
                .filter(EcdSaldoI155Db.cod_cta == cod_cta)
                .filter(EcdSaldoI155Db.dt_ini.like(f"{ano}{mes}%"))
                .first()
            )

            if i155:
                deb = Decimal(str(i155.vl_deb or 0))
                cred = Decimal(str(i155.vl_cred or 0))
                valor = max(deb, cred)
                origem_valor = "I155"

        if valor <= 0:
            continue

        linhas.append(
            {
                "periodo": periodo_norm,
                "cod_cta": cod_cta,
                "nome_cta": conta.nome_cta,
                "nat_bc_cred": nat_bc_cred,
                "tem_natureza": tem_natureza,
                "natureza_descricao": getattr(natureza, "natureza_descricao", None),
                "valor": valor,
                "elegivel_credito": True,
                "origem": origem_valor,
                "categoria": conta.categoria_confirmada or conta.categoria_sugerida,
                "grupo": conta.grupo_conta_confirmado or conta.grupo_conta_sugerido,
            }
        )

    return linhas