from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.domain.ecd.ecd_gap_service import montar_contexto_gap_ecd_efd


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
    caminho_saida = Path(caminho_saida)

    ctx = montar_contexto_gap_ecd_efd(
        db,
        empresa_id=empresa_id,
        versao_id=versao_id,
        periodo=periodo,
    )

    correcoes_automaticas = correcoes_automaticas or []

    # depois:
    # wb = Workbook()
    # criar_aba_resumo(wb, ctx, titulo=titulo)
    # criar_aba_cobertura_por_mes(wb, ctx)
    # criar_aba_bases_efd_por_natureza(wb, ctx)
    # criar_aba_alertas_efd_omissao(wb, ctx)
    # criar_aba_diagnostico_efd(wb, ctx)
    # criar_aba_detalhe_completo(wb, ctx)
    # criar_aba_investigar(wb, ctx)

    if incluir_correcoes_automaticas:
        # criar_aba_correcoes_automaticas(wb, correcoes_automaticas)
        pass

    # wb.save(caminho_saida)
    return caminho_saida