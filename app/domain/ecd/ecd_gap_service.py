from __future__ import annotations

from typing import Any, Dict
from sqlalchemy.orm import Session
from decimal import Decimal
from sqlalchemy import or_, text
import calendar
from app.db.models import EfdRegistro, ContextoFiscalVersao, EcdSaldoI155Db, EcdResultadoI355Db
from app.db.models.ecd_conta_empresa import EcdContaEmpresa

from app.domain.ecd.ecd_credito_analytics import (
    somar_despesa_ecd_potencial_por_mes_natureza,
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

    ecd_por_mes_nat = somar_despesa_ecd_potencial_por_mes_natureza(
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

        if reg and reg.startswith("M"):
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
        valor_ecd = Decimal(str(dados.get("valor_ecd_elegivel") or "0"))
        valor_efd = Decimal(str(dados.get("base_efd_declarada") or "0"))
        gap = Decimal(str(dados.get("gap_base") or "0"))

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

def buscar_naturezas_categoria_esperada(
    db: Session,
    *,
    categoria: str,
    grupo: str | None = None,
) -> list[dict]:
    categoria = str(categoria or "").strip()
    grupo = str(grupo or "").strip()

    if not categoria or categoria == "NaoClassificado":
        return []

    rows = db.execute(
        text("""
            SELECT
                categoria,
                grupo_conta,
                natureza_codigo,
                natureza_descricao,
                fundamento,
                prioridade,
                confianca,
                observacao_padrao
            FROM ecd_categoria_natureza_esperada
            WHERE ativo = 1
              AND categoria = :categoria
              AND (
                    :grupo = ''
                    OR grupo_conta IS NULL
                    OR grupo_conta = ''
                    OR grupo_conta = :grupo
              )
            ORDER BY prioridade ASC, natureza_codigo ASC
        """),
        {
            "categoria": categoria,
            "grupo": grupo,
        },
    ).mappings().all()

    return [dict(r) for r in rows]

def carregar_linhas_ecd_com_natureza_real(
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
                EcdContaEmpresa.grupo_conta_confirmado.isnot(None),
                EcdContaEmpresa.grupo_conta_sugerido.isnot(None),
            )
        )
        .all()
    )

    linhas: list[dict] = []

    for conta in contas:

        categoria = conta.categoria_confirmada or conta.categoria_sugerida
        grupo = conta.grupo_conta_confirmado or conta.grupo_conta_sugerido


        naturezas_catalogo = buscar_naturezas_categoria_esperada(
            db,
            categoria=categoria,
            grupo=grupo,
        )

        naturezas_esperadas = []
        for item in naturezas_catalogo:
            nat = str(item.get("natureza_codigo") or "").strip().zfill(2)
            if nat and nat != "00" and nat not in naturezas_esperadas:
                naturezas_esperadas.append(nat)


        nat_bc_cred = naturezas_esperadas[0] if naturezas_esperadas else "00"
        tem_natureza = bool(naturezas_esperadas)

        natureza_descricao = (
            naturezas_catalogo[0].get("natureza_descricao")
            if naturezas_catalogo
            else None
        )

        confianca = (
            naturezas_catalogo[0].get("confianca")
            if naturezas_catalogo
            else None
        )

        fundamento = (
            naturezas_catalogo[0].get("fundamento")
            if naturezas_catalogo
            else None
        )
        observacao = (
            naturezas_catalogo[0].get("observacao_padrao")
            if naturezas_catalogo
            else None
        )

        tem_catalogo = bool(naturezas_catalogo)

        origem_classificacao = (
            "CSV"
            if conta.categoria_confirmada or conta.grupo_conta_confirmado
            else "Heurística"
        )

        if not tem_catalogo:
            fundamento = "Investigar"
            confianca = 50
            observacao = "Classificação sem correspondência no catálogo fiscal."
            nat_bc_cred = "00"
            naturezas_esperadas = []

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
        elegivel_credito = bool(
            conta.elegivel_credito_confirmado
            if conta.elegivel_credito_confirmado is not None
            else conta.elegivel_credito_sugerido
        )

        linhas.append(
            {
                "periodo": periodo_norm,
                "cod_cta": cod_cta,
                "nome_cta": conta.nome_cta,
                "nat_bc_cred": nat_bc_cred,
                "tem_natureza": tem_natureza,
                "natureza_descricao": natureza_descricao,
                "naturezas_esperadas": naturezas_esperadas,
                "fundamento": fundamento,
                "valor": valor,
                "potencial_credito": tem_natureza,
                "elegivel_credito": elegivel_credito,
                "origem": origem_valor,
                "origem_classificacao": origem_classificacao,
                "categoria": categoria,
                "confianca": confianca,
                "grupo": grupo,
                "observacao": observacao,
            }
        )

    return linhas

def montar_contexto_gap_ecd_efd(
    db,
    *,
    empresa_id: int,
    versao_id: int,
    periodo: str,
) -> dict:
    linhas_ecd = carregar_linhas_ecd_com_natureza_real(
        db=db,
        empresa_id=empresa_id,
        periodo=periodo,
    )

    diagnostico = gerar_diagnostico_gap_ecd_efd_por_versao(
        db=db,
        versao_id=versao_id,
        periodo=periodo,
        linhas_ecd_classificadas=linhas_ecd,
    )

    por_natureza = {}

    periodo_norm = diagnostico["resumo"]["periodo"]
    comparativo = diagnostico["comparativo"].get(periodo_norm) or {}

    for nat, dados in comparativo.items():
        gap = dados.get("gap_base") or Decimal("0")

        por_natureza[nat] = {
            "periodo": periodo_norm,
            "nat_bc_cred": nat,
            "tem_gap": gap > 0,
            "valor_gap": gap,
            "gap": gap,

            "status": dados.get("status"),

            "valor_ecd": dados.get("valor_ecd_elegivel"),
            "ecd_elegivel": dados.get("valor_ecd_elegivel"),

            "valor_efd": dados.get("base_efd_declarada"),
            "efd_declarada": dados.get("base_efd_declarada"),

            "cobertura_pct": dados.get("cobertura_pct"),

            "contas_ecd": (dados.get("ecd") or {}).get("codigos_cta", []),
            "origens": (dados.get("ecd") or {}).get("origens", []),

            "categorias": dados.get("categorias") or [],
            "grupos": dados.get("grupos") or [],
            "fundamentos": dados.get("fundamentos") or [],
            "naturezas_esperadas": dados.get("naturezas_esperadas") or [],

            "categoria": ", ".join(dados.get("categorias") or []),
            "grupo": ", ".join(dados.get("grupos") or []),
            "fundamento": ", ".join(dados.get("fundamentos") or []),
            "observacao": ", ".join(dados.get("observacao_padrao") or []),

        }

    return {
        "periodo": periodo_norm,
        "resumo": diagnostico["resumo"],
        "por_natureza": por_natureza,
        "linhas_ecd": linhas_ecd,
        "comparativo": diagnostico["comparativo"],
        "ecd_por_mes_nat": diagnostico["ecd_por_mes_nat"],
        "efd_por_mes_nat": diagnostico["efd_por_mes_nat"],
    }