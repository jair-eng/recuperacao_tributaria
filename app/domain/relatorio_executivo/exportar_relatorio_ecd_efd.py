from __future__ import annotations

from pathlib import Path
from typing import Any
from openpyxl import Workbook
from sqlalchemy.orm import Session
from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd
from app.domain.fiscal.catalogo.natureza_credito_catalogo import carregar_mapa_nat_bc_cred
from app.domain.relatorio_executivo.aba_alertas_efd_omissao import criar_aba_alertas_efd_omissao
from app.domain.relatorio_executivo.aba_base_por_categoria import criar_aba_base_por_categoria
from app.domain.relatorio_executivo.aba_base_por_natureza import criar_aba_base_por_natureza
from app.domain.relatorio_executivo.aba_diagnostico_efd import criar_aba_diagnostico_efd
from app.domain.relatorio_executivo.aba_investigar import criar_aba_investigar
from app.domain.relatorio_executivo.aba_oportunidades_c170 import criar_aba_oportunidades_c170
from app.domain.relatorio_executivo.aba_oportunidades_f100 import criar_aba_oportunidades_f100
from app.domain.relatorio_executivo.aba_resumo import criar_aba_resumo
from app.domain.relatorio_executivo.aba_categorias import criar_abas_por_categoria
from app.utils.excel import remover_aba_padrao, criar_aba_generica


def exportar_relatorio_executivo_ecd_efd_por_ctx(
    *,
    ctx: dict,
    caminho_saida: str | Path,
    titulo: str = "Relatório Executivo ECD x EFD",
    incluir_correcoes_automaticas: bool = True,
    correcoes_automaticas: list[dict[str, Any]] | None = None,
) -> Path:
    caminho_saida = Path(caminho_saida)
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    correcoes_automaticas = correcoes_automaticas or []

    wb = Workbook()
    remover_aba_padrao(wb)

    criar_aba_alertas_efd_omissao(wb, ctx)
    criar_aba_resumo(wb, ctx, titulo=titulo)

    dominio = str(ctx.get("dominio") or "GERAL").upper()

    criar_aba_oportunidades_c170(wb, ctx)
    criar_aba_oportunidades_f100(wb, ctx)
    criar_aba_base_por_categoria(wb, ctx)
    criar_aba_base_por_natureza(wb, ctx)
    criar_aba_diagnostico_efd(wb, ctx)
    criar_aba_investigar(wb, ctx)
    criar_abas_por_categoria(wb, ctx)

    if incluir_correcoes_automaticas:
        criar_aba_generica(
            wb,
            nome_aba="CorrecoesAutomaticas",
            headers=[
                "Regra",
                "Tipo de correção",
                "Impacto financeiro",
                "Automatizável?",
                "Status",
            ],
            rows=correcoes_automaticas,
        )

    if "Resumo" in wb.sheetnames:
        ws_resumo = wb["Resumo"]
        wb._sheets.remove(ws_resumo)
        wb._sheets.insert(0, ws_resumo)

    wb.save(caminho_saida)
    return caminho_saida

def exportar_relatorio_executivo_ecd_efd(
    db: Session,
    *,
    empresa_id: int,
    versao_id: int,
    periodo: str,
    caminho_saida: str | Path,
    incluir_correcoes_automaticas: bool = True,
    correcoes_automaticas: list[dict[str, Any]] | None = None,
    titulo: str = "Relatório Executivo ECD x EFD",
) -> Path:
    ctx = montar_contexto_gap_ecd_efd(
        db,
        empresa_id=empresa_id,
        versao_id=versao_id,
        periodo=periodo,
    )

    ctx["mapa_nat_bc_cred"] = carregar_mapa_nat_bc_cred(db)

    return exportar_relatorio_executivo_ecd_efd_por_ctx(
        ctx=ctx,
        caminho_saida=caminho_saida,
        incluir_correcoes_automaticas=incluir_correcoes_automaticas,
        correcoes_automaticas=correcoes_automaticas,
        titulo=titulo,
    )